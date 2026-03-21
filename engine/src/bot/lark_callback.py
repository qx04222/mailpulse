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


def _result_card(title: str, status_text: str, color: str = "green") -> Dict:
    """Build a simple result card to replace the original."""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": color,
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": status_text},
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"MailPulse · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    }
                ],
            },
        ],
    }


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

        # Update card via API
        if message_id:
            update_card(message_id, _result_card(
                "✅ 已处理",
                f"**{user_name}** 已标记为已处理\n时间：{datetime.now().strftime('%m-%d %H:%M')}",
                "green",
            ))

        logger.info(f"[Lark Callback] Item {item_id} marked handled by {user_name}")

    elif action_type == "snooze":
        try:
            db.table("action_items").update({
                "dm_sent_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Callback] DB update error (snooze): {e}")

        if message_id:
            update_card(message_id, _result_card(
                "⏰ 已延后",
                f"**{user_name}** 选择稍后处理\n将在 24 小时后再次提醒",
                "yellow",
            ))

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
            update_card(message_id, _result_card(
                "🙋 已认领",
                f"**{user_name}** 已认领此任务",
                "blue",
            ))

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
