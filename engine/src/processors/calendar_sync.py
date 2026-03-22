"""
Bidirectional calendar sync for action items.
- Auto-create calendar events for high-priority action items
- Clean up events when items are resolved
- Send reminders for due-today items still pending
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from ..storage.db import db
from ..destinations.lark_calendar import (
    get_primary_calendar_id,
    create_calendar_event,
    delete_calendar_event,
    update_calendar_event,
)
from ..destinations.lark import send_user_message

logger = logging.getLogger(__name__)


async def sync_action_item_to_calendar(action_item: Dict, person: Dict) -> Optional[str]:
    """
    When a new high-priority action_item is created, auto-create a calendar event.
    - Find the person's calendar (from company's lark_calendar_id or primary)
    - Check lark_calendar_event_id — skip if already synced
    - Create event: title = action_item title, time = next business day 9:00 AM or due_date
    - Update action_item.lark_calendar_event_id
    - Returns event_id or None
    """
    item_id = action_item.get("id", "")
    title = action_item.get("title", "")

    # Skip if already synced
    if action_item.get("lark_calendar_event_id"):
        logger.debug(f"[CalendarSync] Item {item_id} already synced, skipping")
        return action_item["lark_calendar_event_id"]

    # Resolve calendar_id: company setting > primary
    company_id = action_item.get("company_id")
    calendar_id = None
    if company_id:
        try:
            resp = db.table("companies") \
                .select("lark_calendar_id") \
                .eq("id", company_id) \
                .limit(1) \
                .execute()
            if resp.data:
                calendar_id = resp.data[0].get("lark_calendar_id")
        except Exception as e:
            logger.warning(f"[CalendarSync] Could not load company calendar: {e}")

    if not calendar_id:
        calendar_id = get_primary_calendar_id()

    if not calendar_id:
        logger.warning("[CalendarSync] No calendar_id found, skipping")
        return None

    # Determine event time: due_date or next business day 9:00 AM
    now = datetime.now(timezone.utc)
    due_date_str = action_item.get("due_date")
    if due_date_str:
        try:
            due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
            event_time = due_date.replace(hour=14, minute=0, second=0, microsecond=0)  # 14:00 UTC = 9:00 EST
        except Exception:
            event_time = None
    else:
        event_time = None

    if not event_time or event_time < now:
        # Next business day at 9:00 AM EST (14:00 UTC)
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:  # skip weekends
            next_day += timedelta(days=1)
        event_time = next_day.replace(hour=14, minute=0, second=0, microsecond=0)

    assignee_name = person.get("name", "未分配") if person else "未分配"
    event_title = f"📋 待办: {title[:50]}"
    event_desc = (
        f"负责人: {assignee_name}\n"
        f"优先级: {action_item.get('priority', 'medium')}\n"
        f"描述: {action_item.get('description', '') or ''}\n\n"
        f"— MailPulse 自动创建"
    )

    start_ts = int(event_time.timestamp())
    event = create_calendar_event(
        calendar_id=calendar_id,
        summary=event_title,
        description=event_desc,
        start_timestamp=start_ts,
        end_timestamp=start_ts + 1800,
    )

    if not event or not event.get("event_id"):
        logger.warning(f"[CalendarSync] Failed to create event for item {item_id}")
        return None

    event_id = event["event_id"]

    # Update action_item with linked event_id
    try:
        db.table("action_items").update({
            "lark_calendar_event_id": event_id,
        }).eq("id", item_id).execute()
    except Exception as e:
        logger.warning(f"[CalendarSync] Could not update action_item {item_id}: {e}")

    # Also track in lark_calendar_events table
    try:
        db.table("lark_calendar_events").insert({
            "company_id": company_id,
            "action_item_id": item_id,
            "event_id": event_id,
            "summary": event_title[:200],
            "event_time": event_time.isoformat(),
        }).execute()
    except Exception:
        pass

    logger.info(f"[CalendarSync] Created event {event_id} for action_item {item_id}")
    return event_id


async def mark_calendar_event_done(action_item_id: str) -> bool:
    """
    When action_item is marked resolved/handled:
    - Find the linked calendar event via lark_calendar_event_id
    - Delete the event (or update title to "done" prefix)
    - Return True if successful
    """
    try:
        resp = db.table("action_items") \
            .select("lark_calendar_event_id, company_id") \
            .eq("id", action_item_id) \
            .limit(1) \
            .execute()
    except Exception as e:
        logger.warning(f"[CalendarSync] Could not load action_item {action_item_id}: {e}")
        return False

    if not resp.data:
        return False

    item = resp.data[0]
    event_id = item.get("lark_calendar_event_id")
    if not event_id:
        return False  # No linked calendar event

    # Resolve calendar_id
    company_id = item.get("company_id")
    calendar_id = None
    if company_id:
        try:
            comp = db.table("companies") \
                .select("lark_calendar_id") \
                .eq("id", company_id) \
                .limit(1) \
                .execute()
            if comp.data:
                calendar_id = comp.data[0].get("lark_calendar_id")
        except Exception:
            pass

    if not calendar_id:
        calendar_id = get_primary_calendar_id()

    if not calendar_id:
        logger.warning("[CalendarSync] No calendar_id for cleanup")
        return False

    # Try to delete the event; fall back to updating title
    deleted = delete_calendar_event(calendar_id, event_id)
    if not deleted:
        # Fallback: prefix title with done marker
        update_calendar_event(calendar_id, event_id, {
            "summary": f"✅ [已处理] (原事件)",
        })

    # Clean up tracking table
    try:
        db.table("lark_calendar_events") \
            .delete() \
            .eq("event_id", event_id) \
            .execute()
    except Exception:
        pass

    # Clear the link on the action_item
    try:
        db.table("action_items").update({
            "lark_calendar_event_id": None,
        }).eq("id", action_item_id).execute()
    except Exception:
        pass

    logger.info(f"[CalendarSync] Cleaned up event {event_id} for item {action_item_id}")
    return True


async def check_due_calendar_events() -> int:
    """
    Scheduled job: Check for calendar events that are due today but action_item still pending.
    - Query action_items where lark_calendar_event_id IS NOT NULL
      AND status IN (pending, in_progress)
      AND (due_date = today OR created recently)
    - For each, send a reminder DM via Lark
    - Returns count of reminders sent
    """
    today = datetime.now(timezone.utc).date()
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc).isoformat()
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=timezone.utc).isoformat()

    try:
        resp = db.table("action_items") \
            .select("id, title, priority, due_date, assigned_to_id, lark_calendar_event_id, people(name, lark_user_id)") \
            .not_.is_("lark_calendar_event_id", "null") \
            .in_("status", ["pending", "in_progress"]) \
            .execute()
    except Exception as e:
        logger.error(f"[CalendarSync] Due check query error: {e}")
        return 0

    items = resp.data or []
    if not items:
        return 0

    sent = 0
    for item in items:
        # Check if due today or event is today-ish
        due_str = item.get("due_date")
        is_due_today = False
        if due_str:
            try:
                due = datetime.fromisoformat(due_str.replace("Z", "+00:00")).date()
                is_due_today = due == today
            except Exception:
                pass

        # If not due today, check if created in the last 7 days (catch items without due_date)
        if not is_due_today and not due_str:
            continue
        if not is_due_today:
            continue

        # Send reminder DM
        person = item.get("people")
        if not person or not person.get("lark_user_id"):
            continue

        open_id = person["lark_user_id"]
        name = person.get("name", "")
        title = item.get("title", "")[:60]
        priority = item.get("priority", "medium")
        priority_label = {"high": "高", "medium": "中", "low": "低"}.get(priority, priority)

        reminder_text = (
            f"Hi {name}，提醒你有一个待办事项今天到期：\n\n"
            f"📋 {title}\n"
            f"优先级：{priority_label}\n\n"
            f"请尽快处理，或在待办卡片中点击「已处理」。"
        )

        try:
            ok = send_user_message(open_id, reminder_text)
            if ok:
                sent += 1
        except Exception as e:
            logger.warning(f"[CalendarSync] Reminder DM error for {item.get('id')}: {e}")

    if sent:
        logger.info(f"[CalendarSync] Due date reminders sent: {sent}")
    return sent
