"""
Events storage layer — maps to the `events` table.
Business events generated during digest runs (new_client, overdue, sla_breach, etc.)
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .db import db


def create_event(
    company_id: str,
    event_type: str,
    severity: str,
    title: str,
    description: Optional[str] = None,
    thread_id: Optional[str] = None,
    email_id: Optional[str] = None,
    client_id: Optional[str] = None,
    person_id: Optional[str] = None,
    action_item_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new event record.

    event_type must be one of:
        new_client, new_inquiry, quote_sent, quote_followup,
        client_replied, overdue_warning, overdue_escalation,
        complaint, deal_closed, deal_lost,
        assignment_changed, sla_breach, digest_completed, custom
    severity: info, warning, critical
    """
    data: Dict[str, Any] = {
        "company_id": company_id,
        "event_type": event_type,
        "severity": severity,
        "title": title,
    }
    if description:
        data["description"] = description
    if thread_id:
        data["thread_id"] = thread_id
    if email_id:
        data["email_id"] = email_id
    if client_id:
        data["client_id"] = client_id
    if person_id:
        data["person_id"] = person_id
    if action_item_id:
        data["action_item_id"] = action_item_id
    if metadata:
        data["metadata"] = metadata

    resp = db.table("events").insert(data).execute()
    return resp.data[0] if resp.data else data


def get_events_by_company(
    company_id: str,
    limit: int = 50,
    unread_only: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch events for a company."""
    query = db.table("events") \
        .select("*") \
        .eq("company_id", company_id) \
        .order("created_at", desc=True) \
        .limit(limit)

    if unread_only:
        query = query.eq("is_read", False)

    resp = query.execute()
    return resp.data or []


def mark_event_read(event_id: str) -> None:
    """Mark an event as read."""
    db.table("events").update({"is_read": True}).eq("id", event_id).execute()


def mark_event_resolved(event_id: str, resolved_by_id: Optional[str] = None) -> None:
    """Mark an event as resolved."""
    data: Dict[str, Any] = {
        "is_resolved": True,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }
    if resolved_by_id:
        data["resolved_by_id"] = resolved_by_id
    db.table("events").update(data).eq("id", event_id).execute()
