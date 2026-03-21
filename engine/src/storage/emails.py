"""
Email storage layer — maps to the `emails` table.
"""
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .db import db


def _parse_sender_email(sender: str) -> str:
    """Extract bare email from 'Name <email@example.com>' format."""
    match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', sender)
    return match.group().lower() if match else sender.lower()


def _parse_sender_name(sender: str) -> str:
    """Extract display name from 'Name <email@example.com>' format."""
    match = re.match(r'^"?([^"<]+)"?\s*<', sender)
    if match:
        return match.group(1).strip()
    return ""


def _get_all_company_domains() -> Dict[str, str]:
    """Get mapping of domain → company_id from all companies."""
    resp = db.table("companies").select("id, email_domains").eq("is_active", True).execute()
    domain_map = {}
    for c in (resp.data or []):
        for domain in (c.get("email_domains") or []):
            domain_map[domain.lower()] = c["id"]
    return domain_map


def _detect_direction_by_domain(sender_email: str, company_domains: Dict[str, str]) -> str:
    """Determine if email is inbound or outbound based on sender domain.
    If sender's domain matches any company domain → outbound (our employee sent it).
    Otherwise → inbound (client sent it).
    """
    domain = sender_email.split("@")[-1].lower() if "@" in sender_email else ""
    return "outbound" if domain in company_domains else "inbound"


def _detect_direction(sender_email: str, team_emails: List[str]) -> str:
    """Legacy fallback: detect direction by exact email match."""
    return "outbound" if sender_email in team_emails else "inbound"


def _find_company_by_domain(email_addr: str, company_domains: Dict[str, str]) -> Optional[str]:
    """Given an email, return the company_id if domain matches."""
    domain = email_addr.split("@")[-1].lower() if "@" in email_addr else ""
    return company_domains.get(domain)


def _detect_is_reply(subject: str, is_first_in_thread: bool) -> bool:
    """Detect if email is a reply based on subject prefix or thread position."""
    if not is_first_in_thread:
        return True
    prefix = subject.strip().lower()
    return prefix.startswith("re:") or prefix.startswith("fwd:") or prefix.startswith("fw:")


def detect_true_company(
    gmail_thread_id: str,
    current_company_id: str,
    recipients: List[str],
    company_domains: Dict[str, str],
) -> tuple:
    """
    Detect the true company for an email based on thread history and recipient domains.
    Returns (true_company_id, classification_source).

    Rules (priority order):
    1. Thread history: if this thread already exists under a different company → use that
    2. Recipient domains: if To/CC contains a domain belonging to another company → use that
    3. Fallback: use the current company from Gmail label
    """
    from .threads import get_thread_by_gmail_id

    # Rule 1: Thread history — most reliable
    existing_thread = get_thread_by_gmail_id(gmail_thread_id)
    if existing_thread and existing_thread["company_id"] != current_company_id:
        return existing_thread["company_id"], "thread_history"

    # Rule 2: Recipient domains — check To/CC for company domain hints
    for recip in recipients:
        recip_lower = recip.lower().strip()
        domain = recip_lower.split("@")[-1] if "@" in recip_lower else ""
        if domain in company_domains:
            detected = company_domains[domain]
            if detected != current_company_id:
                return detected, "recipient_domain"

    # Rule 3: Fallback
    return current_company_id, "gmail_label"


