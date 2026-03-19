"""
Tests for permission logic.
Uses plain dicts to match the new DB-based config (no more PersonConfig/CompanyConfig classes).
"""
from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# Permission functions (reference implementation for bot/auth.py)
# ---------------------------------------------------------------------------

def get_visible_companies(user: dict, all_companies: list, user_company_ids: list) -> list:
    """
    Determine which companies a user can see based on their role.
    - owner: all companies
    - manager/member: only companies they are linked to via company_members
    """
    if user["role"] == "owner":
        return all_companies
    return [c for c in all_companies if c["id"] in user_company_ids]


def can_view_email(user: dict, email_recipients: list, company_id: str, user_company_ids: list) -> bool:
    """
    Determine if a user can view a specific email.
    - owner: all emails
    - manager: all emails in their companies
    - member: only emails where they are in To/CC
    """
    if user["role"] == "owner":
        return True
    if company_id not in user_company_ids:
        return False
    if user["role"] == "manager":
        return True
    return user["email"].lower() in [r.lower() for r in email_recipients]


def is_authorized(user: Optional[dict]) -> bool:
    return user is not None


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

COMPANIES = [
    {"id": "c1", "name": "Arcview", "gmail_label": "Arcview"},
    {"id": "c2", "name": "TorqueMax", "gmail_label": "TorqueMax"},
    {"id": "c3", "name": "Arctrek", "gmail_label": "Arctrek"},
]

OWNER = {"id": "p1", "name": "Xin", "email": "xqi@arcview.ca", "role": "owner", "telegram_user_id": "111"}
OWNER_COMPANIES = ["c1", "c2", "c3"]

MANAGER = {"id": "p2", "name": "Nahrain", "email": "nahrain@arcview.ca", "role": "manager", "telegram_user_id": "222"}
MANAGER_COMPANIES = ["c1"]

MEMBER = {"id": "p3", "name": "Warren", "email": "warren@arctrek.ca", "role": "member", "telegram_user_id": "333"}
MEMBER_COMPANIES = ["c3"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOwnerPermissions:
    def test_owner_sees_all_companies(self):
        visible = get_visible_companies(OWNER, COMPANIES, OWNER_COMPANIES)
        assert len(visible) == 3

    def test_owner_can_view_any_email(self):
        assert can_view_email(OWNER, ["nahrain@arcview.ca"], "c1", OWNER_COMPANIES)

    def test_owner_can_view_email_in_any_company(self):
        assert can_view_email(OWNER, ["warren@arctrek.ca"], "c3", OWNER_COMPANIES)


class TestManagerPermissions:
    def test_manager_sees_only_assigned_companies(self):
        visible = get_visible_companies(MANAGER, COMPANIES, MANAGER_COMPANIES)
        assert len(visible) == 1
        assert visible[0]["name"] == "Arcview"

    def test_manager_can_view_emails_in_assigned_company(self):
        assert can_view_email(MANAGER, ["someone@arcview.ca"], "c1", MANAGER_COMPANIES)

    def test_manager_cannot_view_emails_in_other_company(self):
        assert not can_view_email(MANAGER, ["someone@arctrek.ca"], "c3", MANAGER_COMPANIES)


class TestMemberPermissions:
    def test_member_sees_only_assigned_companies(self):
        visible = get_visible_companies(MEMBER, COMPANIES, MEMBER_COMPANIES)
        assert len(visible) == 1
        assert visible[0]["name"] == "Arctrek"

    def test_member_can_view_own_emails(self):
        assert can_view_email(MEMBER, ["warren@arctrek.ca"], "c3", MEMBER_COMPANIES)

    def test_member_cannot_view_others_emails(self):
        assert not can_view_email(MEMBER, ["xqi@arcview.ca"], "c3", MEMBER_COMPANIES)

    def test_member_cannot_view_other_company_emails(self):
        assert not can_view_email(MEMBER, ["warren@arctrek.ca"], "c1", MEMBER_COMPANIES)


class TestUnregisteredUser:
    def test_unregistered_user_rejected(self):
        assert not is_authorized(None)

    def test_registered_user_accepted(self):
        assert is_authorized(OWNER)
        assert is_authorized(MANAGER)
        assert is_authorized(MEMBER)
