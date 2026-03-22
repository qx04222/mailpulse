"""
Shared helper functions used across bot modules.
Extracted to avoid duplication between lark_message.py and daily_todo.py.
"""
from typing import Optional, List, Dict

from ..config import load_companies, load_people
from ..storage.db import db


def is_feature_enabled(company_id: str, feature_key: str) -> bool:
    """Check if a feature is enabled for a company."""
    try:
        resp = db.table("company_features") \
            .select("is_enabled") \
            .eq("company_id", company_id) \
            .eq("feature_key", feature_key) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0].get("is_enabled", False)
    except Exception:
        pass
    return True  # default on if no record


def get_person_companies(person_id: str) -> List[Dict]:
    """Get companies this person belongs to."""
    companies = load_companies()
    result = []
    for c in companies:
        for m in c.get("members", []):
            if m.get("id") == person_id:
                result.append(c)
                break
    return result


def get_person_by_open_id(open_id: str) -> Optional[Dict]:
    """Look up a person by their Lark open_id."""
    people = load_people()
    for p in people:
        if p.get("lark_user_id") == open_id:
            return p
    return None
