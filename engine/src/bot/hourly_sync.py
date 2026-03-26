"""
Hourly lightweight sync: pull new emails + AI score + notify urgent items.
Runs Mon-Sat 10:00-17:00 every hour. No reports, no full analysis.
High-priority emails (score >= 4) get instant Lark DM to the assignee.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from ..config import reload_config, load_companies, load_people, get_person_by_id
from ..main import run_company
from ..storage.db import db
from ..destinations.lark import send_user_message
from .helpers import is_feature_enabled

logger = logging.getLogger(__name__)


def _get_new_urgent_emails(company_id: str, since_minutes: int = 65) -> List[Dict]:
    """Get emails scored >= 4 that were inserted in the last ~hour."""
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()
        resp = db.table("emails") \
            .select("id, subject, sender_email, one_line, score, action_needed, assigned_to_id, client_name, received_at, thread_id") \
            .eq("company_id", company_id) \
            .gte("score", 4) \
            .gte("created_at", cutoff) \
            .order("score", desc=True) \
            .limit(10) \
            .execute()
        return resp.data or []
    except Exception as e:
        logger.error(f"[Hourly] Error querying urgent emails: {e}")
        return []


def _already_notified(email_id: str) -> bool:
    """Check if we already sent an urgent notification for this email."""
    try:
        resp = db.table("events") \
            .select("id") \
            .eq("email_id", email_id) \
            .eq("event_type", "urgent_notify") \
            .limit(1) \
            .execute()
        return bool(resp.data)
    except Exception:
        return False


def _record_notification(company_id: str, email_id: str, person_id: str):
    """Record that we sent an urgent notification."""
    try:
        from ..storage.events import create_event
        create_event(
            company_id=company_id,
            event_type="urgent_notify",
            severity="info",
            title="Urgent email notification sent",
            email_id=email_id,
            person_id=person_id,
        )
    except Exception:
        pass


def _ensure_action_item(email: Dict, company_id: str, assigned_to_id: str) -> Optional[str]:
    """Find or create an action_item for an urgent email. Returns item_id."""
    thread_id = email.get("thread_id")
    try:
        # Check if action_item already exists for this thread
        if thread_id:
            resp = db.table("action_items") \
                .select("id") \
                .eq("thread_id", thread_id) \
                .eq("company_id", company_id) \
                .in_("status", ["pending", "in_progress", "overdue"]) \
                .limit(1) \
                .execute()
            if resp.data:
                return resp.data[0]["id"]

        # Create new action_item
        score = email.get("score", 4)
        priority = "high" if score >= 5 else "medium"
        resp = db.table("action_items").insert({
            "company_id": company_id,
            "thread_id": thread_id,
            "email_id": email.get("id"),
            "title": email.get("subject", "")[:200],
            "priority": priority,
            "status": "pending",
            "assigned_to_id": assigned_to_id,
            "description": email.get("one_line", ""),
            "seen_count": 1,
        }).execute()
        if resp.data:
            return resp.data[0]["id"]
    except Exception as e:
        logger.error(f"[Hourly] Error ensuring action_item: {e}")
    return None


async def notify_urgent_emails(company: Dict[str, Any]):
    """Send consolidated Lark DM for high-priority emails found during sync."""
    company_id = company["id"]
    company_name = company["name"]

    urgent = _get_new_urgent_emails(company_id)
    if not urgent:
        return 0

    people = load_people()
    people_map = {p["id"]: p for p in people}

    # Group by assignee: person_id -> list of task data
    per_person: Dict[str, List[Dict]] = {}
    notifiable_emails: Dict[str, List[Dict]] = {}  # person_id -> emails (for record_notification)

    for email in urgent:
        email_id = email.get("id")
        if not email_id or _already_notified(email_id):
            continue

        assigned_id = email.get("assigned_to_id")
        if not assigned_id:
            continue

        person = people_map.get(assigned_id)
        if not person or not person.get("lark_user_id"):
            continue

        action_item_id = _ensure_action_item(email, company_id, assigned_id)

        per_person.setdefault(assigned_id, []).append({
            "subject": email.get("subject", ""),
            "client_name": email.get("client_name", ""),
            "score": email.get("score", 4),
            "summary": email.get("one_line", ""),
            "action_item_id": action_item_id,
        })
        notifiable_emails.setdefault(assigned_id, []).append({
            "email_id": email_id,
            "action_item_id": action_item_id,
        })

    # Send one plain-text DM per person
    sent = 0
    for person_id, tasks in per_person.items():
        person = people_map.get(person_id)
        if not person:
            continue

        lines = []
        for i, t in enumerate(tasks, 1):
            score = t.get("score", 0)
            icon = "🔴" if score >= 5 else ("🟠" if score >= 4 else "🟡")
            subject = t.get("subject", "")[:50]
            client = t.get("client_name", "")
            summary = t.get("summary", "")
            line = f"{icon} {i}. {subject}"
            if client:
                line += f"\n   客户: {client}"
            if summary:
                line += f" · {summary}"
            lines.append(line)

        task_text = f"⚡ {company_name} 紧急邮件 ({len(tasks)}项)\n\n"
        task_text += "\n".join(lines)
        task_text += "\n\n💡 回复 \"添加任务 <内容>\" 可快速创建个人待办"

        dm_ok = send_user_message(person["lark_user_id"], task_text)
        if dm_ok:
            for entry in notifiable_emails.get(person_id, []):
                _record_notification(company_id, entry["email_id"], person_id)
                if entry.get("action_item_id"):
                    try:
                        db.table("action_items").update({
                            "dm_sent_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", entry["action_item_id"]).execute()
                    except Exception:
                        pass
            sent += len(tasks)
            logger.info(f"[Hourly] Sent {len(tasks)} tasks to {person['name']} (text DM)")

    return sent


async def hourly_sync():
    """
    Lightweight hourly sync: pull emails + score + notify urgent.
    10:00-17:00 Mon-Sat.
    """
    logger.info("[Hourly Sync] Starting...")
    reload_config()
    companies = load_companies()

    total_emails = 0
    total_urgent = 0

    for company in companies:
        try:
            result = await run_company(company, sync_only=True)
            emails = result.get("emails", 0)
            total_emails += emails

            # Notify urgent emails
            urgent_count = await notify_urgent_emails(company)
            total_urgent += urgent_count

            if emails > 0 or urgent_count > 0:
                logger.info(f"[Hourly] {company['name']}: {emails} emails, {urgent_count} urgent notified")

        except Exception as e:
            logger.error(f"[Hourly] Error for {company['name']}: {e}")

    logger.info(f"[Hourly Sync] Done: {total_emails} emails synced, {total_urgent} urgent notified")
