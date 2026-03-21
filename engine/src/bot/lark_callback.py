"""
Lark card action callback handler.
Receives button click events from interactive cards.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from aiohttp import web

from ..storage.db import db
from ..storage.action_items import mark_resolved

logger = logging.getLogger(__name__)


async def handle_card_action(request: web.Request) -> web.Response:
    """Handle Lark card action callback (button clicks)."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    # URL verification challenge (required during bot setup)
    if body.get("type") == "url_verification":
        return web.json_response({"challenge": body.get("challenge", "")})

    # Card action event
    if body.get("type") == "interactive":
        return await _process_card_action(body)

    return web.json_response({"ok": True})


async def _process_card_action(body: Dict[str, Any]) -> web.Response:
    """Process a card button click."""
    try:
        action = body.get("action", {})
        value_str = action.get("value", "{}")
        value = json.loads(value_str) if isinstance(value_str, str) else value_str

        action_type = value.get("action", "")
        item_id = value.get("item_id", "")

        if not item_id:
            return web.json_response({"ok": True})

        # Get the user who clicked
        open_id = body.get("open_id", "")
        user_name = _get_user_name(open_id)

        if action_type == "handled":
            mark_resolved(item_id, note=f"Handled by {user_name}")
            db.table("action_items").update({
                "dm_acknowledged": True,
                "dm_acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()

            logger.info(f"[Lark Callback] Item {item_id} marked handled by {user_name}")

            # Return updated card
            return web.json_response({
                "toast": {"type": "success", "content": f"已标记为已处理 ✅"},
            })

        elif action_type == "snooze":
            # Reset dm_sent_at to now → gives another 24h before escalation
            db.table("action_items").update({
                "dm_sent_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()

            logger.info(f"[Lark Callback] Item {item_id} snoozed by {user_name}")

            return web.json_response({
                "toast": {"type": "info", "content": "已延后提醒 ⏰"},
            })

        elif action_type == "claim":
            # Someone in the group claims the escalated task
            person_id = _get_person_id(open_id)
            if person_id:
                db.table("action_items").update({
                    "assigned_to_id": person_id,
                    "dm_acknowledged": True,
                    "dm_acknowledged_at": datetime.now(timezone.utc).isoformat(),
                    "status": "in_progress",
                }).eq("id", item_id).execute()

            logger.info(f"[Lark Callback] Item {item_id} claimed by {user_name}")

            return web.json_response({
                "toast": {"type": "success", "content": f"{user_name} 已认领 🙋"},
            })

    except Exception as e:
        logger.error(f"[Lark Callback] Error: {e}")

    return web.json_response({"ok": True})


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
    # Health check
    app.router.add_get("/health", lambda _: web.json_response({"status": "ok"}))
    return app
