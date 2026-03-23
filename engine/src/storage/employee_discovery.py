"""
员工自动发现 v2：支持多邮箱合并。

查找顺序：
1. person_emails 表查邮箱 → 找到已有人员
2. people.email 查邮箱 → 兼容旧数据
3. 都没有 → 按用户名部分匹配同一个人（sage@arcview.ca 和 sage@torquemax.ca → 同一个 Sage）
4. 都匹配不到 → 自动创建新人员

公共邮箱检测：info@, quote@, support@, admin@, sales@ → person_type = 'shared_mailbox'
"""
import re
from typing import Optional, Dict, List, Any

from .db import db


# 内存缓存：email → person record
_person_cache = {}

# 公共邮箱前缀列表
SHARED_MAILBOX_PREFIXES = {
    "info", "quote", "quotes", "support", "admin", "sales",
    "service", "help", "contact", "office", "hr", "accounting",
    "billing", "noreply", "no-reply", "notification", "alert",
    "ip",  # Arcview specific
}


def clear_cache():
    _person_cache.clear()


def _parse_display_name(sender: str) -> str:
    """从 'Belle Ren <belle@arcview.ca>' 提取 'Belle Ren'"""
    match = re.match(r'^"?([^"<]+)"?\s*<', sender)
    if match:
        name = match.group(1).strip()
        # 过滤掉纯邮箱作为名字的情况
        if "@" not in name:
            return name
    return ""


def _is_shared_mailbox(email: str) -> bool:
    """检测是否是公共邮箱"""
    local = email.split("@")[0].lower() if "@" in email else email.lower()
    return local in SHARED_MAILBOX_PREFIXES


def _find_person_by_email(email_lower: str) -> Optional[Dict[str, Any]]:
    """先查 person_emails，再查 people.email"""
    # 1. 查 person_emails 表
    resp = db.table("person_emails") \
        .select("person_id, people(*)") \
        .eq("email", email_lower) \
        .limit(1) \
        .execute()
    if resp.data and resp.data[0].get("people"):
        return resp.data[0]["people"]

    # 2. 兜底查 people.email
    resp = db.table("people").select("*").eq("email", email_lower).limit(1).execute()
    if resp.data:
        return resp.data[0]

    return None


def _find_person_by_username(email: str) -> Optional[Dict[str, Any]]:
    """
    按用户名部分匹配：sage@arcview.ca → 找已有的 sage@torquemax.ca 的 Sage。
    只匹配真人（非公共邮箱），避免 info@a.ca 匹配 info@b.ca。
    """
    if _is_shared_mailbox(email):
        return None

    local = email.split("@")[0].lower() if "@" in email else ""
    if not local or len(local) < 2:
        return None

    # 查 person_emails 里有没有同用户名的
    resp = db.table("person_emails").select("person_id, email, people(*)").execute()
    for row in (resp.data or []):
        existing_local = row["email"].split("@")[0].lower() if "@" in row["email"] else ""
        if existing_local == local and row.get("people"):
            return row["people"]

    return None


def _add_email_to_person(person_id: str, email: str, company_id: Optional[str] = None):
    """给已有人员添加一个新邮箱"""
    try:
        email_lower = email.lower()
        # Check if already exists to avoid unnecessary upsert
        existing = db.table("person_emails") \
            .select("id") \
            .eq("email", email_lower) \
            .limit(1) \
            .execute()
        if existing.data:
            return  # already linked, skip

        data = {
            "person_id": person_id,
            "email": email_lower,
            "is_primary": False,
        }
        if company_id:
            data["company_id"] = company_id
        db.table("person_emails").insert(data).execute()
    except Exception as e:
        # Log but don't crash — duplicate email is expected race condition
        import logging
        logging.getLogger(__name__).debug(f"person_emails insert skip: {email} → {e}")


def get_or_create_employee(
    email: str,
    display_name: str,
    company_id: str,
) -> Dict[str, Any]:
    """
    查找或自动创建员工。支持多邮箱合并。
    """
    email_lower = email.lower().strip()

    # 缓存命中
    if email_lower in _person_cache:
        person = _person_cache[email_lower]
        _ensure_company_link(person.get("id"), company_id)
        return person

    # 1. 精确查找（person_emails 或 people.email）
    person = _find_person_by_email(email_lower)
    if person:
        _person_cache[email_lower] = person
        _ensure_company_link(person["id"], company_id)
        # 确保这个邮箱在 person_emails 里
        _add_email_to_person(person["id"], email_lower, company_id)
        return person

    # 2. 用户名匹配（合并同一人的不同公司邮箱）
    person = _find_person_by_username(email_lower)
    if person:
        # 找到同名人员，添加这个新邮箱
        _add_email_to_person(person["id"], email_lower, company_id)
        _ensure_company_link(person["id"], company_id)
        _person_cache[email_lower] = person
        print(f"  → Merged email {email_lower} → {person['name']}")
        return person

    # 3. 创建新人员
    is_shared = _is_shared_mailbox(email_lower)
    name = display_name or email_lower.split("@")[0].replace(".", " ").title()
    person_type = "shared_mailbox" if is_shared else "employee"

    new_person = {
        "name": name,
        "email": email_lower,
        "role": "member",
        "is_active": not is_shared,  # 公共邮箱默认不活跃
        "auto_discovered": True,
        "person_type": person_type,
    }
    resp = db.table("people").insert(new_person).execute()
    if resp.data:
        person = resp.data[0]
        _person_cache[email_lower] = person
        _ensure_company_link(person["id"], company_id)
        # 写入 person_emails
        _add_email_to_person(person["id"], email_lower, company_id)
        tag = " [shared]" if is_shared else ""
        print(f"  → Auto-discovered: {name} ({email_lower}){tag}")
        return person

    return {"id": None, "name": name, "email": email_lower}


def _ensure_company_link(person_id: Optional[str], company_id: str):
    """确保 person 和 company 的关联存在"""
    if not person_id or not company_id:
        return
    try:
        db.table("company_members").upsert(
            {"person_id": person_id, "company_id": company_id},
            on_conflict="company_id,person_id"
        ).execute()
    except Exception:
        pass


def discover_employees_from_email(
    sender_email: str,
    sender_raw: str,
    recipients: List[str],
    company_id: str,
    company_domains: Dict[str, str],
) -> Optional[str]:
    """
    从一封邮件中发现所有公司员工，返回 assigned_to_id。
    公共邮箱不会被设为 assigned_to。
    """
    sender_domain = sender_email.split("@")[-1].lower() if "@" in sender_email else ""
    sender_display = _parse_display_name(sender_raw)
    assigned_to_id = None

    # 发件人是我方员工？
    if sender_domain in company_domains:
        person = get_or_create_employee(sender_email, sender_display, company_id)
        # 公共邮箱不设为负责人
        if person.get("id") and not _is_shared_mailbox(sender_email):
            assigned_to_id = person.get("id")

    # 收件人中有我方员工？
    for recip in recipients:
        recip_lower = recip.lower().strip()
        recip_domain = recip_lower.split("@")[-1] if "@" in recip_lower else ""
        if recip_domain in company_domains:
            recip_company_id = company_domains.get(recip_domain, company_id)
            person = get_or_create_employee(recip_lower, "", recip_company_id)
            # inbound 时，assigned_to = 第一个非公共邮箱的收件员工
            if not assigned_to_id and person.get("id") and not _is_shared_mailbox(recip_lower):
                assigned_to_id = person.get("id")

    return assigned_to_id
