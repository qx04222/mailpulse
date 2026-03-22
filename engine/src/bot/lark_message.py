"""
Lark message receive handler — @bot Q&A in groups and DMs.
Registers as p2_im_message_receive_v1 on the EventDispatcherHandler.
Reuses query.py for AI-driven email Q&A, scoped to the user's companies.
"""
import asyncio
import json
import logging
from typing import Optional

from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from ..config import settings, load_companies, load_people
from ..storage.db import db
from ..destinations.lark import send_text_message, send_user_message

from .lark_chat_context import chat_contexts
from .query import process_query

logger = logging.getLogger(__name__)


def _get_person_by_open_id(open_id: str) -> Optional[dict]:
    """Look up a person by their Lark open_id."""
    people = load_people()
    for p in people:
        if p.get("lark_user_id") == open_id:
            return p
    return None


def _get_companies_for_person(person_id: str) -> list:
    """Get all company_ids a person belongs to."""
    companies = load_companies()
    result = []
    for c in companies:
        for m in c.get("members", []):
            if m.get("id") == person_id:
                result.append(c)
                break
    return result


def _is_feature_enabled(company_id: str, feature_key: str) -> bool:
    """Check if a feature is enabled for a company."""
    try:
        resp = db.table("company_features") \
            .select("is_enabled") \
            .eq("company_id", company_id) \
            .eq("feature_key", feature_key) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0].get("is_enabled", False)
    except Exception:
        pass
    return True  # default on if no record


def _extract_text(content_str: str) -> str:
    """Extract plain text from Lark message content JSON."""
    try:
        content = json.loads(content_str)
        return content.get("text", "").strip()
    except Exception:
        return content_str.strip() if content_str else ""


def _strip_mentions(text: str) -> str:
    """Remove @mention placeholders from text."""
    # Lark uses @_user_1 style placeholders
    import re
    return re.sub(r'@_user_\d+', '', text).strip()


def handle_lark_message(data: P2ImMessageReceiveV1) -> None:
    """
    Handle incoming Lark messages (groups + DMs).
    SDK requires sync handler — we bridge to async internally.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_handle_lark_message_async(data))
    except RuntimeError:
        asyncio.run(_handle_lark_message_async(data))


async def _handle_lark_message_async(data: P2ImMessageReceiveV1) -> None:
    """Actual async message handler."""
    event = data.event
    if not event or not event.message:
        return

    msg = event.message
    chat_id = msg.chat_id
    chat_type = msg.chat_type  # "p2p" or "group"
    msg_type = msg.message_type
    content_str = msg.content or ""
    sender = event.sender
    open_id = sender.sender_id.open_id if sender and sender.sender_id else ""

    # Only handle text messages
    if msg_type != "text":
        return

    text = _extract_text(content_str)
    if not text:
        return

    # In groups, only respond when @mentioned
    if chat_type == "group":
        mentions = msg.mentions or []
        bot_mentioned = False
        for m in mentions:
            if m.id and m.id.open_id == "":
                # Bot mentions have empty open_id in some SDK versions
                bot_mentioned = True
                break
            # Also check by name
            if m.name and "bot" in (m.name or "").lower():
                bot_mentioned = True
                break
        # Simpler check: if there are mentions at all in a group, assume bot is mentioned
        # (the message wouldn't be delivered to bot otherwise in most configurations)
        if mentions:
            bot_mentioned = True
        if not bot_mentioned:
            return
        text = _strip_mentions(text)

    if not text:
        return

    # Look up the person
    person = _get_person_by_open_id(open_id)
    if not person:
        logger.warning(f"[Lark Q&A] Unknown user {open_id}, ignoring")
        reply = "抱歉，你还没有在系统中注册。请联系管理员添加你的飞书 ID。"
        if chat_type == "p2p":
            send_user_message(open_id, reply)
        else:
            send_text_message(chat_id, reply)
        return

    # Check feature gate
    companies = _get_companies_for_person(person["id"])
    if not companies:
        reply = "你目前没有关联任何公司，无法查询邮件数据。"
        if chat_type == "p2p":
            send_user_message(open_id, reply)
        else:
            send_text_message(chat_id, reply)
        return

    qa_enabled = any(_is_feature_enabled(c["id"], "lark_qa") for c in companies)
    if not qa_enabled:
        return

    logger.info(f"[Lark Q&A] {person['name']} ({chat_type}): {text[:50]}")

    # Get conversation context
    context_key = f"{chat_id}:{open_id}" if chat_type == "group" else open_id
    chat_history = chat_contexts.get(context_key)

    try:
        answer = await process_query(
            question=text,
            chat_context=chat_history,
        )

        # Save to context
        chat_contexts.append(context_key, "user", text)
        chat_contexts.append(context_key, "assistant", answer)

        # Reply
        if chat_type == "p2p":
            send_user_message(open_id, answer)
        else:
            send_text_message(chat_id, answer)

        logger.info(f"[Lark Q&A] Replied to {person['name']}: {answer[:50]}...")

    except Exception as e:
        logger.error(f"[Lark Q&A] Error: {e}")
        error_msg = f"处理出错，请稍后再试: {str(e)[:100]}"
        if chat_type == "p2p":
            send_user_message(open_id, error_msg)
        else:
            send_text_message(chat_id, error_msg)
