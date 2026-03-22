"""
AI-driven email query: single-pass Sonnet for both intent extraction and answer.
Fetches pre-indexed data from Supabase, scoped to user's companies.
Supports keyword search + time range extraction from natural language.
"""
import re
from typing import Optional, Dict, Any, List

from anthropic import AsyncAnthropic
from ..config import settings, load_companies
from ..storage.emails import get_emails_by_company, search_emails
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


def _extract_time_range(question: str) -> int:
    """Extract time range from question. Returns days."""
    q = question.lower()
    if any(w in q for w in ["上个月", "一个月", "30天", "last month"]):
        return 30
    if any(w in q for w in ["两周", "半个月", "15天", "two weeks"]):
        return 14
    if any(w in q for w in ["上周", "一周", "last week", "7天"]):
        return 7
    if any(w in q for w in ["今天", "today"]):
        return 1
    if any(w in q for w in ["昨天", "yesterday"]):
        return 2
    if any(w in q for w in ["这周", "本周", "this week"]):
        return 7
    if any(w in q for w in ["最近", "近期"]):
        return 14
    # Default
    return 7


def _extract_search_keyword(question: str, companies: List[Dict]) -> Optional[str]:
    """Extract a search keyword from the question (names, topics, etc.)."""
    q = question
    # Remove common question words
    noise = ["帮我找", "帮我查", "搜索", "找一下", "查一下", "关于", "有没有",
             "最近", "上周", "上个月", "今天", "昨天", "的邮件", "邮件",
             "什么", "怎么样", "如何", "是否", "有", "吗", "呢", "了",
             "需要处理", "待处理", "高优", "紧急"]
    for n in noise:
        q = q.replace(n, " ")
    # Remove company names
    for c in companies:
        q = q.replace(c["name"], " ").replace(c["name"].lower(), " ")
    q = q.strip()
    # If anything meaningful remains, use it as search keyword
    if len(q) >= 2:
        return q
    return None


async def process_query(
    question: str,
    chat_context: Optional[List] = None,
    company_ids: Optional[List[str]] = None,
) -> str:
    """
    Single-pass query: fetch relevant emails → Sonnet answers directly.
    Supports keyword search and wider time windows.
    """
    companies = load_companies()

    # Scope to user's companies
    if company_ids is not None:
        companies = [c for c in companies if c["id"] in company_ids]

    if not companies:
        return "你目前没有关联的公司，无法查询邮件数据。"

    # Try to match a specific company from the question
    company = _guess_company(question, companies)
    days = _extract_time_range(question)
    keyword = _extract_search_keyword(question, companies)

    # Fetch emails — try keyword search first, fallback to date-based
    rows = []
    scoped_ids = [company["id"]] if company else [c["id"] for c in companies]

    if keyword:
        rows = search_emails(
            keyword=keyword,
            company_ids=scoped_ids,
            days=max(days, 30),  # search wider for keyword queries
            limit=30,
        )

    # If keyword search got few results, supplement with date-based fetch
    if len(rows) < 10:
        if company:
            date_rows = get_emails_by_company(company["id"], days=days, limit=30)
        else:
            date_rows = []
            per_limit = max(3, 20 // len(companies))
            for c in companies:
                date_rows.extend(get_emails_by_company(c["id"], days=days, limit=per_limit))
        # Merge without duplicates
        existing_ids = {r.get("id") for r in rows}
        for r in date_rows:
            if r.get("id") not in existing_ids:
                rows.append(r)
                if len(rows) >= 40:
                    break

    # Get action items
    action_items = []
    for c in ([company] if company else companies):
        action_items.extend(get_pending_items(c["id"]))

    # Build prompt
    email_context = _format_emails_for_context(rows[:40])
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
