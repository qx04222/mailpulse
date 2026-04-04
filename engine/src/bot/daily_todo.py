"""
Daily todo card sender — pushes personal todo cards to each person via Lark DM.
Scheduled at 9:30 AM, only sends if the person has pending items.
"""
import logging
from datetime import datetime, timezone, timedelta, time as dt_time
from typing import List, Dict, Any

from ..config import load_companies, load_people
from ..storage.db import db
from ..storage.action_items import get_pending_items
from ..destinations.lark import send_user_message
from .helpers import is_feature_enabled, get_person_companies
from ..utils.holidays import is_business_day

logger = logging.getLogger(__name__)


def _get_followup_reminders(person_id: str) -> List[Dict]:
    """Get pending follow-up reminders due today or overdue."""
    try:
        now = datetime.now(timezone.utc)
        end_of_day = now.replace(hour=23, minute=59, second=59)
        resp = db.table("follow_up_reminders") \
            .select("*") \
            .eq("person_id", person_id) \
            .eq("status", "pending") \
            .lte("remind_at", end_of_day.isoformat()) \
            .order("remind_at") \
            .limit(10) \
            .execute()
        return resp.data or []
    except Exception:
        return []


async def send_daily_todo(person: Dict[str, Any]) -> bool:
    """Send daily todo card to a single person. Returns True if sent."""
    person_id = person["id"]
    open_id = person.get("lark_user_id")
    name = person.get("name", "")

    if not open_id:
        return False

    # Check quiet hours (quiet_hours are in America/Toronto local time)
    try:
        from zoneinfo import ZoneInfo
        local_now = datetime.now(ZoneInfo("America/Toronto"))
    except Exception:
        local_now = datetime.now(timezone.utc)
    quiet_start = person.get("quiet_hours_start")
    quiet_end = person.get("quiet_hours_end")
    if quiet_start and quiet_end:
        # Parse string times (e.g. "22:00:00") to datetime.time if needed
        if isinstance(quiet_start, str):
            parts = quiet_start.split(":")
            quiet_start = dt_time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
        if isinstance(quiet_end, str):
            parts = quiet_end.split(":")
            quiet_end = dt_time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
        current_time = local_now.time()
        if quiet_start <= current_time <= quiet_end:
            return False

    # Check feature enabled for any of their companies
    companies = get_person_companies(person_id)
    if not any(is_feature_enabled(c["id"], "daily_todo") for c in companies):
        return False

    # Gather action items across all companies
    urgent_items = []
    pending_items = []

    for company in companies:
        items = get_pending_items(company["id"])
        for item in items:
            # Only show items assigned to this person (or unassigned)
            assigned = item.get("assigned_to_id")
            if assigned and assigned != person_id:
                continue

            days_pending = 0
            if item.get("created_at"):
                try:
                    created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                    days_pending = (datetime.now(timezone.utc) - created).days
                except Exception:
                    pass

            enriched = {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "status": item.get("status", "pending"),
                "priority": item.get("priority", "medium"),
                "days_pending": days_pending,
                "company": company["name"],
            }

            if item.get("status") == "overdue" or (item.get("priority") == "high" and item.get("status") == "pending"):
                urgent_items.append(enriched)
            else:
                pending_items.append(enriched)

    # Get follow-up reminders
    followup_items = _get_followup_reminders(person_id)

    # Don't send if nothing to show
    if not urgent_items and not pending_items and not followup_items:
        return False

    # Sort: urgent by days_pending desc
    urgent_items.sort(key=lambda x: x.get("days_pending", 0), reverse=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%m月%d日 %A").replace(
        "Monday", "周一").replace("Tuesday", "周二").replace(
        "Wednesday", "周三").replace("Thursday", "周四").replace(
        "Friday", "周五").replace("Saturday", "周六").replace("Sunday", "周日")

    # Build plain-text todo list
    lines = [f"📋 {name} 今日待办 · {date_str}", ""]

    if urgent_items:
        lines.append("🔴 需立即处理")
        for i, item in enumerate(urgent_items[:5], 1):
            title = item.get("title", "")[:50]
            days = item.get("days_pending", 0)
            suffix = f" — 等待 {days} 天" if days else ""
            lines.append(f"{i}. {title}{suffix}")
        lines.append("")

    if followup_items:
        lines.append("📧 需跟进")
        for i, item in enumerate(followup_items[:5], 1):
            subject = item.get("subject", "")[:50]
            reason = item.get("reason", "")
            lines.append(f"{i}. {subject}")
            if reason:
                lines.append(f"   {reason}")
        lines.append("")

    if pending_items:
        lines.append("🟡 进行中")
        for i, item in enumerate(pending_items[:5], 1):
            title = item.get("title", "")[:50]
            lines.append(f"{i}. {title}")
        lines.append("")

    total = len(urgent_items) + len(pending_items) + len(followup_items)
    lines.append(f"共 {total} 项待办 · MailPulse")

    text = "\n".join(lines)
    msg_id = send_user_message(open_id, text)
    if msg_id:
        logger.info(f"[Daily Todo] Sent to {name}: {len(urgent_items)} urgent, {len(pending_items)} pending, {len(followup_items)} followups")
        return True
    return False


async def send_all_daily_todos():
    """Send daily todo cards to all eligible people."""
    if not is_business_day():
        logger.info("[Daily Todo] Skipped — not a business day (Sunday or holiday)")
        return
    logger.info("[Daily Todo] Starting daily todo push...")
    people = load_people()
    sent = 0
    skipped = 0

    for person in people:
        if not person.get("is_active", True):
            continue
        if not person.get("lark_user_id"):
            continue

        try:
            if await send_daily_todo(person):
                sent += 1
            else:
                skipped += 1
        except Exception as e:
            logger.error(f"[Daily Todo] Error for {person.get('name', '?')}: {e}")

    logger.info(f"[Daily Todo] Done: {sent} sent, {skipped} skipped")
