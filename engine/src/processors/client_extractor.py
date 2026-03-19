"""
Client extractor — extracts and upserts client information from email data.
"""
import re
from typing import Optional, List, Dict, Any

from ..storage.clients import upsert_client, link_client_to_company, extract_client_from_email
from ..storage.emails import _parse_sender_email, _parse_sender_name


def process_email_for_client(
    sender: str,
    recipients_to: List[str],
    recipients_cc: List[str],
    direction: str,
    company_id: str,
    team_emails: List[str],
    assigned_to_id: Optional[str] = None,
    client_org: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Extract client info from an email, upsert the client record,
    and link to the company.

    Returns the client row if an external party was found, else None.
    """
    sender_email = _parse_sender_email(sender)
    sender_name = _parse_sender_name(sender)

    client_info = extract_client_from_email(
        sender_email=sender_email,
        sender_name=sender_name,
        recipients_to=recipients_to,
        recipients_cc=recipients_cc,
        direction=direction,
        team_emails=team_emails,
    )

    if not client_info:
        return None

    # Upsert the client record
    client = upsert_client(
        email=client_info["email"],
        name=client_info.get("name"),
        organization=client_org,
    )

    if not client or not client.get("id"):
        return None

    # Link client to company
    link_client_to_company(
        client_id=client["id"],
        company_id=company_id,
        primary_contact_id=assigned_to_id,
    )

    return client


def is_new_client(client: Dict[str, Any]) -> bool:
    """
    Determine if this client was just created (first_seen_at == last_activity_at
    within a small window, or no prior emails).
    """
    first = client.get("first_seen_at", "")
    last = client.get("last_activity_at", "")
    # If they were created in the same second, it's likely new
    if first and last:
        return first[:19] == last[:19]
    return False
