"""
Weekly personal performance report — sends every Saturday 9:30 AM.
Covers Saturday to Friday. Anomaly-first design.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from anthropic import AsyncAnthropic

from ..config import settings, load_companies, load_people
from ..storage.db import db
from ..destinations.lark import send_user_card
from ..destinations.lark_cards import build_weekly_report_card
from .helpers import is_feature_enabled, get_person_companies

logger = logging.getLogger(__name__)
client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def _get_period() -> tuple:
    """Get last Saturday 00:00 to last Friday 23:59 (UTC)."""
    now = datetime.now(timezone.utc)
    # Find last Saturday
    days_since_sat = (now.weekday() + 2) % 7  # Saturday = 0 offset
    if days_since_sat == 0:
        days_since_sat = 7  # If today is Saturday, go back to last Saturday
    end = now - timedelta(days=days_since_sat - 6)  # Last Friday
    end = end.replace(hour=23, minute=59, second=59)
    start = end - timedelta(days=6)
    start = start.replace(hour=0, minute=0, second=0)
    return start, end


def _get_person_stats(person_id: str, company_ids: List[str], start: datetime, end: datetime) -> Dict:
    """Gather stats for a person across their companies for the period."""
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    stats = {
        "emails_total": 0,
        "emails_inbound": 0,
        "emails_outbound": 0,
        "high_priority": 0,
        "action_items_created": 0,
        "action_items_resolved": 0,
        "top_clients": [],
        "pending_items": 0,
    }

    try:
        for cid in company_ids:
            # Emails assigned to this person
            resp = db.table("emails") \
                .select("direction, score, client_name", count="exact") \
                .eq("assigned_to_id", person_id) \
                .eq("company_id", cid) \
                .gte("received_at", start_iso) \
                .lte("received_at", end_iso) \
                .execute()
            emails = resp.data or []
            stats["emails_total"] += len(emails)
            stats["emails_inbound"] += sum(1 for e in emails if e.get("direction") == "inbound")
            stats["emails_outbound"] += sum(1 for e in emails if e.get("direction") == "outbound")
            stats["high_priority"] += sum(1 for e in emails if (e.get("score") or 0) >= 4)

            # Client frequency
            client_counts: Dict[str, int] = {}
            for e in emails:
                cn = e.get("client_name")
                if cn:
                    client_counts[cn] = client_counts.get(cn, 0) + 1
            for cn, count in sorted(client_counts.items(), key=lambda x: -x[1])[:3]:
                stats["top_clients"].append({"name": cn, "count": count})

            # Action items created this period
            resp = db.table("action_items") \
                .select("id", count="exact") \
                .eq("assigned_to_id", person_id) \
                .eq("company_id", cid) \
                .gte("created_at", start_iso) \
                .lte("created_at", end_iso) \
                .execute()
            stats["action_items_created"] += resp.count or 0

            # Action items resolved this period
            resp = db.table("action_items") \
                .select("id", count="exact") \
                .eq("assigned_to_id", person_id) \
                .eq("company_id", cid) \
                .eq("status", "resolved") \
                .gte("resolved_at", start_iso) \
                .lte("resolved_at", end_iso) \
                .execute()
            stats["action_items_resolved"] += resp.count or 0

            # Currently pending
            resp = db.table("action_items") \
                .select("id", count="exact") \
                .eq("assigned_to_id", person_id) \
                .eq("company_id", cid) \
                .in_("status", ["pending", "in_progress", "overdue"]) \
                .execute()
            stats["pending_items"] += resp.count or 0

    except Exception as e:
        logger.error(f"[Weekly] Stats error for {person_id}: {e}")

    return stats


async def _generate_highlights(person_name: str, stats: Dict, question: str = "") -> List[str]:
    """Use AI to generate 2-3 highlight bullets from stats."""
    if stats["emails_total"] == 0:
        return ["本周暂无邮件数据"]

    context = (
        f"员工：{person_name}\n"
        f"本周数据：\n"
        f"- 处理邮件 {stats['emails_total']} 封（收 {stats['emails_inbound']}，发 {stats['emails_outbound']}）\n"
        f"- 高优先 {stats['high_priority']} 封\n"
        f"- 任务创建 {stats['action_items_created']} 个，完成 {stats['action_items_resolved']} 个\n"
        f"- 当前待处理 {stats['pending_items']} 个\n"
        f"- 主要客户：{', '.join(c['name'] + '(' + str(c['count']) + '封)' for c in stats['top_clients'])}\n"
    )

    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content":
                f"根据以下数据，生成 2-3 条简短的周报亮点/异常。只输出要点，每条一行，不要标号。异常优先（如待处理积压多、高优先邮件多等）。\n\n{context}"
            }],
        )
        text = resp.content[0].text.strip()
        return [line.strip() for line in text.split("\n") if line.strip()][:3]
    except Exception as e:
        logger.error(f"[Weekly] AI highlights error: {e}")
        return [f"处理邮件 {stats['emails_total']} 封，完成任务 {stats['action_items_resolved']} 个"]


async def send_weekly_report(person: Dict[str, Any]) -> bool:
    """Generate and send weekly report to one person."""
    person_id = person["id"]
    open_id = person.get("lark_user_id")
    name = person.get("name", "")

    if not open_id:
        return False

    companies = get_person_companies(person_id)
    if not any(is_feature_enabled(c["id"], "weekly_report") for c in companies):
        return False

    company_ids = [c["id"] for c in companies]
    start, end = _get_period()
    period_str = f"{start.strftime('%m/%d')} - {end.strftime('%m/%d')}"

    stats = _get_person_stats(person_id, company_ids, start, end)
    highlights = await _generate_highlights(name, stats)

    card = build_weekly_report_card(
        person_name=name,
        period=period_str,
        stats=stats,
        highlights=highlights,
    )

    msg_id = send_user_card(open_id, card)
    if msg_id:
        # Record in weekly_reports table
        try:
            db.table("weekly_reports").insert({
                "company_id": company_ids[0] if company_ids else None,
                "person_id": person_id,
                "report_type": "personal",
                "period_start": start.strftime("%Y-%m-%d"),
                "period_end": end.strftime("%Y-%m-%d"),
                "content_json": stats,
                "lark_message_id": msg_id,
            }).execute()
        except Exception:
            pass
        logger.info(f"[Weekly] Sent to {name}: {stats['emails_total']} emails, {stats['action_items_resolved']} resolved")
        return True
    return False


async def send_all_weekly_reports():
    """Send weekly reports to all eligible people. Saturday 9:30 AM."""
    logger.info("[Weekly Report] Starting...")
    people = load_people()
    sent = 0

    for person in people:
        if not person.get("is_active", True) or not person.get("lark_user_id"):
            continue
        try:
            if await send_weekly_report(person):
                sent += 1
        except Exception as e:
            logger.error(f"[Weekly] Error for {person.get('name', '?')}: {e}")

    logger.info(f"[Weekly Report] Done: {sent} sent")
