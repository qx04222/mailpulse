"""
Lark Calendar integration.
Auto-create follow-up events for high-priority threads and action items.
"""
import time as time_mod
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from .lark import _api_call


def get_primary_calendar_id() -> Optional[str]:
    """Get the primary calendar ID for the bot/tenant."""
    try:
        data = _api_call("GET", "/open-apis/calendar/v4/calendars", params={"page_size": 50})
        calendars = data.get("data", {}).get("calendar_list", [])
        for cal in calendars:
            if cal.get("role") == "owner" or cal.get("type") == "primary":
                return cal.get("calendar_id")
        if calendars:
            return calendars[0].get("calendar_id")
        return None
    except Exception as e:
        print(f"[Lark Calendar] Error getting calendars: {e}")
        return None


def create_calendar_event(
    calendar_id: str,
    summary: str,
    description: str = "",
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Create a calendar event. Returns event data or None."""
    if not start_timestamp:
        start_timestamp = int(time_mod.time()) + 3600
    if not end_timestamp:
        end_timestamp = start_timestamp + 1800  # 30 min

    event_body: Dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start_time": {"timestamp": str(start_timestamp)},
        "end_time": {"timestamp": str(end_timestamp)},
        "reminders": [{"minutes": 30}],
    }

    try:
        data = _api_call(
            "POST",
            f"/open-apis/calendar/v4/calendars/{calendar_id}/events",
            json_data=event_body,
        )
        event = data.get("data", {}).get("event", {})
        print(f"[Lark Calendar] Event created: {summary} -> {event.get('event_id')}")
        return event
    except Exception as e:
        print(f"[Lark Calendar] Error creating event: {e}")
        return None


def sync_followups_to_calendar(
    calendar_id: str,
    threads: List[Dict[str, Any]],
    action_items: List[Dict[str, Any]],
    company_id: str,
    company_name: str,
    people_map: Optional[Dict[str, str]] = None,
) -> int:
    """
    Create follow-up calendar events for:
    1. High-priority threads (score >= 4) → next business day 9:00 AM
    2. Action items with due dates → due date 9:00 AM

    Uses lark_calendar_events table to avoid duplicates.
    Returns number of events created.
    """
    if not calendar_id:
        print("[Lark Calendar] Sync skipped: no calendar_id configured")
        return 0

    people_map = people_map or {}

    # Load existing calendar events from DB
    existing_thread_ids: set = set()
    existing_action_ids: set = set()
    try:
        from ..storage.db import db
        resp = db.table("lark_calendar_events") \
            .select("thread_id,action_item_id") \
            .eq("company_id", company_id) \
            .execute()
        for row in (resp.data or []):
            if row.get("thread_id"):
                existing_thread_ids.add(row["thread_id"])
            if row.get("action_item_id"):
                existing_action_ids.add(row["action_item_id"])
    except Exception as e:
        print(f"[Lark Calendar] Could not load existing events: {e}")

    created = 0
    now = datetime.now(timezone.utc)

    # Next business day at 9:00 AM (EST/Toronto time)
    next_day = now + timedelta(days=1)
    while next_day.weekday() >= 5:  # skip weekends
        next_day += timedelta(days=1)
    followup_time = next_day.replace(hour=14, minute=0, second=0, microsecond=0)  # 14:00 UTC = 9:00 EST

    # 1. High-priority threads
    for t in threads:
        score = t.get("max_score", 0)
        if score < 4:
            continue

        db_thread_id = t.get("db_thread_id", "")
        if not db_thread_id or db_thread_id in existing_thread_ids:
            continue

        client_name = t.get("client_name", "") or "未知客户"
        subject = t.get("subject", "")[:50]
        assignee_id = t.get("assigned_to_id")
        assignee = people_map.get(assignee_id, "") if assignee_id else ""
        summary_text = t.get("thread_summary", "")[:200]

        event_title = f"📧 跟进: {client_name} - {subject}"
        event_desc = (
            f"公司: {company_name}\n"
            f"客户: {client_name}\n"
            f"负责人: {assignee or '未分配'}\n"
            f"优先级: {score}/5\n\n"
            f"摘要: {summary_text}\n\n"
            f"— MailPulse 自动创建"
        )

        start_ts = int(followup_time.timestamp())
        event = create_calendar_event(
            calendar_id=calendar_id,
            summary=event_title,
            description=event_desc,
            start_timestamp=start_ts,
            end_timestamp=start_ts + 1800,
        )
        if event and event.get("event_id"):
            created += 1
            try:
                from ..storage.db import db
                db.table("lark_calendar_events").insert({
                    "company_id": company_id,
                    "thread_id": db_thread_id,
                    "event_id": event["event_id"],
                    "summary": event_title[:200],
                    "event_time": followup_time.isoformat(),
                }).execute()
            except Exception:
                pass

    # 2. Action items with due dates
    for ai in action_items:
        action_id = ai.get("id", "")
        if not action_id or action_id in existing_action_ids:
            continue

        due_date_str = ai.get("due_date")
        if not due_date_str:
            continue

        try:
            due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
        except Exception:
            continue

        # Skip past due dates
        if due_date < now:
            continue

        title = ai.get("title", "")[:50]
        assignee_id = ai.get("assigned_to_id")
        assignee = people_map.get(assignee_id, "") if assignee_id else ""

        event_title = f"📋 待办: {title}"
        event_desc = (
            f"公司: {company_name}\n"
            f"负责人: {assignee or '未分配'}\n"
            f"描述: {ai.get('description', '') or ''}\n\n"
            f"— MailPulse 自动创建"
        )

        due_9am = due_date.replace(hour=14, minute=0, second=0, microsecond=0)
        start_ts = int(due_9am.timestamp())
        event = create_calendar_event(
            calendar_id=calendar_id,
            summary=event_title,
            description=event_desc,
            start_timestamp=start_ts,
            end_timestamp=start_ts + 1800,
        )
        if event and event.get("event_id"):
            created += 1
            try:
                from ..storage.db import db
                db.table("lark_calendar_events").insert({
                    "company_id": company_id,
                    "action_item_id": action_id,
                    "event_id": event["event_id"],
                    "summary": event_title[:200],
                    "event_time": due_9am.isoformat(),
                }).execute()
            except Exception:
                pass

    print(f"[Lark Calendar] Sync done: {created} events created")
    return created


def delete_calendar_event(calendar_id: str, event_id: str) -> bool:
    """Delete a calendar event. Used when action_item is resolved."""
    try:
        _api_call(
            "DELETE",
            f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}",
        )
        print(f"[Lark Calendar] Event deleted: {event_id}")
        return True
    except Exception as e:
        print(f"[Lark Calendar] Error deleting event {event_id}: {e}")
        return False


def update_calendar_event(calendar_id: str, event_id: str, updates: dict) -> bool:
    """Update an existing event (e.g., mark title as completed)."""
    try:
        _api_call(
            "PATCH",
            f"/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}",
            json_data=updates,
        )
        print(f"[Lark Calendar] Event updated: {event_id}")
        return True
    except Exception as e:
        print(f"[Lark Calendar] Error updating event {event_id}: {e}")
        return False
