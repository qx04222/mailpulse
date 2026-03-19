"""
Action items storage layer — maps to the `action_items` table.
Uses UUID foreign keys for company_id, thread_id, assigned_to_id.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .db import db
from ..config import settings


def upsert_action_item(
    company_id: str,
    thread_id: Optional[str],
    email_id: Optional[str],
    client_id: Optional[str],
    title: str,
    priority: str,
    assigned_to_id: Optional[str],
    run_id: str,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert or update an action item.
    If the same thread already has a pending/in_progress item for this company,
    update seen_count and last_seen_run_id instead of creating a new one.
    """
    # Look for existing open action item on the same thread
    if thread_id:
        existing = db.table("action_items") \
            .select("id, seen_count, status") \
            .eq("thread_id", thread_id) \
            .eq("company_id", company_id) \
            .in_("status", ["pending", "in_progress", "overdue"]) \
            .limit(1) \
            .execute()

        if existing.data:
            item = existing.data[0]
            new_count = item["seen_count"] + 1

            # Auto-escalate to overdue if seen too many times
            new_status = item["status"]
            if item["status"] == "pending" and new_count >= 3:
                new_status = "overdue"

            updates: Dict[str, Any] = {
                "seen_count": new_count,
                "last_seen_run_id": run_id,
                "status": new_status,
                "priority": priority,
            }
            if assigned_to_id:
                updates["assigned_to_id"] = assigned_to_id

            resp = db.table("action_items") \
                .update(updates) \
                .eq("id", item["id"]) \
                .execute()
            return resp.data[0] if resp.data else item

    # Create new action item
    data: Dict[str, Any] = {
        "company_id": company_id,
        "title": title,
        "priority": priority,
        "status": "pending",
        "first_seen_run_id": run_id,
        "last_seen_run_id": run_id,
        "seen_count": 1,
    }
    if thread_id:
        data["thread_id"] = thread_id
    if email_id:
        data["email_id"] = email_id
    if client_id:
        data["client_id"] = client_id
    if assigned_to_id:
        data["assigned_to_id"] = assigned_to_id
    if description:
        data["description"] = description
    if due_date:
        data["due_date"] = due_date

    resp = db.table("action_items").insert(data).execute()
    return resp.data[0] if resp.data else data


def get_pending_items(company_id: str) -> List[Dict[str, Any]]:
    """Get all pending/in_progress/overdue action items for a company."""
    resp = db.table("action_items") \
        .select("*, threads(gmail_thread_id, subject)") \
        .eq("company_id", company_id) \
        .in_("status", ["pending", "in_progress", "overdue"]) \
        .order("created_at") \
        .execute()
    return resp.data or []


def mark_resolved(
    item_id: str,
    note: str = "resolved",
) -> None:
    """Mark an action item as resolved."""
    db.table("action_items").update({
        "status": "resolved",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolution_note": note,
    }).eq("id", item_id).execute()


def mark_resolved_by_thread(
    thread_id: str,
    note: str = "auto: thread replied",
) -> None:
    """Mark all pending action items for a thread as resolved."""
    db.table("action_items").update({
        "status": "resolved",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolution_note": note,
    }).eq("thread_id", thread_id) \
      .in_("status", ["pending", "in_progress", "overdue"]) \
      .execute()


def get_overdue_items(company_id: str) -> List[Dict[str, Any]]:
    """Get action items that have been seen multiple times (overdue)."""
    resp = db.table("action_items") \
        .select("*") \
        .eq("company_id", company_id) \
        .eq("status", "overdue") \
        .order("created_at") \
        .execute()
    return resp.data or []
