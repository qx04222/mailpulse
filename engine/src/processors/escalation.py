"""
Escalation safety net.
Checks for DMs sent but not acknowledged within the threshold,
and escalates them to the group chat.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from ..storage.db import db
from ..destinations import lark as lark_client
from ..destinations.lark_cards import build_escalation_card

logger = logging.getLogger(__name__)

MAX_ESCALATIONS_PER_RUN = 5  # Avoid flooding the group


def check_unacknowledged_dms(
    company_id: str,
    company_name: str,
    lark_group_id: str,
    hours_threshold: int = 24,
) -> int:
    """
    Check for DMs sent > threshold hours ago that haven't been acknowledged.
    Escalates them to the group chat (oldest first, max 5 per run).
    Returns number of items escalated.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_threshold)).isoformat()

    try:
        resp = db.table("action_items") \
            .select("*, people(name, lark_user_id), clients(name)") \
            .eq("company_id", company_id) \
            .eq("dm_acknowledged", False) \
            .eq("escalated_to_group", False) \
            .not_.is_("dm_sent_at", "null") \
            .lt("dm_sent_at", cutoff) \
            .in_("status", ["pending", "in_progress", "overdue"]) \
            .order("dm_sent_at") \
            .limit(MAX_ESCALATIONS_PER_RUN) \
            .execute()
    except Exception as e:
        logger.error(f"[Escalation] Query error: {e}")
        return 0

    items = resp.data or []
    if not items:
        return 0

    escalated = 0
    for item in items:
        try:
            dm_sent = datetime.fromisoformat(
                item["dm_sent_at"].replace("Z", "+00:00")
            )
            hours_since = int(
                (datetime.now(timezone.utc) - dm_sent).total_seconds() / 3600
            )

            assignee_name = "未分配"
            if item.get("people"):
                assignee_name = item["people"].get("name", "未知")

            client_name = ""
            if item.get("clients"):
                client_name = item["clients"].get("name", "")

            card = build_escalation_card(
                title=item.get("title", "")[:60],
                assignee_name=assignee_name,
                hours_overdue=hours_since,
                priority=item.get("priority", "medium"),
                action_item_id=item["id"],
                client_name=client_name,
                company_name=company_name,
            )

            msg_id = lark_client.send_card_message(lark_group_id, card)
            if msg_id:
                db.table("action_items").update({
                    "escalated_to_group": True,
                    "escalated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", item["id"]).execute()
                escalated += 1

        except Exception as e:
            logger.error(f"[Escalation] Error escalating {item.get('id')}: {e}")

    if escalated:
        logger.info(f"[Escalation] {company_name}: {escalated} items escalated to group")
    return escalated
