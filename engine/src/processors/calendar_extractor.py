"""
Calendar proposal extraction — detect meetings/events in email content.
Uses AI to extract datetime, location, attendees.
Only proposes (never auto-creates); user confirms via card button.
"""
import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from anthropic import AsyncAnthropic
from ..config import settings
from ..storage.db import db

logger = logging.getLogger(__name__)
client = AsyncAnthropic(api_key=settings.anthropic_api_key)

# Keywords that suggest a meeting/event in the email
MEETING_KEYWORDS = [
    "meeting", "call", "conference", "visit", "site visit",
    "appointment", "schedule", "zoom", "teams",
    "会议", "通话", "电话", "拜访", "现场", "约", "见面",
    "discuss at", "let's meet", "catch up",
]


def _has_meeting_signal(text: str) -> bool:
    """Quick keyword check before calling AI (save cost)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in MEETING_KEYWORDS)


EXTRACT_PROMPT = """从以下邮件内容中提取会议/日程信息。如果没有明确的会议安排，返回 null。

要求：
- 只提取有明确时间的会议/通话/拜访
- "下次再聊" 等模糊表述不算
- 输出 JSON 或 null

格式：
{{
  "title": "会议标题",
  "start": "2026-03-25T14:00:00",
  "end": "2026-03-25T15:00:00",
  "location": "地点或线上链接",
  "attendees": ["人名1", "人名2"]
}}

邮件主题：{subject}
邮件内容：
{body}"""


async def extract_calendar_proposal(
    email_row: Dict[str, Any],
    company_id: str,
) -> Optional[Dict]:
    """Extract meeting proposal from an email. Returns proposal dict or None."""
    subject = email_row.get("subject", "")
    body = email_row.get("body_full") or email_row.get("body_preview", "")

    # Quick keyword filter
    if not _has_meeting_signal(subject + " " + body):
        return None

    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
                subject=subject,
                body=body[:2000],
            )}],
        )
        raw = resp.content[0].text.strip()
        if raw.lower() == "null" or not raw.startswith("{"):
            return None

        proposal = json.loads(raw)
        if not proposal.get("title") or not proposal.get("start"):
            return None

        # Validate the proposed time is in the future
        try:
            start = datetime.fromisoformat(proposal["start"])
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if start < datetime.now(timezone.utc):
                return None  # Past event, skip
        except Exception:
            return None

        return proposal

    except Exception as e:
        logger.error(f"[Calendar] Extraction error: {e}")
        return None


def save_calendar_proposal(
    company_id: str,
    email_id: str,
    person_id: str,
    proposal: Dict,
) -> Optional[Dict]:
    """Save a calendar proposal to the database."""
    try:
        resp = db.table("calendar_proposals").insert({
            "company_id": company_id,
            "email_id": email_id,
            "person_id": person_id,
            "event_title": proposal["title"],
            "event_start": proposal.get("start"),
            "event_end": proposal.get("end"),
            "location": proposal.get("location", ""),
            "attendees": proposal.get("attendees", []),
            "raw_text": json.dumps(proposal, ensure_ascii=False),
            "status": "proposed",
        }).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.error(f"[Calendar] Save error: {e}")
        return None


async def process_emails_for_calendar(
    email_records: List[Dict],
    company_id: str,
) -> int:
    """Process scored emails for calendar proposals. Returns count of proposals created."""
    count = 0
    for rec in email_records:
        email_row = rec.get("email_row", {})
        score = email_row.get("score") or 0
        if score < 3:
            continue

        assigned_to_id = rec.get("assigned_to_id") or email_row.get("assigned_to_id")
        if not assigned_to_id:
            continue

        # Check if already proposed for this email
        email_id = email_row.get("id")
        if not email_id:
            continue
        try:
            existing = db.table("calendar_proposals") \
                .select("id") \
                .eq("email_id", email_id) \
                .limit(1) \
                .execute()
            if existing.data:
                continue
        except Exception:
            pass

        proposal = await extract_calendar_proposal(email_row, company_id)
        if proposal:
            saved = save_calendar_proposal(company_id, email_id, assigned_to_id, proposal)
            if saved:
                count += 1
                logger.info(f"[Calendar] Proposal: {proposal['title']} for {email_row.get('subject', '')[:30]}")

    return count
