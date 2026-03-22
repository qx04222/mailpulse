"""
Hourly lightweight sync: pull new emails + AI score + notify urgent items.
Runs Mon-Sat 10:00-17:00 every hour. No reports, no full analysis.
High-priority emails (score >= 4) get instant Lark DM to the assignee.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

from ..config import reload_config, load_companies, load_people, get_person_by_id
from ..main import run_company
from ..storage.db import db
from ..destinations.lark import send_user_card
from ..destinations.lark_cards import build_client_thread_card
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


async def notify_urgent_emails(company: Dict[str, Any]):
    """Send instant Lark DM for high-priority emails found during sync."""
    company_id = company["id"]
    company_name = company["name"]

    urgent = _get_new_urgent_emails(company_id)
    if not urgent:
        return 0

    people = load_people()
    people_map = {p["id"]: p for p in people}
    sent = 0

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

        # Build a quick notification card
        card = build_client_thread_card(
            thread_id=email.get("thread_id", ""),
            subject=email.get("subject", ""),
            client_name=email.get("client_name", ""),
            score=email.get("score", 4),
            summary=email.get("one_line", ""),
            assignee=person.get("name", ""),
            email_count=1,
            direction="inbound",
            action_item_id=None,
        )

        msg_id = send_user_card(person["lark_user_id"], card)
        if msg_id:
            _record_notification(company_id, email_id, assigned_id)
            sent += 1
            logger.info(f"[Hourly] Urgent notify: {email['subject'][:40]} -> {person['name']}")

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
