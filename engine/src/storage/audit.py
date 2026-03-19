"""
Audit log storage layer — maps to the `audit_logs` table.
Records who did what and when, for admin/compliance purposes.
"""
from typing import Optional, Dict, Any, List

from .db import db


def log_action(
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    entity_name: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_name: str = "System",
    changes: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Write an audit log entry.

    action must be one of:
        create, update, delete, login, logout,
        assign, unassign, role_change, status_change,
        report_generated, digest_run, telegram_bind, telegram_unbind,
        export, import
    """
    data: Dict[str, Any] = {
        "action": action,
        "entity_type": entity_type,
        "actor_name": actor_name,
    }
    if actor_id:
        data["actor_id"] = actor_id
    if entity_id:
        data["entity_id"] = entity_id
    if entity_name:
        data["entity_name"] = entity_name
    if changes:
        data["changes"] = changes
    if description:
        data["description"] = description
    if ip_address:
        data["ip_address"] = ip_address
    if user_agent:
        data["user_agent"] = user_agent

    resp = db.table("audit_logs").insert(data).execute()
    return resp.data[0] if resp.data else data


def get_audit_log(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Query audit log entries with optional filters."""
    query = db.table("audit_logs") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(limit)

    if entity_type:
        query = query.eq("entity_type", entity_type)
    if entity_id:
        query = query.eq("entity_id", entity_id)
    if actor_id:
        query = query.eq("actor_id", actor_id)

    resp = query.execute()
    return resp.data or []
