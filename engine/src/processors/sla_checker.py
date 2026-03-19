"""
SLA checker — checks threads against SLA configs and generates breach events.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from ..storage.db import db
from ..storage.events import create_event


def _load_sla_config(company_id: str) -> Optional[Dict[str, Any]]:
    """Load active SLA config for a company."""
    resp = db.table("sla_configs") \
        .select("*") \
        .eq("company_id", company_id) \
        .eq("is_active", True) \
        .limit(1) \
        .execute()
    return resp.data[0] if resp.data else None


def check_sla_breaches(
    company_id: str,
    threads: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Check threads against SLA configs and generate sla_breach events.

    For threads in 'active' status (client sent last):
        Check if our response time exceeds first_response_hours.
    For threads in 'waiting_reply' status (we sent last):
        Check if client response time exceeds followup_response_hours.

    Returns list of created breach events.
    """
    sla = _load_sla_config(company_id)
    if not sla:
        return []

    first_response_hours = sla.get("first_response_hours", 24)
    followup_response_hours = sla.get("followup_response_hours", 48)
    escalate_after_hours = sla.get("escalate_after_hours", 72)
    escalate_to_id = sla.get("escalate_to_id")

    now = datetime.now(timezone.utc)
    breaches = []

    for thread in threads:
        status = thread.get("status")
        thread_id = thread.get("id")

        if status == "active":
            # Client sent last — check if WE are slow to respond
            last_inbound = thread.get("last_inbound_at")
            if not last_inbound:
                continue

            try:
                if isinstance(last_inbound, str):
                    last_inbound_dt = datetime.fromisoformat(
                        last_inbound.replace("Z", "+00:00")
                    )
                else:
                    last_inbound_dt = last_inbound

                if last_inbound_dt.tzinfo is None:
                    last_inbound_dt = last_inbound_dt.replace(tzinfo=timezone.utc)

                hours_elapsed = (now - last_inbound_dt).total_seconds() / 3600

                if hours_elapsed > first_response_hours:
                    severity = "critical" if hours_elapsed > escalate_after_hours else "warning"
                    event = create_event(
                        company_id=company_id,
                        event_type="sla_breach",
                        severity=severity,
                        title=f"SLA breach: no response in {int(hours_elapsed)}h",
                        description=(
                            f"Thread '{thread.get('subject', '')}' has been waiting "
                            f"for our response for {int(hours_elapsed)} hours "
                            f"(SLA: {first_response_hours}h)."
                        ),
                        thread_id=thread_id,
                        client_id=thread.get("client_id"),
                        person_id=escalate_to_id if severity == "critical" else thread.get("assigned_to_id"),
                        metadata={
                            "hours_elapsed": round(hours_elapsed, 1),
                            "sla_hours": first_response_hours,
                            "escalated": severity == "critical",
                        },
                    )
                    breaches.append(event)

            except (ValueError, TypeError):
                continue

        elif status == "waiting_reply":
            # We sent last — check if THEY are slow (informational only)
            last_outbound = thread.get("last_outbound_at")
            if not last_outbound:
                continue

            try:
                if isinstance(last_outbound, str):
                    last_outbound_dt = datetime.fromisoformat(
                        last_outbound.replace("Z", "+00:00")
                    )
                else:
                    last_outbound_dt = last_outbound

                if last_outbound_dt.tzinfo is None:
                    last_outbound_dt = last_outbound_dt.replace(tzinfo=timezone.utc)

                hours_elapsed = (now - last_outbound_dt).total_seconds() / 3600

                if hours_elapsed > followup_response_hours:
                    event = create_event(
                        company_id=company_id,
                        event_type="quote_followup",
                        severity="info",
                        title=f"Client hasn't replied in {int(hours_elapsed)}h",
                        description=(
                            f"Thread '{thread.get('subject', '')}' — we sent last "
                            f"message {int(hours_elapsed)} hours ago, no client reply yet."
                        ),
                        thread_id=thread_id,
                        client_id=thread.get("client_id"),
                        person_id=thread.get("assigned_to_id"),
                        metadata={
                            "hours_elapsed": round(hours_elapsed, 1),
                            "sla_hours": followup_response_hours,
                        },
                    )
                    breaches.append(event)

            except (ValueError, TypeError):
                continue

    return breaches
