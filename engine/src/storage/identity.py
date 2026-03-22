"""
统一身份解析：(provider, external_id) → person record.

查找顺序：
1. person_identities 精确匹配
2. 邮箱类 provider 回退：person_emails + people.email
3. 用户名部分匹配（复用 employee_discovery 的逻辑）
"""
import logging
from typing import Optional, Dict, Any

from .db import db

logger = logging.getLogger(__name__)

# provider 中属于邮箱类的前缀
_EMAIL_PROVIDERS = {"gmail", "zoho", "outlook", "email"}


def resolve_person(provider: str, external_id: str) -> Optional[Dict[str, Any]]:
    """
    Resolve (provider, external_id) → person record.
    1. Exact match in person_identities
    2. Fallback: if provider is email-like (gmail, zoho), check person_emails and people.email
    3. Fallback: username matching (existing logic from employee_discovery)
    Returns the full person dict or None.
    """
    if not provider or not external_id:
        return None

    ext_lower = external_id.strip().lower()

    # 1. person_identities 精确匹配
    person = _find_by_identity(provider, ext_lower)
    if person:
        return person

    # 2. 邮箱类 provider 回退
    if provider in _EMAIL_PROVIDERS and "@" in ext_lower:
        person = _find_by_email(ext_lower)
        if person:
            return person

    # 3. 用户名匹配（只对像邮箱的 external_id 有效）
    if "@" in ext_lower:
        person = _find_by_username(ext_lower)
        if person:
            return person

    return None


def register_identity(
    person_id: str,
    provider: str,
    external_id: str,
    display_name: str = "",
) -> bool:
    """Register a new identity for a person. Upsert to avoid duplicates."""
    if not person_id or not provider or not external_id:
        return False

    try:
        data: Dict[str, Any] = {
            "person_id": person_id,
            "provider": provider,
            "external_id": external_id.strip().lower(),
            "is_verified": True,
        }
        if display_name:
            data["display_name"] = display_name

        db.table("person_identities") \
            .upsert(data, on_conflict="provider,external_id") \
            .execute()
        logger.info(f"[Identity] Registered {provider}:{external_id} → person {person_id}")
        return True
    except Exception as e:
        logger.warning(f"[Identity] Failed to register {provider}:{external_id}: {e}")
        return False


def get_person_lark_open_id(person_id: str) -> Optional[str]:
    """
    Get the Lark open_id for a person (for sending DMs).
    Check person_identities where provider='lark' first,
    fallback to people.lark_user_id.
    """
    if not person_id:
        return None

    # 1. person_identities
    try:
        resp = db.table("person_identities") \
            .select("external_id") \
            .eq("person_id", person_id) \
            .eq("provider", "lark") \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0].get("external_id")
    except Exception as e:
        logger.warning(f"[Identity] Error querying lark identity: {e}")

    # 2. fallback: people.lark_user_id
    try:
        resp = db.table("people") \
            .select("lark_user_id") \
            .eq("id", person_id) \
            .limit(1) \
            .execute()
        if resp.data:
            lark_id = resp.data[0].get("lark_user_id")
            if lark_id:
                return lark_id
    except Exception as e:
        logger.warning(f"[Identity] Error querying people.lark_user_id: {e}")

    return None


# ══════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════

def _find_by_identity(provider: str, external_id: str) -> Optional[Dict[str, Any]]:
    """Exact lookup in person_identities → join people."""
    try:
        resp = db.table("person_identities") \
            .select("person_id, people(*)") \
            .eq("provider", provider) \
            .eq("external_id", external_id) \
            .limit(1) \
            .execute()
        if resp.data and resp.data[0].get("people"):
            return resp.data[0]["people"]
    except Exception as e:
        logger.warning(f"[Identity] Error querying person_identities: {e}")
    return None


def _find_by_email(email_lower: str) -> Optional[Dict[str, Any]]:
    """Fallback: check person_emails then people.email."""
    # person_emails
    try:
        resp = db.table("person_emails") \
            .select("person_id, people(*)") \
            .eq("email", email_lower) \
            .limit(1) \
            .execute()
        if resp.data and resp.data[0].get("people"):
            return resp.data[0]["people"]
    except Exception as e:
        logger.warning(f"[Identity] Error querying person_emails: {e}")

    # people.email
    try:
        resp = db.table("people") \
            .select("*") \
            .eq("email", email_lower) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        logger.warning(f"[Identity] Error querying people.email: {e}")

    return None


def _find_by_username(email: str) -> Optional[Dict[str, Any]]:
    """
    Username-part matching: xqi@arcview.ca → find existing xqi@*.
    Skip shared mailboxes (info@, support@, etc.).
    """
    from .employee_discovery import _is_shared_mailbox

    if _is_shared_mailbox(email):
        return None

    local = email.split("@")[0].lower() if "@" in email else ""
    if not local or len(local) < 2:
        return None

    try:
        resp = db.table("person_emails") \
            .select("person_id, email, people(*)") \
            .execute()
        for row in (resp.data or []):
            existing_local = row["email"].split("@")[0].lower() if "@" in row["email"] else ""
            if existing_local == local and row.get("people"):
                return row["people"]
    except Exception as e:
        logger.warning(f"[Identity] Error in username matching: {e}")

    return None
