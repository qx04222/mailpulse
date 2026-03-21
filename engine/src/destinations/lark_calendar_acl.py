"""
Lark Calendar ACL sync.
Automatically keeps calendar permissions in sync with company_members.
Each person only sees calendars for companies they belong to.
"""
from typing import Dict, List, Set

from .lark import _api_call


def sync_calendar_acl(
    companies: List[Dict],
    people: List[Dict],
    company_members: List[Dict],
) -> Dict[str, int]:
    """
    Sync calendar ACL for all companies based on company_members.

    Args:
        companies: list of company dicts with 'id', 'name', 'lark_calendar_id'
        people: list of person dicts with 'id', 'lark_user_id'
        company_members: list of {'person_id', 'company_id'} dicts

    Returns:
        dict with 'added' and 'removed' counts
    """
    stats = {"added": 0, "removed": 0, "errors": 0}

    # Build person_id -> lark_user_id map (only people with Lark accounts)
    person_lark_map: Dict[str, str] = {}
    for p in people:
        lark_id = p.get("lark_user_id")
        if lark_id:
            person_lark_map[p["id"]] = lark_id

    if not person_lark_map:
        print("[Calendar ACL] No people with Lark accounts, skipping")
        return stats

    # Build company_id -> set of lark_user_ids that should have access
    company_expected: Dict[str, Set[str]] = {}
    for cm in company_members:
        company_id = cm.get("company_id")
        person_id = cm.get("person_id")
        lark_id = person_lark_map.get(person_id)
        if not lark_id or not company_id:
            continue
        if company_id not in company_expected:
            company_expected[company_id] = set()
        company_expected[company_id].add(lark_id)

    for company in companies:
        calendar_id = company.get("lark_calendar_id")
        company_id = company.get("id")
        company_name = company.get("name", "")

        if not calendar_id:
            continue

        expected_users = company_expected.get(company_id, set())

        try:
            # Get current ACL
            current_acls = _list_acls(calendar_id)

            # Build current lark_user_id -> acl_id map (exclude owner/bot)
            current_users: Dict[str, str] = {}
            for acl in current_acls:
                scope = acl.get("scope", {})
                if scope.get("type") == "user":
                    user_id = scope.get("user_id", "")
                    acl_id = acl.get("acl_id", "")
                    # Skip the bot/owner
                    if acl.get("role") == "owner":
                        continue
                    if user_id and acl_id:
                        current_users[user_id] = acl_id

            # Add missing users
            to_add = expected_users - set(current_users.keys())
            for user_id in to_add:
                if _add_acl(calendar_id, user_id):
                    stats["added"] += 1
                else:
                    stats["errors"] += 1

            # Remove users who should no longer have access
            to_remove = set(current_users.keys()) - expected_users
            for user_id in to_remove:
                acl_id = current_users[user_id]
                if _remove_acl(calendar_id, acl_id):
                    stats["removed"] += 1
                else:
                    stats["errors"] += 1

            if to_add or to_remove:
                print(
                    f"[Calendar ACL] {company_name}: "
                    f"+{len(to_add)} -{len(to_remove)}"
                )

        except Exception as e:
            print(f"[Calendar ACL] Error syncing {company_name}: {e}")
            stats["errors"] += 1

    total = stats["added"] + stats["removed"]
    if total:
        print(f"[Calendar ACL] Sync done: +{stats['added']} -{stats['removed']} errors={stats['errors']}")
    return stats


def _list_acls(calendar_id: str) -> List[Dict]:
    """List all ACL entries for a calendar."""
    try:
        data = _api_call(
            "GET",
            f"/open-apis/calendar/v4/calendars/{calendar_id}/acls",
            params={"page_size": "50", "user_id_type": "open_id"},
        )
        return data.get("data", {}).get("acls", [])
    except Exception as e:
        print(f"[Calendar ACL] Error listing ACLs: {e}")
        return []


def _add_acl(calendar_id: str, user_id: str) -> bool:
    """Add a user as writer to a calendar."""
    try:
        _api_call(
            "POST",
            f"/open-apis/calendar/v4/calendars/{calendar_id}/acls",
            json_data={
                "role": "writer",
                "scope": {"type": "user", "user_id": user_id},
            },
        )
        return True
    except Exception as e:
        print(f"[Calendar ACL] Error adding {user_id}: {e}")
        return False


def _remove_acl(calendar_id: str, acl_id: str) -> bool:
    """Remove an ACL entry from a calendar."""
    try:
        _api_call(
            "DELETE",
            f"/open-apis/calendar/v4/calendars/{calendar_id}/acls/{acl_id}",
        )
        return True
    except Exception as e:
        print(f"[Calendar ACL] Error removing ACL {acl_id}: {e}")
        return False
