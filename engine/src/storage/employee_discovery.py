"""
员工自动发现：从邮件中识别公司员工，自动创建 people 记录。

逻辑：
- 发件人域名匹配公司域名 → 这是我方员工
- 收件人域名匹配公司域名 → 这也是我方员工
- 如果 people 表里没有这个邮箱 → 自动创建
"""
import re
from typing import Optional, Dict, List, Any

from .db import db


# 内存缓存：email → person record
_person_cache = {}


def clear_cache():
    """清除缓存（测试或 reload 时调用）"""
    _person_cache.clear()


def _parse_display_name(sender: str) -> str:
    """从 'Belle Ren <belle@arcview.ca>' 提取 'Belle Ren'"""
    match = re.match(r'^"?([^"<]+)"?\s*<', sender)
    if match:
        return match.group(1).strip()
    return ""


def get_or_create_employee(
    email: str,
    display_name: str,
    company_id: str,
) -> Dict[str, Any]:
    """
    查找或自动创建员工。
    返回 people 记录（dict）。
    """
    email_lower = email.lower().strip()

    # 缓存命中
    if email_lower in _person_cache:
        return _person_cache[email_lower]

    # 查 DB
    resp = db.table("people").select("*").eq("email", email_lower).limit(1).execute()
    if resp.data:
        person = resp.data[0]
        _person_cache[email_lower] = person
        # 确保关联到公司
        _ensure_company_link(person["id"], company_id)
        return person

    # 自动创建
    name = display_name or email_lower.split("@")[0].replace(".", " ").title()
    new_person = {
        "name": name,
        "email": email_lower,
        "role": "member",
        "is_active": True,
        "auto_discovered": True,
    }
    resp = db.table("people").insert(new_person).execute()
    if resp.data:
        person = resp.data[0]
        _person_cache[email_lower] = person
        # 关联到公司
        _ensure_company_link(person["id"], company_id)
        print(f"  → Auto-discovered employee: {name} ({email_lower})")
        return person

    return {"id": None, "name": name, "email": email_lower}


def _ensure_company_link(person_id: str, company_id: str):
    """确保 person 和 company 的关联存在"""
    if not person_id or not company_id:
        return
    try:
        db.table("company_members").upsert(
            {"person_id": person_id, "company_id": company_id},
            on_conflict="company_id,person_id"
        ).execute()
    except Exception:
        pass  # 已存在则忽略


def discover_employees_from_email(
    sender_email: str,
    sender_raw: str,
    recipients: List[str],
    company_id: str,
    company_domains: Dict[str, str],
) -> Optional[str]:
    """
    从一封邮件中发现所有公司员工。
    返回 assigned_to_id（最相关的员工 ID）。

    规则：
    - 发件人域名匹配 → 这是发件员工，assigned_to = 此人
    - 收件人域名匹配 → 也是员工，创建但不设为 assigned_to
    - 如果是 inbound（客户发的），assigned_to = 收件人中第一个匹配的员工
    """
    sender_domain = sender_email.split("@")[-1].lower() if "@" in sender_email else ""
    sender_display = _parse_display_name(sender_raw)
    assigned_to_id = None

    # 发件人是我方员工？
    if sender_domain in company_domains:
        person = get_or_create_employee(sender_email, sender_display, company_id)
        assigned_to_id = person.get("id")

    # 收件人中有我方员工？
    for recip in recipients:
        recip_lower = recip.lower().strip()
        recip_domain = recip_lower.split("@")[-1] if "@" in recip_lower else ""
        if recip_domain in company_domains:
            person = get_or_create_employee(recip_lower, "", company_domains[recip_domain])
            # 如果发件人不是我方员工（inbound），assigned_to = 第一个收件员工
            if not assigned_to_id:
                assigned_to_id = person.get("id")

    return assigned_to_id
