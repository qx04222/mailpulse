"""
Client storage layer — maps to `clients` and `client_company_links` tables.
Clients are external contacts auto-extracted from email data.
"""
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .db import db


def upsert_client(
    email: str,
    name: Optional[str] = None,
    organization: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create or update a client by email (case-insensitive).
    Updates name/organization only if the new values are non-empty
    and the existing ones are empty.
    Returns the client row.
    """
    email_lower = email.strip().lower()

    # Check if client exists (case-insensitive via lower())
    existing = db.table("clients") \
        .select("*") \
        .ilike("email", email_lower) \
        .limit(1) \
        .execute()

    if existing.data:
        client = existing.data[0]
        updates: Dict[str, Any] = {
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
        }
        # Only update name/org if currently empty and we have new values
        if name and not client.get("name"):
            updates["name"] = name
        if organization and not client.get("organization"):
            updates["organization"] = organization

        resp = db.table("clients").update(updates).eq("id", client["id"]).execute()
        return resp.data[0] if resp.data else client
    else:
        data = {
            "email": email_lower,
            "name": name or "",
            "organization": organization or "",
            "status": "lead",
            "first_seen_at": datetime.now(timezone.utc).isoformat(),
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
        }
        resp = db.table("clients").insert(data).execute()
        return resp.data[0] if resp.data else data


def link_client_to_company(
    client_id: str,
    company_id: str,
    primary_contact_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create or update a client-company link.
    Increments email_count on each call.
    """
    existing = db.table("client_company_links") \
        .select("*") \
        .eq("client_id", client_id) \
        .eq("company_id", company_id) \
        .limit(1) \
        .execute()

    now = datetime.now(timezone.utc).isoformat()

    if existing.data:
        link = existing.data[0]
        updates: Dict[str, Any] = {
            "email_count": link["email_count"] + 1,
            "last_email_at": now,
        }
        if primary_contact_id and not link.get("primary_contact_id"):
            updates["primary_contact_id"] = primary_contact_id
        resp = db.table("client_company_links") \
            .update(updates) \
            .eq("id", link["id"]) \
            .execute()
        return resp.data[0] if resp.data else link
    else:
        data: Dict[str, Any] = {
            "client_id": client_id,
            "company_id": company_id,
            "email_count": 1,
            "last_email_at": now,
        }
        if primary_contact_id:
            data["primary_contact_id"] = primary_contact_id
        resp = db.table("client_company_links").insert(data).execute()
        return resp.data[0] if resp.data else data


def get_clients_by_company(company_id: str) -> List[Dict[str, Any]]:
    """Fetch all clients linked to a company."""
    resp = db.table("client_company_links") \
        .select("*, clients(*)") \
        .eq("company_id", company_id) \
        .order("last_email_at", desc=True) \
        .execute()
    return resp.data or []


def get_client_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Look up a client by email (case-insensitive)."""
    resp = db.table("clients") \
        .select("*") \
        .ilike("email", email.strip().lower()) \
        .limit(1) \
        .execute()
    return resp.data[0] if resp.data else None


def get_preferred_assignee(client_id: str, company_id: str) -> Optional[str]:
    """
    Find the most frequent assigned_to_id for this client's emails.
    Returns the person_id who most often handles this client, or None.
    """
    try:
        resp = db.table("emails") \
            .select("assigned_to_id") \
            .eq("client_id", client_id) \
            .eq("company_id", company_id) \
            .not_.is_("assigned_to_id", "null") \
            .order("received_at", desc=True) \
            .limit(20) \
            .execute()

        if not resp.data:
            return None

        # Count frequency
        counts: Dict[str, int] = {}
        for row in resp.data:
            aid = row.get("assigned_to_id")
            if aid:
                counts[aid] = counts.get(aid, 0) + 1

        if counts:
            return max(counts, key=counts.get)
    except Exception:
        pass
    return None


def extract_client_from_email(
    sender_email: str,
    sender_name: str,
    recipients_to: List[str],
    recipients_cc: List[str],
    direction: str,
    team_emails: List[str],
) -> Optional[Dict[str, str]]:
    """
    Given an email record, figure out who the external party is.
    - For inbound: sender is the client.
    - For outbound: first non-team recipient is the client.

    Returns {"email": ..., "name": ...} or None if no external party found.
    """
    team_set = {e.lower() for e in team_emails}

    if direction == "inbound":
        if sender_email.lower() not in team_set:
            return {"email": sender_email.lower(), "name": sender_name}
    else:
        # Outbound: find first non-team recipient
        all_recipients = list(recipients_to) + list(recipients_cc)
        for addr in all_recipients:
            addr_lower = addr.strip().lower()
            # Extract email from "Name <email>" if needed
            match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', addr_lower)
            clean_email = match.group() if match else addr_lower
            if clean_email not in team_set:
                return {"email": clean_email, "name": ""}

    return None
