"""
Lark topic group manager — routes messages to the correct topic thread.

Topics:
  📊 report  — 每日/每周报告 + DOCX 附件
  🔴 urgent  — 紧急邮件通知 + 升级提醒
  ⚠️ alert   — SLA 违规 + 系统告警

In topic groups, each "topic" is a thread started by a root message.
Subsequent messages reply to that root to stay in the same thread.
"""
import logging
from typing import Optional, Dict, Any

from ..storage.db import db
from . import lark as lark_client

logger = logging.getLogger(__name__)

# Topic definitions: key → display title for the root message
TOPIC_TITLES = {
    "report": "📊 每日/每周报告",
    "urgent": "🔴 紧急待处理",
    "alert": "⚠️ 系统告警",
}


def get_topic_message_id(company_id: str, topic_key: str) -> Optional[str]:
    """Get the stored root message_id for a topic. Returns None if not created yet."""
    try:
        resp = db.table("lark_topics") \
            .select("message_id") \
            .eq("company_id", company_id) \
            .eq("topic_key", topic_key) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0]["message_id"]
    except Exception:
        pass
    return None


def _create_topic(company_id: str, chat_id: str, topic_key: str) -> Optional[str]:
    """Create a new topic by sending a root message. Returns the message_id."""
    title = TOPIC_TITLES.get(topic_key, topic_key)

    # Send a text message as the topic root
    import json as json_mod
    try:
        data = lark_client._api_call(
            "POST",
            "/open-apis/im/v1/messages?receive_id_type=chat_id",
            json_data={
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json_mod.dumps({"text": title}),
            },
        )
        message_id = data.get("data", {}).get("message_id")
        if message_id:
            # Store in DB
            db.table("lark_topics").upsert({
                "company_id": company_id,
                "chat_id": chat_id,
                "topic_key": topic_key,
                "message_id": message_id,
            }, on_conflict="company_id,topic_key").execute()
            logger.info(f"[Topics] Created topic '{topic_key}' for company {company_id}: {message_id}")
            return message_id
    except Exception as e:
        logger.error(f"[Topics] Error creating topic '{topic_key}': {e}")
    return None


def ensure_topic(company_id: str, chat_id: str, topic_key: str) -> Optional[str]:
    """Get or create a topic. Returns the root message_id."""
    msg_id = get_topic_message_id(company_id, topic_key)
    if msg_id:
        return msg_id
    return _create_topic(company_id, chat_id, topic_key)


def send_to_topic(
    company_id: str,
    chat_id: str,
    topic_key: str,
    card: Dict[str, Any],
) -> Optional[str]:
    """
    Send a card to the correct topic in a group.
    If the group is not in topic mode, falls back to normal send.
    Returns the message_id on success.
    """
    topic_msg_id = ensure_topic(company_id, chat_id, topic_key)

    if topic_msg_id:
        # Reply to the topic root
        msg_id = lark_client.reply_card_message(topic_msg_id, card)
        if msg_id:
            return msg_id
        # If reply fails (maybe topic was deleted), recreate
        logger.warning(f"[Topics] Reply failed, recreating topic '{topic_key}'")
        # Delete old topic record
        try:
            db.table("lark_topics") \
                .delete() \
                .eq("company_id", company_id) \
                .eq("topic_key", topic_key) \
                .execute()
        except Exception:
            pass
        # Create new and retry
        new_topic_id = _create_topic(company_id, chat_id, topic_key)
        if new_topic_id:
            return lark_client.reply_card_message(new_topic_id, card)

    # Fallback: send as normal message (group not in topic mode)
    return lark_client.send_card_message(chat_id, card)


def send_file_to_topic(
    company_id: str,
    chat_id: str,
    topic_key: str,
    file_bytes: bytes,
    filename: str,
) -> bool:
    """Send a file to a topic. Falls back to normal send."""
    topic_msg_id = ensure_topic(company_id, chat_id, topic_key)

    file_key = lark_client.upload_file(file_bytes, filename)
    if not file_key:
        return False

    if topic_msg_id:
        msg_id = lark_client.reply_file_message(topic_msg_id, file_key)
        if msg_id:
            return True

    # Fallback
    return lark_client.send_file_message(chat_id, file_key)
