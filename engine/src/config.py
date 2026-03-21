"""
Configuration: env vars via pydantic-settings, companies/people from database.
"""
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import Optional, List, Dict, Any


class Settings(BaseSettings):
    anthropic_api_key: str
    gmail_client_id: str
    gmail_client_secret: str
    gmail_refresh_token: str
    telegram_bot_token: str = ""
    telegram_enabled: bool = True
    supabase_url: str
    supabase_service_key: str
    digest_lookback_days: int = 3
    followup_overdue_days: int = 7

    # Lark integration
    lark_app_id: str = ""
    lark_app_secret: str = ""
    lark_base_url: str = "https://open.larksuite.com"
    lark_enabled: bool = True  # can disable Lark push globally

    class Config:
        env_file = ".env"


settings = Settings()


# -----------------------------------------------------------------
# Database-driven company/people config
# Loaded at startup and refreshable at runtime.
# -----------------------------------------------------------------

# Cache
_companies_cache: Optional[List[Dict[str, Any]]] = None
_people_cache: Optional[List[Dict[str, Any]]] = None
_team_emails_cache: Optional[List[str]] = None


def load_companies(force: bool = False) -> List[Dict[str, Any]]:
    """
    Load active companies from the database with their members.
    Returns list of company dicts, each with a 'members' key containing
    person records via the company_members join.
    """
    global _companies_cache
    if _companies_cache is not None and not force:
        return _companies_cache

    from .storage.db import db
    result = db.table("companies") \
        .select("*, company_members(person_id, people(*))") \
        .eq("is_active", True) \
        .execute()

    companies = []
    for row in (result.data or []):
        # Flatten members from the join
        members = []
        for cm in (row.get("company_members") or []):
            person = cm.get("people")
            if person and person.get("is_active", True):
                members.append(person)
        row["members"] = members
        companies.append(row)

    _companies_cache = companies
    return companies


def load_people(force: bool = False) -> List[Dict[str, Any]]:
    """Load all active people from the database."""
    global _people_cache
    if _people_cache is not None and not force:
        return _people_cache

    from .storage.db import db
    result = db.table("people") \
        .select("*") \
        .eq("is_active", True) \
        .execute()
    _people_cache = result.data or []
    return _people_cache


def get_team_emails(force: bool = False) -> List[str]:
    """
    Get list of all team member emails (lowercase).
    Used for direction detection (inbound vs outbound).
    """
    global _team_emails_cache
    if _team_emails_cache is not None and not force:
        return _team_emails_cache

    people = load_people(force=force)
    _team_emails_cache = [p["email"].lower() for p in people if p.get("email")]
    return _team_emails_cache


def get_company_by_id(company_id: str) -> Optional[Dict[str, Any]]:
    """Look up a company from cache by UUID."""
    companies = load_companies()
    for c in companies:
        if c["id"] == company_id:
            return c
    return None


def get_company_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Look up a company from cache by name."""
    companies = load_companies()
    for c in companies:
        if c["name"] == name:
            return c
    return None


def get_person_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Look up a person from cache by email."""
    people = load_people()
    email_lower = email.lower()
    for p in people:
        if p.get("email", "").lower() == email_lower:
            return p
    return None


def get_person_by_id(person_id: str) -> Optional[Dict[str, Any]]:
    """Look up a person from cache by UUID."""
    people = load_people()
    for p in people:
        if p["id"] == person_id:
            return p
    return None


def reload_config() -> None:
    """Force reload all cached config from the database."""
    global _companies_cache, _people_cache, _team_emails_cache
    _companies_cache = None
    _people_cache = None
    _team_emails_cache = None
    load_companies(force=True)
    load_people(force=True)
    get_team_emails(force=True)
