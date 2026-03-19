"""
AI-driven email query: fetch pre-indexed data from Supabase, instant responses.
Rewritten to use the new storage layer (emails table instead of email_summaries).
"""
import json
import re
from typing import Optional, Dict, Any, List

from anthropic import Anthropic
from ..config import settings, load_companies
from ..storage.emails import get_emails_by_company
from ..storage.action_items import get_pending_items

client = Anthropic(api_key=settings.anthropic_api_key)


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


INTENT_PROMPT = """Extract intent from user question, output JSON only:
{{
  "company": "company name or null",
  "person": "person name or null",
  "topic": "search keyword or null",
  "days": 7,
  "query_type": "general|new_clients|followup|progress|report"
}}

Known companies: {companies}
Known people: {members}

User question: {question}"""

ANSWER_PROMPT = """You are the email assistant for {company}. Answer the user's question
based on the following email data from the database. Be concise and professional.
Cite specific email details. If data is insufficient, say so.

## Emails (last {days} days, {count} total)
{email_context}

## Pending Action Items
{action_context}

## User Question
{question}"""

ANSWER_PROMPT_GENERAL = """You are a multi-company email assistant managing: {companies}.
Answer the user's question based on the following email data. Be concise and professional.

## Email Data
{email_context}

## User Question
{question}"""


async def extract_intent(question: str) -> dict:
    """Use Haiku for fast intent extraction."""
    companies = load_companies()
    company_names = ", ".join(c["name"] for c in companies)
    member_names = ", ".join(
        f"{m['name']}({c['name']})"
        for c in companies
        for m in c.get("members", [])
    )
    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=100,
        messages=[{"role": "user", "content": INTENT_PROMPT.format(
            companies=company_names,
            members=member_names,
            question=question,
        )}],
    )
    try:
        raw = resp.content[0].text
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        return json.loads(match.group() if match else raw)
    except Exception:
        return {"company": None, "person": None, "topic": None, "days": 7, "query_type": "general"}


def _format_emails_for_context(rows: List[Dict[str, Any]]) -> str:
    """Format email query results as AI context."""
    if not rows:
        return "(No email data found. You may need to run a digest first.)"
    lines = []
    for r in rows:
        score = r.get("score") or 0
        score_emoji = "!" if score >= 4 else "-" if score == 3 else " "
        action_flag = " [ACTION NEEDED]" if r.get("action_needed") else ""
        client_info = f" | client:{r['client_name']}" if r.get("client_name") else ""
        lines.append(
            f"{score_emoji} {r.get('sender_email', '')} | {r.get('subject', '')}\n"
            f"  {str(r.get('received_at', ''))[:10]} | "
            f"{r.get('one_line', '')}{client_info}{action_flag}"
        )
    return "\n---\n".join(lines)


def _format_actions_for_context(items: List[Dict[str, Any]]) -> str:
    """Format action items as AI context."""
    if not items:
        return "(no pending items)"
    lines = []
    for item in items:
        status = item.get("status", "pending")
        emoji = "!" if status == "overdue" else "-"
        lines.append(
            f"{emoji} [{status}] {item.get('title', '')}\n"
            f"   seen {item.get('seen_count', 1)} times"
        )
    return "\n".join(lines)


def _filter_rows(
    rows: List[Dict[str, Any]],
    person: Optional[str] = None,
    keyword: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Client-side filtering by person or keyword."""
    result = rows
    if person:
        p = person.lower()
        result = [
            r for r in result
            if p in (r.get("sender_email") or "").lower()
            or p in (r.get("sender_name") or "").lower()
            or p in (r.get("client_name") or "").lower()
        ]
    if keyword:
        k = keyword.lower()
        result = [
            r for r in result
            if k in (r.get("subject") or "").lower()
            or k in (r.get("body_preview") or "").lower()
            or k in (r.get("sender_email") or "").lower()
            or k in (r.get("client_name") or "").lower()
        ]
    return result


async def process_query(question: str, chat_context: Optional[List] = None) -> str:
    """
    Process user query: extract intent -> query Supabase -> AI answer.
    """
    # Step 1: Extract intent
    intent = await extract_intent(question)
    company_name = intent.get("company")
    person = intent.get("person")
    topic = intent.get("topic")
    days = min(intent.get("days", 7), 30)

    # Step 2: Query from Supabase
    company = find_company(company_name) if company_name else None
    companies = load_companies()

    if company:
        rows = get_emails_by_company(company["id"], days=days, limit=20)
        rows = _filter_rows(rows, person=person, keyword=topic)
    else:
        rows = []
        for c in companies:
            company_rows = get_emails_by_company(c["id"], days=days, limit=5)
            company_rows = _filter_rows(company_rows, person=person, keyword=topic)
            rows.extend(company_rows)

    # Step 3: Get action items
    action_context = ""
    if company:
        pending = get_pending_items(company["id"])
        action_context = _format_actions_for_context(pending)

    # Step 4: Generate answer
    email_context = _format_emails_for_context(rows)

    if company:
        prompt = ANSWER_PROMPT.format(
            company=company["name"],
            days=days,
            count=len(rows),
            email_context=email_context,
            action_context=action_context,
            question=question,
        )
    else:
        prompt = ANSWER_PROMPT_GENERAL.format(
            companies=", ".join(c["name"] for c in companies),
            email_context=email_context,
            question=question,
        )

    # Include conversation history
    messages = []
    if chat_context:
        for ctx in chat_context[-6:]:
            messages.append(ctx)
    messages.append({"role": "user", "content": prompt})

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=messages,
    )
    return resp.content[0].text
