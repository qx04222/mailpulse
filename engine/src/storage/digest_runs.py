"""
Digest runs storage layer — maps to the `digest_runs` table.
Tracks each digest execution: start, completion, stats, and report URLs.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .db import db


def create_run(
    company_id: str,
    lookback_days: int = 3,
) -> str:
    """
    Create a new digest run record in 'running' state.
    Returns the run_id (UUID).
    """
    resp = db.table("digest_runs").insert({
        "company_id": company_id,
        "run_date": datetime.now(timezone.utc).date().isoformat(),
        "lookback_days": lookback_days,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return resp.data[0]["id"]


def complete_run(
    run_id: str,
    stats: Dict[str, Any],
) -> None:
    """
    Mark a run as completed with statistics.

    Expected stats keys:
    - total_emails, new_emails, high_priority, action_items_created
    - telegram_delivered (bool)
    - report_docx_url, report_pdf_url (optional)
    """
    data: Dict[str, Any] = {
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_emails": stats.get("total_emails", 0),
        "new_emails": stats.get("new_emails", 0),
        "high_priority": stats.get("high_priority", 0),
        "action_items_created": stats.get("action_items_created", 0),
        "telegram_delivered": stats.get("telegram_delivered", False),
    }
    if stats.get("report_docx_url"):
        data["report_docx_url"] = stats["report_docx_url"]
    if stats.get("report_pdf_url"):
        data["report_pdf_url"] = stats["report_pdf_url"]

    db.table("digest_runs").update(data).eq("id", run_id).execute()


def fail_run(run_id: str, error_message: str) -> None:
    """Mark a run as failed with an error message."""
    db.table("digest_runs").update({
        "status": "failed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "error_message": error_message,
    }).eq("id", run_id).execute()


def get_recent_runs(
    company_id: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Fetch recent digest runs for a company."""
    resp = db.table("digest_runs") \
        .select("*") \
        .eq("company_id", company_id) \
        .order("started_at", desc=True) \
        .limit(limit) \
        .execute()
    return resp.data or []


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single run by ID."""
    resp = db.table("digest_runs") \
        .select("*") \
        .eq("id", run_id) \
        .limit(1) \
        .execute()
    return resp.data[0] if resp.data else None