def upsert_email(
    gmail_message_id: str,
    gmail_thread_id: str,
    thread_id: Optional[str],
    company_id: str,
    subject: str,
    sender: str,
    recipients_to: List[str],
    recipients_cc: List[str],
    received_at: datetime,
    body_preview: str,
    body_full: str,
    direction: str,
    is_reply: bool,
    bucket: str = "inbox",
    client_id: Optional[str] = None,
    assigned_to_id: Optional[str] = None,
    score: Optional[int] = None,
    score_reason: Optional[str] = None,
    one_line: Optional[str] = None,
    action_needed: bool = False,
    client_name: Optional[str] = None,
    client_org: Optional[str] = None,
    project_address: Optional[str] = None,
    product_type: Optional[str] = None,
    run_id: Optional[str] = None,
    true_company_id: Optional[str] = None,
    bridged_from_company_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert or update an email record. Returns the row."""
    sender_email = _parse_sender_email(sender)
    sender_name = _parse_sender_name(sender)

    data = {
        "gmail_message_id": gmail_message_id,
        "gmail_thread_id": gmail_thread_id,
        "company_id": company_id,
        "subject": subject,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "recipients_to": recipients_to[:20],
        "recipients_cc": recipients_cc[:20],
        "received_at": received_at.isoformat(),
        "body_preview": (body_preview or "")[:500],
        "body_full": body_full,
        "direction": direction,
        "is_reply": is_reply,
        "bucket": bucket,
        "action_needed": action_needed,
    }

    # Optional foreign keys
    if thread_id:
        data["thread_id"] = thread_id
    if client_id:
        data["client_id"] = client_id
    if assigned_to_id:
        data["assigned_to_id"] = assigned_to_id
    if score is not None:
        data["score"] = score
    if score_reason:
        data["score_reason"] = score_reason
    if one_line:
        data["one_line"] = one_line
    if client_name:
        data["client_name"] = client_name
    if client_org:
        data["client_org"] = client_org
    if project_address:
        data["project_address"] = project_address
    if product_type:
        data["product_type"] = product_type
    if run_id:
        data["run_id"] = run_id
    if true_company_id:
        data["true_company_id"] = true_company_id
    if bridged_from_company_id:
        data["bridged_from_company_id"] = bridged_from_company_id

    resp = db.table("emails").upsert(
        data, on_conflict="gmail_message_id"
    ).execute()
    return resp.data[0] if resp.data else data


def update_email_scores(
    email_id: str,
    score: int,
    score_reason: str,
    one_line: str,
    action_needed: bool,
    client_name: Optional[str] = None,
    client_org: Optional[str] = None,
    project_address: Optional[str] = None,
    product_type: Optional[str] = None,
    assigned_to_id: Optional[str] = None,
) -> None:
    """Update AI-generated fields on an email record."""
    data: Dict[str, Any] = {
        "score": score,
        "score_reason": score_reason,
        "one_line": one_line,
        "action_needed": action_needed,
    }
    if client_name:
        data["client_name"] = client_name
    if client_org:
        data["client_org"] = client_org
    if project_address:
        data["project_address"] = project_address
    if product_type:
        data["product_type"] = product_type
    if assigned_to_id:
        data["assigned_to_id"] = assigned_to_id

    db.table("emails").update(data).eq("id", email_id).execute()


def get_emails_by_company(
    company_id: str,
    days: int = 7,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch recent emails for a company (for bot queries)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    resp = db.table("emails") \
        .select("*") \
        .eq("company_id", company_id) \
        .gte("received_at", cutoff) \
        .order("received_at", desc=True) \
        .limit(limit) \
        .execute()
    return resp.data or []


def get_emails_by_thread(thread_id: str) -> List[Dict[str, Any]]:
    """Fetch all emails in a thread, ordered by received_at."""
    resp = db.table("emails") \
        .select("*") \
        .eq("thread_id", thread_id) \
        .order("received_at") \
        .execute()
    return resp.data or []


def get_email_by_gmail_id(gmail_message_id: str) -> Optional[Dict[str, Any]]:
    """Look up a single email by Gmail message ID."""
    resp = db.table("emails") \
        .select("*") \
        .eq("gmail_message_id", gmail_message_id) \
        .limit(1) \
        .execute()
    return resp.data[0] if resp.data else None


def count_thread_emails(gmail_thread_id: str) -> int:
    """Count how many emails exist for a Gmail thread."""
    resp = db.table("emails") \
        .select("id", count="exact") \
        .eq("gmail_thread_id", gmail_thread_id) \
        .execute()
    return resp.count or 0
