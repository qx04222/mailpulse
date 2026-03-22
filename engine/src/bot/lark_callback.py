"""
Lark card action callback handler — uses lark-oapi SDK (v2 schema).
Handles button clicks (已处理/稍后处理/认领) from interactive cards.
Returns updated card to replace the original in-place.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import lark_oapi as lark
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
    P2CardActionTriggerResponse,
)
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from aiohttp import web

from ..config import settings
from ..storage.db import db
from ..storage.action_items import mark_resolved
from .lark_message import handle_lark_message

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# SDK Event Handler (v2 schema — P2CardActionTrigger)
# ══════════════════════════════════════════════════════════════

def _handle_card_action(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    """
    SDK v2 card action callback.
    data.event.action.value → Dict[str, str]
    data.event.operator.open_id → str
    """
    event = data.event
    value = event.action.value or {}
    action_type = value.get("action", "")
    item_id = value.get("item_id", "")
    open_id = event.operator.open_id if event.operator else ""
    user_name = _get_user_name(open_id)

    logger.info(f"[Lark Card] action={action_type} item={item_id} user={user_name} open_id={open_id}")

    info = _get_action_item_info(item_id)
    card = None

    if action_type == "handled":
        try:
            mark_resolved(item_id, note=f"Handled by {user_name}")
            db.table("action_items").update({
                "dm_acknowledged": True,
                "dm_acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Card] DB error (handled): {e}")

        logger.info(f"[Lark Card] Item {item_id} handled by {user_name}")
        card = _status_card(
            info["title"] or item_id,
            "✅ 已处理",
            f"✅ **{user_name}** 已处理 · {datetime.now().strftime('%m-%d %H:%M')}",
            "green", info, item_id=item_id,
        )

    elif action_type == "snooze":
        try:
            db.table("action_items").update({
                "status": "in_progress",
                "dm_sent_at": None,
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Card] DB error (snooze): {e}")

        logger.info(f"[Lark Card] Item {item_id} snoozed by {user_name}")
        card = _status_card(
            info["title"] or item_id,
            "⏰ 稍后处理",
            f"⏰ **{user_name}** 稍后处理 · 下次推送时再提醒",
            "yellow", info, item_id=item_id,
        )

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
            logger.warning(f"[Lark Card] DB error (claim): {e}")

        logger.info(f"[Lark Card] Item {item_id} claimed by {user_name}")
        card = _status_card(
            info["title"] or item_id,
            "🙋 已认领",
            f"🙋 **{user_name}** 已认领 · {datetime.now().strftime('%m-%d %H:%M')}",
            "blue", info, item_id=item_id,
        )

    elif action_type == "undo":
        try:
            db.table("action_items").update({
                "status": "pending",
                "dm_acknowledged": False,
                "dm_acknowledged_at": None,
                "resolved_at": None,
                "resolution_note": None,
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Card] DB error (undo): {e}")

        logger.info(f"[Lark Card] Item {item_id} undone by {user_name}")
        # Rebuild original card with action buttons
        card = _original_card_with_buttons(info, item_id)

    if card:
        return P2CardActionTriggerResponse({
            "toast": {"type": "success", "content": "操作成功"},
            "card": {
                "type": "raw",
                "data": card,
            },
        })

    return P2CardActionTriggerResponse({
        "toast": {"type": "info", "content": "收到"},
    })


# Build the SDK v2 event handler (card actions + message receive)
_event_handler = lark.EventDispatcherHandler.builder(
    settings.lark_encrypt_key,
    settings.lark_verification_token,
    lark.LogLevel.DEBUG,
).register_p2_card_action_trigger(
    _handle_card_action
).register_p2_im_message_receive_v1(
    handle_lark_message
).build()


# ══════════════════════════════════════════════════════════════
# aiohttp adapter
# ══════════════════════════════════════════════════════════════

async def handle_lark_callback(request: web.Request) -> web.Response:
    """aiohttp handler that delegates to the SDK EventDispatcherHandler."""
    body = await request.read()
    headers = dict(request.headers)

    raw_req = lark.RawRequest()
    raw_req.uri = str(request.url)
    raw_req.body = body
    raw_req.headers = headers

    logger.info(f"[Lark Callback] Received: {body[:300].decode('utf-8', errors='replace')}")

    raw_resp: lark.RawResponse = _event_handler.do(raw_req)

    logger.info(f"[Lark Callback] Response status={raw_resp.status_code} body={raw_resp.content[:300] if raw_resp.content else b''}")

    return web.Response(
        status=raw_resp.status_code,
        body=raw_resp.content,
        headers=raw_resp.headers or {"Content-Type": "application/json"},
    )


# ══════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════

def _get_action_item_info(item_id: str) -> Dict:
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
    item_id: str = "",
) -> Dict:
    elements = []
    summary = f"**{original_title}**"
    if info.get("client"):
        summary += f"\n客户：{info['client']}"
    if info.get("company"):
        summary += f"\n公司：{info['company']}"
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": summary}})
    elements.append({"tag": "hr"})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": status_detail}})

    # 撤销按钮
    if item_id:
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "↩️ 撤销"},
                    "type": "danger",
                    "value": {"action": "undo", "item_id": item_id},
                },
            ],
        })

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


def _original_card_with_buttons(info: Dict, item_id: str) -> Dict:
    """Rebuild the card with action buttons (for undo)."""
    elements = []
    title = info.get("title", "")
    summary = f"**{title}**"
    if info.get("client"):
        summary += f"\n客户：{info['client']}"
    if info.get("company"):
        summary += f"\n公司：{info['company']}"
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": summary}})
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "✅ 已处理"},
                "type": "primary",
                "value": {"action": "handled", "item_id": item_id},
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "⏰ 稍后处理"},
                "type": "default",
                "value": {"action": "snooze", "item_id": item_id},
            },
        ],
    })
    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": f"MailPulse · 已撤销 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
    ]})

    priority = info.get("priority", "medium")
    template = "red" if priority == "high" else "yellow"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📋 {title[:50]}"},
            "template": template,
        },
        "elements": elements,
    }


def _get_user_name(open_id: str) -> str:
    if not open_id:
        return "Unknown"
    try:
        resp = db.table("people").select("name").eq("lark_user_id", open_id).limit(1).execute()
        if resp.data:
            return resp.data[0].get("name", "Unknown")
    except Exception:
        pass
    return "Unknown"


def _get_person_id(open_id: str) -> Optional[str]:
    if not open_id:
        return None
    try:
        resp = db.table("people").select("id").eq("lark_user_id", open_id).limit(1).execute()
        if resp.data:
            return resp.data[0].get("id")
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════
# Test endpoint
# ══════════════════════════════════════════════════════════════

async def _send_test_card(request: web.Request) -> web.Response:
    from ..destinations.lark import send_user_card

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

        company_resp = db.table("companies").select("id").eq("is_active", True).limit(1).execute()
        if not company_resp.data:
            return web.json_response({"error": "no active company"}, status=404)
        company_id = company_resp.data[0]["id"]

        test_item = db.table("action_items").insert({
            "company_id": company_id,
            "title": "测试按钮卡片",
            "priority": "high",
            "status": "pending",
        }).execute()
        item_id = test_item.data[0]["id"]

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
                            "value": {"action": "handled", "item_id": item_id},
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "⏰ 稍后处理"},
                            "type": "default",
                            "value": {"action": "snooze", "item_id": item_id},
                        },
                    ],
                },
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": f"MailPulse Test · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                ]},
            ],
        }

        msg_id = send_user_card(open_id, card)
        logger.info(f"[Test] Sent test card to {name} ({open_id}), msg_id={msg_id}")
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
    import os
    app = web.Application()
    app.router.add_post("/lark/callback", handle_lark_callback)
    app.router.add_get("/health", lambda _: web.json_response({"status": "ok"}))
    if os.environ.get("ENABLE_TEST_ENDPOINTS"):
        app.router.add_get("/test-card", _send_test_card)
    return app
