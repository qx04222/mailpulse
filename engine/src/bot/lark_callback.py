"""
Lark card action callback handler.
Receives button click events from interactive cards.
Returns updated card in callback response so Lark replaces it in-place.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from aiohttp import web

from ..storage.db import db
from ..storage.action_items import mark_resolved

logger = logging.getLogger(__name__)


def _get_action_item_info(item_id: str) -> Dict:
    """Get action item details for building status card."""
    try:
        resp = db.table("action_items") \
            .select("title, priority, companies(name), clients(name)") \
            .eq("id", item_id) \
            .limit(1) \
            .execute()
        if resp.data:
            row = resp.data[0]
            return {
                "title": row.get("title", ""),
                "priority": row.get("priority", "medium"),
                "company": row.get("companies", {}).get("name", "") if row.get("companies") else "",
                "client": row.get("clients", {}).get("name", "") if row.get("clients") else "",
            }
    except Exception:
        pass
    return {"title": item_id, "priority": "medium", "company": "", "client": ""}


def _status_card(
    original_title: str,
    status_label: str,
    status_detail: str,
    color: str,
    info: Dict,
) -> Dict:
    """Build a status card that shows what was done."""
    elements = []

    # Original info summary
    summary = f"**{original_title}**"
    if info.get("client"):
        summary += f"\n客户：{info['client']}"
    if info.get("company"):
        summary += f"\n公司：{info['company']}"
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": summary}})

    elements.append({"tag": "hr"})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": status_detail}})
    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": f"MailPulse · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
    ]})

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"{status_label} | {original_title[:40]}"},
            "template": color,
        },
        "elements": elements,
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
    """Process a card button click. Returns updated card in response."""
    logger.info(f"[Lark Callback] Received body: {json.dumps(body, ensure_ascii=False)[:500]}")

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

    logger.info(f"[Lark Callback] action={action_type} item={item_id} user={user_name}")

    card = None  # The updated card to return

    if action_type == "handled":
        try:
            mark_resolved(item_id, note=f"Handled by {user_name}")
            db.table("action_items").update({
                "dm_acknowledged": True,
                "dm_acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Callback] DB update error (handled): {e}")

        info = _get_action_item_info(item_id)
        card = _status_card(
            info["title"] or item_id,
            "✅ 已处理",
            f"✅ **{user_name}** 已处理 · {datetime.now().strftime('%m-%d %H:%M')}",
            "green", info,
        )
        logger.info(f"[Lark Callback] Item {item_id} marked handled by {user_name}")

    elif action_type == "snooze":
        try:
            db.table("action_items").update({
                "dm_sent_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Callback] DB update error (snooze): {e}")

        info = _get_action_item_info(item_id)
        card = _status_card(
            info["title"] or item_id,
            "⏰ 稍后处理",
            f"⏰ **{user_name}** 稍后处理 · 24h 后再提醒",
            "yellow", info,
        )
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

        info = _get_action_item_info(item_id)
        card = _status_card(
            info["title"] or item_id,
            "🙋 已认领",
            f"🙋 **{user_name}** 已认领 · {datetime.now().strftime('%m-%d %H:%M')}",
            "blue", info,
        )
        logger.info(f"[Lark Callback] Item {item_id} claimed by {user_name}")

    # Return the updated card in response — Lark replaces the card in-place
    if card:
        logger.info(f"[Lark Callback] Returning updated card")
        return web.json_response({"card": card})

    return web.json_response({})


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


async def _send_test_card(request: web.Request) -> web.Response:
    """Send a test card with action buttons to verify callback flow."""
    import json as json_mod
    from ..destinations.lark import send_user_card

    # Find first person with lark_user_id
    try:
        resp = db.table("people") \
            .select("id, name, lark_user_id") \
            .not_.is_("lark_user_id", "null") \
            .limit(1) \
            .execute()
        if not resp.data:
            return web.json_response({"error": "no user with lark_user_id"}, status=404)

        person = resp.data[0]
        open_id = person["lark_user_id"]
        name = person.get("name", "Test User")

        # Create a test action_item
        from datetime import datetime, timezone
        test_item = db.table("action_items").insert({
            "title": "测试按钮卡片",
            "priority": "high",
            "status": "pending",
        }).execute()
        item_id = test_item.data[0]["id"]

        # Build test card with buttons
        card = {
            "config": {"wide_screen_mode": True, "update_multi": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🧪 测试卡片 | 点击按钮验证"},
                "template": "purple",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content":
                    f"**这是一张测试卡片**\n\n"
                    f"发送给：{name}\n"
                    f"Item ID：{item_id}\n\n"
                    f"请点击下方按钮测试回调功能："}},
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "✅ 已处理"},
                            "type": "primary",
                            "value": json_mod.dumps({"action": "handled", "item_id": item_id}),
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "⏰ 稍后处理"},
                            "type": "default",
                            "value": json_mod.dumps({"action": "snooze", "item_id": item_id}),
                        },
                    ],
                },
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": f"MailPulse Test · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                ]},
            ],
        }

        msg_id = send_user_card(open_id, card)
        logger.info(f"[Test] Sent test card to {name} ({open_id}), message_id={msg_id}")
        return web.json_response({
            "ok": True,
            "sent_to": name,
            "open_id": open_id,
            "message_id": msg_id,
            "item_id": item_id,
        })
    except Exception as e:
        logger.error(f"[Test] Error: {e}")
        return web.json_response({"error": str(e)}, status=500)


def create_callback_app() -> web.Application:
    """Create the aiohttp app for Lark callbacks."""
    app = web.Application()
    app.router.add_post("/lark/callback", handle_card_action)
    app.router.add_get("/health", lambda _: web.json_response({"status": "ok"}))
    app.router.add_get("/test-card", _send_test_card)
    return app
