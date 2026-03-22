"""
AI-driven email query: single-pass Sonnet for both intent extraction and answer.
Fetches pre-indexed data from Supabase, scoped to user's companies.
"""
import json
import re
from typing import Optional, Dict, Any, List

from anthropic import AsyncAnthropic
from ..config import settings, load_companies
from ..storage.emails import get_emails_by_company
from ..storage.action_items import get_pending_items

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def find_company(name: str) -> Optional[Dict[str, Any]]:
    """Fuzzy match a company by name. Returns company dict or None."""
    if not name:
        return None
    name_lower = name.lower().strip()
    companies = load_companies()
    for c in companies:
        if name_lower in c["name"].lower() or c["name"].lower() in name_lower:
            return c
    return None


UNIFIED_PROMPT = """你是 MailPulse 邮件助手，负责管理以下公司的邮件：{companies}。
请根据下方邮件数据回答用户问题。要求：
- 简洁专业，用中文回答
- 引用具体邮件信息（发件人、日期、主题）
- 如果数据不足，直接说明
- 不要编造不存在的邮件

## 邮件数据（最近 {days} 天，共 {count} 封）
{email_context}

## 待处理事项
{action_context}

## 用户问题
{question}"""


def _format_emails_for_context(rows: List[Dict[str, Any]]) -> str:
    """Format email query results as AI context."""
    if not rows:
        return "（暂无邮件数据）"
    lines = []
    for r in rows:
        score = r.get("score") or 0
        score_emoji = "🔴" if score >= 4 else "🟡" if score == 3 else "⚪"
        action_flag = " [需处理]" if r.get("action_needed") else ""
        client_info = f" | 客户:{r['client_name']}" if r.get("client_name") else ""
        lines.append(
            f"{score_emoji} {r.get('sender_email', '')} | {r.get('subject', '')}\n"
            f"  {str(r.get('received_at', ''))[:10]} | "
            f"{r.get('one_line', '')}{client_info}{action_flag}"
        )
    return "\n---\n".join(lines)


def _format_actions_for_context(items: List[Dict[str, Any]]) -> str:
    """Format action items as AI context."""
    if not items:
        return "（无待处理事项）"
    lines = []
    for item in items:
        status = item.get("status", "pending")
        emoji = "🔴" if status == "overdue" else "🟡"
        lines.append(
            f"{emoji} [{status}] {item.get('title', '')}\n"
            f"   已出现 {item.get('seen_count', 1)} 次"
        )
    return "\n".join(lines)


def _guess_company(question: str, companies: List[Dict]) -> Optional[Dict]:
    """Simple keyword match to detect company in question."""
    q = question.lower()
    for c in companies:
        if c["name"].lower() in q:
            return c
    return None


async def process_query(
    question: str,
    chat_context: Optional[List] = None,
    company_ids: Optional[List[str]] = None,
) -> str:
    """
    Single-pass query: fetch relevant emails → Sonnet answers directly.
    No separate intent extraction step.
    """
    companies = load_companies()

    # Scope to user's companies
    if company_ids is not None:
        companies = [c for c in companies if c["id"] in company_ids]

    if not companies:
        return "你目前没有关联的公司，无法查询邮件数据。"

    # Try to match a specific company from the question
    company = _guess_company(question, companies)
    days = 7

    # Fetch emails
    if company:
        rows = get_emails_by_company(company["id"], days=days, limit=30)
    else:
        rows = []
        per_company_limit = max(3, 20 // len(companies))
        for c in companies:
            rows.extend(get_emails_by_company(c["id"], days=days, limit=per_company_limit))

    # Get action items
    action_items = []
    target_companies = [company] if company else companies
    for c in target_companies:
        action_items.extend(get_pending_items(c["id"]))

    # Build prompt
    email_context = _format_emails_for_context(rows)
    action_context = _format_actions_for_context(action_items)

    prompt = UNIFIED_PROMPT.format(
        companies=", ".join(c["name"] for c in companies),
        days=days,
        count=len(rows),
        email_context=email_context,
        action_context=action_context,
        question=question,
    )

    # Build messages with conversation history
    messages = []
    if chat_context:
        for ctx in chat_context[-6:]:
            messages.append(ctx)
    messages.append({"role": "user", "content": prompt})

    resp = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=messages,
    )
    return resp.content[0].text
