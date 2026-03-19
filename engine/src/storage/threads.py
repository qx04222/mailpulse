"""
Thread storage layer — maps to the `threads` table.
Tracks conversation-level state: status, counters, timestamps.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .db import db


def upsert_thread(
    gmail_thread_id: str,
    company_id: str,
    subject: str,
    direction: str,
    received_at: datetime,
    client_id: Optional[str] = None,
    assigned_to_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create or update a thread record.
    - Increments email_count and direction-specific counters.
    - Updates timestamps.
    - Updates status based on latest direction.
    Returns the thread row (with id).
    """
    existing = get_thread_by_gmail_id(gmail_thread_id)

    if existing:
        thread_id = existing["id"]
        email_count = existing["email_count"] + 1
        inbound_count = existing["inbound_count"] + (1 if direction == "inbound" else 0)
        outbound_count = existing["outbound_count"] + (1 if direction == "outbound" else 0)

        updates: Dict[str, Any] = {
            "email_count": email_count,
            "inbound_count": inbound_count,
            "outbound_count": outbound_count,
            "last_email_at": received_at.isoformat(),
        }

        if direction == "inbound":
            updates["last_inbound_at"] = received_at.isoformat()
        else:
            updates["last_outbound_at"] = received_at.isoformat()

        # Update status based on who sent last
        updates["status"] = _compute_status(direction, existing)

        # Update client/assignee if provided and not already set
        if client_id and not existing.get("client_id"):
            updates["client_id"] = client_id
        if assigned_to_id and not existing.get("assigned_to_id"):
            updates["assigned_to_id"] = assigned_to_id

        # Update subject if it was missing
        if subject and not existing.get("subject"):
            updates["subject"] = subject

        resp = db.table("threads").update(updates).eq("id", thread_id).execute()
        return resp.data[0] if resp.data else existing

    else:
        # New thread
        initiated_by = "them" if direction == "inbound" else "us"
        status = "active" if direction == "inbound" else "waiting_reply"

        data: Dict[str, Any] = {
            "gmail_thread_id": gmail_thread_id,
            "company_id": company_id,
            "subject": subject,
            "status": status,
            "initiated_by": initiated_by,
            "email_count": 1,
            "inbound_count": 1 if direction == "inbound" else 0,
            "outbound_count": 1 if direction == "outbound" else 0,
            "first_email_at": received_at.isoformat(),
            "last_email_at": received_at.isoformat(),
        }

        if direction == "inbound":
            data["last_inbound_at"] = received_at.isoformat()
        else:
            data["last_outbound_at"] = received_at.isoformat()

        if client_id:
            data["client_id"] = client_id
        if assigned_to_id:
            data["assigned_to_id"] = assigned_to_id

        resp = db.table("threads").insert(data).execute()
        return resp.data[0] if resp.data else data


def _compute_status(direction: str, existing: Dict[str, Any]) -> str:
    """
    Determine thread status:
    - Our team sent last -> 'waiting_reply'
    - Client sent last -> 'active'
    - No activity > 14 days -> 'stale'
    """
    # Check for staleness based on last_email_at
    last_email_str = existing.get("last_email_at")
    if last_email_str:
        try:
            if isinstance(last_email_str, str):
                last_email = datetime.fromisoformat(last_email_str.replace("Z", "+00:00"))
            else:
                last_email = last_email_str
            if last_email.tzinfo is None:
                last_email = last_email.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - last_email) > timedelta(days=14):
                return "stale"
        except (ValueError, TypeError):
            pass

    # Active direction-based status
    if direction == "outbound":
        return "waiting_reply"
    else:
        return "active"


def get_thread_by_gmail_id(gmail_thread_id: str) -> Optional[Dict[str, Any]]:
    """Look up a thread by Gmail thread ID."""
    resp = db.table("threads") \
        .select("*") \
        .eq("gmail_thread_id", gmail_thread_id) \
        .limit(1) \
        .execute()
    return resp.data[0] if resp.data else None


def get_threads_by_company(
    company_id: str,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch threads for a company, optionally filtered by status."""
    query = db.table("threads") \
        .select("*") \
        .eq("company_id", company_id) \
        .order("last_email_at", desc=True) \
        .limit(limit)

    if status:
        query = query.eq("status", status)

    resp = query.execute()
    return resp.data or []


def mark_thread_resolved(thread_id: str) -> None:
    """Mark a thread as resolved."""
    db.table("threads").update({
        "status": "resolved",
    }).eq("id", thread_id).execute()


def mark_stale_threads(company_id: str, days: int = 14) -> int:
    """Mark threads with no activity in `days` as stale. Returns count updated."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    resp = db.table("threads") \
        .update({"status": "stale"}) \
        .eq("company_id", company_id) \
        .in_("status", ["active", "waiting_reply"]) \
        .lt("last_email_at", cutoff) \
        .execute()
    return len(resp.data) if resp.data else 0
