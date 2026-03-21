"""
Lark card action callback handler.
Receives button click events from interactive cards.
Updates the card via API to show action result.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from aiohttp import web

from ..storage.db import db
from ..storage.action_items import mark_resolved
from ..destinations.lark import update_card

logger = logging.getLogger(__name__)


def _update_card_status(
    original_card: Dict,
    new_title: str,
    status_line: str,
    color: str,
) -> Dict:
    """
    Keep original card content but:
    1. Change header color + title to show status
    2. Remove action buttons
    3. Append status line at bottom
    """
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": new_title},
            "template": color,
        },
        "elements": [],
    }

    # Copy original elements, skip action buttons
    for elem in original_card.get("elements", []):
        if elem.get("tag") == "action":
            continue  # remove buttons
        card["elements"].append(elem)

    # Append status line
    card["elements"].append({"tag": "hr"})
    card["elements"].append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": status_line},
    })

    return card


def _get_original_card(message_id: str) -> Optional[Dict]:
    """Fetch the original card content from Lark API."""
    try:
        from ..destinations.lark import _api_call
        data = _api_call("GET", f"/open-apis/im/v1/messages/{message_id}")
        items = data.get("data", {}).get("items", [])
        if items:
            body = items[0].get("body", {})
            content = body.get("content", "{}")
            return json.loads(content) if isinstance(content, str) else content
    except Exception as e:
        logger.warning(f"[Lark Callback] Failed to fetch original card: {e}")
    return None


async def handle_card_action(request: web.Request) -> web.Response:
    """Handle Lark card action callback (button clicks)."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    # URL verification challenge
    if body.get("type") == "url_verification":
        return web.json_response({"challenge": body.get("challenge", "")})

    # Card action event
    if body.get("type") == "interactive":
        return await _process_card_action(body)

    return web.Response(status=200)


async def _process_card_action(body: Dict[str, Any]) -> web.Response:
    """Process a card button click."""
    action = body.get("action", {})
    value_str = action.get("value", "{}")
    try:
        value = json.loads(value_str) if isinstance(value_str, str) else value_str
    except Exception:
        value = {}

    action_type = value.get("action", "")
    item_id = value.get("item_id", "")
    open_id = body.get("open_id", "")
    user_name = _get_user_name(open_id)

    # Get the message_id so we can update the card
    message_id = body.get("open_message_id", "")

    if action_type == "handled":
        try:
            mark_resolved(item_id, note=f"Handled by {user_name}")
            db.table("action_items").update({
                "dm_acknowledged": True,
                "dm_acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Callback] DB update error (handled): {e}")

        # Update card: keep content, remove buttons, add status
        if message_id:
            original = _get_original_card(message_id)
            if original:
                updated = _update_card_status(
                    original,
                    f"✅ 已处理 | {original.get('header', {}).get('title', {}).get('content', '')[:40]}",
                    f"✅ **{user_name}** 已处理 · {datetime.now().strftime('%m-%d %H:%M')}",
                    "green",
                )
                update_card(message_id, updated)

        logger.info(f"[Lark Callback] Item {item_id} marked handled by {user_name}")

    elif action_type == "snooze":
        try:
            db.table("action_items").update({
                "dm_sent_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Callback] DB update error (snooze): {e}")

        if message_id:
            original = _get_original_card(message_id)
            if original:
                updated = _update_card_status(
                    original,
                    f"⏰ 稍后 | {original.get('header', {}).get('title', {}).get('content', '')[:40]}",
                    f"⏰ **{user_name}** 稍后处理 · 24h 后再提醒",
                    "yellow",
                )
                update_card(message_id, updated)

        logger.info(f"[Lark Callback] Item {item_id} snoozed by {user_name}")

    elif action_type == "claim":
        try:
            person_id = _get_person_id(open_id)
            if person_id:
                db.table("action_items").update({
                    "assigned_to_id": person_id,
                    "dm_acknowledged": True,
                    "dm_acknowledged_at": datetime.now(timezone.utc).isoformat(),
                    "status": "in_progress",
                }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Callback] DB update error (claim): {e}")

        if message_id:
            original = _get_original_card(message_id)
            if original:
                updated = _update_card_status(
                    original,
                    f"🙋 已认领 | {original.get('header', {}).get('title', {}).get('content', '')[:40]}",
                    f"🙋 **{user_name}** 已认领 · {datetime.now().strftime('%m-%d %H:%M')}",
                    "blue",
                )
                update_card(message_id, updated)

        logger.info(f"[Lark Callback] Item {item_id} claimed by {user_name}")

    # Return empty 200 — card update is done via API
    return web.Response(status=200)


def _get_user_name(open_id: str) -> str:
    """Get person name from open_id."""
    if not open_id:
        return "Unknown"
    try:
        resp = db.table("people") \
            .select("name") \
            .eq("lark_user_id", open_id) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0].get("name", "Unknown")
    except Exception:
        pass
    return "Unknown"


def _get_person_id(open_id: str) -> Optional[str]:
    """Get person UUID from open_id."""
    if not open_id:
        return None
    try:
        resp = db.table("people") \
            .select("id") \
            .eq("lark_user_id", open_id) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0].get("id")
    except Exception:
        pass
    return None


def create_callback_app() -> web.Application:
    """Create the aiohttp app for Lark callbacks."""
    app = web.Application()
    app.router.add_post("/lark/callback", handle_card_action)
    app.router.add_get("/health", lambda _: web.json_response({"status": "ok"}))
    return app
