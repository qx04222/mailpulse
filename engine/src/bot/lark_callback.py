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
from .ingest import handle_ingest

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

        # Auto-clean linked calendar event (fire-and-forget in background thread)
        try:
            import asyncio
            import threading
            from ..processors.calendar_sync import mark_calendar_event_done

            def _cleanup():
                try:
                    asyncio.run(mark_calendar_event_done(item_id))
                except Exception as ex:
                    logger.warning(f"[Lark Card] Calendar cleanup error: {ex}")

            threading.Thread(target=_cleanup, daemon=True).start()
        except Exception as e:
            logger.warning(f"[Lark Card] Calendar cleanup dispatch error: {e}")

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
                "status": "pending",
                "snoozed_at": datetime.now(timezone.utc).isoformat(),
                # Keep dm_sent_at intact so escalation safety net still works
            }).eq("id", item_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Card] DB error (snooze): {e}")

        logger.info(f"[Lark Card] Item {item_id} snoozed by {user_name}")
        card = _status_card(
            info["title"] or item_id,
            "⏰ 稍后处理",
            f"⏰ **{user_name}** 稍后处理 · 下次每日待办中再提醒",
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

    elif action_type == "calendar_accept":
        proposal_id = value.get("proposal_id", "")
        try:
            resp = db.table("calendar_proposals") \
                .select("*") \
                .eq("id", proposal_id) \
                .single() \
                .execute()
            proposal = resp.data
            if proposal:
                # Create Lark calendar event
                from ..destinations.lark_calendar import create_single_event
                event_id = create_single_event(
                    calendar_id=None,  # Use default company calendar
                    title=proposal.get("event_title", ""),
                    start_time=proposal.get("event_start", ""),
                    end_time=proposal.get("event_end", ""),
                    description=f"From email. Created by {user_name}",
                )
                db.table("calendar_proposals").update({
                    "status": "created",
                    "lark_event_id": event_id or "",
                }).eq("id", proposal_id).execute()

                card = _status_card(
                    proposal.get("event_title", ""),
                    "✅ 已添加日历",
                    f"✅ **{user_name}** 已创建日历事件",
                    "green", {"title": proposal.get("event_title", ""), "client": "", "company": ""},
                )
        except Exception as e:
            logger.warning(f"[Lark Card] Calendar accept error: {e}")
            card = _status_card("日历事件", "⚠️ 创建失败", f"创建失败: {str(e)[:50]}", "red",
                              {"title": "日历事件", "client": "", "company": ""})

    elif action_type == "calendar_reject":
        proposal_id = value.get("proposal_id", "")
        try:
            db.table("calendar_proposals").update({
                "status": "rejected",
            }).eq("id", proposal_id).execute()
        except Exception as e:
            logger.warning(f"[Lark Card] Calendar reject error: {e}")

        card = _status_card(
            "日历提案", "❌ 已忽略",
            f"❌ **{user_name}** 已忽略此日程提案",
            "grey", {"title": "日历提案", "client": "", "company": ""},
        )

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


# ── No-op handlers for events we subscribe to but don't need to process ──

def _handle_bot_p2p_chat_entered(data) -> None:
    """User opened the bot chat — safe to ignore."""
    logger.debug("[Lark] bot_p2p_chat_entered (ignored)")

def _handle_message_read(data) -> None:
    """User read a message — safe to ignore."""
    logger.debug("[Lark] message_read (ignored)")


# Build the SDK v2 event handler (card actions + message receive + no-op events)
_event_handler = lark.EventDispatcherHandler.builder(
    settings.lark_encrypt_key,
    settings.lark_verification_token,
    lark.LogLevel.DEBUG,
).register_p2_card_action_trigger(
    _handle_card_action
).register_p2_im_message_receive_v1(
    handle_lark_message
).register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
    _handle_bot_p2p_chat_entered
).register_p2_im_message_message_read_v1(
    _handle_message_read
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


async def _init_topics(request: web.Request) -> web.Response:
    """Initialize all topics for all active companies."""
    from ..config import load_companies
    from ..destinations.lark_topics import init_all_topics

    results = {}
    companies = load_companies()
    for company in companies:
        chat_id = company.get("lark_group_id")
        if not chat_id:
            continue
        topics = init_all_topics(company["id"], chat_id)
        results[company["name"]] = topics

    return web.json_response({"ok": True, "topics": results})


async def _broadcast_file(request: web.Request) -> web.Response:
    """
    Broadcast a pre-uploaded file to all active employees via DM.
    Usage: POST /broadcast-file with multipart form: file=<pdf>
    Also sends a text message before the file.
    """
    from ..config import load_people
    from ..destinations.lark import upload_file, send_user_file, send_user_message

    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != "file":
            return web.json_response({"error": "missing 'file' field"}, status=400)

        filename = field.filename or "document.pdf"
        file_bytes = bytes(await field.read())

        # Upload file — try direct upload, capture Lark error
        logger.info(f"[Broadcast] Uploading {filename} ({len(file_bytes)} bytes)")

        # Try upload with detailed error capture
        import httpx
        from ..destinations.lark import _get_tenant_access_token, _get_base_url
        upload_url = f"{_get_base_url()}/open-apis/im/v1/files"
        token = _get_tenant_access_token()
        upload_resp = httpx.post(
            upload_url,
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": "stream", "file_name": filename},
            files={"file": (filename, file_bytes)},
            timeout=60,
        )
        upload_data = upload_resp.json()
        if upload_data.get("code") != 0:
            return web.json_response({
                "error": "file upload failed",
                "lark_code": upload_data.get("code"),
                "lark_msg": upload_data.get("msg"),
            }, status=500)
        file_key = upload_data.get("data", {}).get("file_key")
        logger.info(f"[Broadcast] Upload OK: {file_key}")

        # Send to all active people with lark_user_id
        people = load_people()
        sent = 0
        failed = 0
        for person in people:
            open_id = person.get("lark_user_id")
            if not open_id or not person.get("is_active", True):
                continue
            # Send welcome + intro message
            welcome = (
                f"Hi {person.get('name', '')}，\n\n"
                f"欢迎使用 MailPulse AI 邮件助手！\n\n"
                f"从现在开始，我会帮你自动监控公司邮件、分析优先级、推送待办提醒。"
                f"你可以直接向我提问，比如「最近有什么需要处理的？」\n\n"
                f"附件是完整的功能使用指南，2 分钟即可了解所有功能。"
            )
            send_user_message(open_id, welcome)
            # Send file
            ok = send_user_file(open_id, file_key)
            if ok:
                sent += 1
            else:
                failed += 1

        logger.info(f"[Broadcast] File '{filename}' sent to {sent} people, {failed} failed")
        return web.json_response({"ok": True, "sent": sent, "failed": failed, "file_key": file_key})

    except Exception as e:
        logger.error(f"[Broadcast] Error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def _broadcast_welcome(request: web.Request) -> web.Response:
    """Send welcome message to all active employees via DM (text only, no file)."""
    from ..config import load_people
    from ..destinations.lark import send_user_message

    people = load_people()
    sent = 0
    for person in people:
        open_id = person.get("lark_user_id")
        if not open_id or not person.get("is_active", True):
            continue
        name = person.get("name", "")
        welcome = (
            f"Hi {name}，\n\n"
            f"欢迎使用 MailPulse AI 邮件助手！从现在开始，我会帮你：\n\n"
            f"-- 每天 9:30 推送待办提醒\n"
            f"-- 紧急邮件实时通知\n"
            f"-- 24h 未处理自动升级到群\n"
            f"-- 随时提问查邮件、找客户、看数据\n\n"
            f"你可以直接给我发消息试试，比如：\n"
            f"「最近有什么需要处理的？」\n"
            f"「帮我找关于报价的邮件」\n\n"
            f"详细功能指南请查看群公告中的 PDF 文件。"
        )
        ok = send_user_message(open_id, welcome)
        if ok:
            sent += 1

    logger.info(f"[Broadcast] Welcome sent to {sent} people")
    return web.json_response({"ok": True, "sent": sent})


async def _introduce(request: web.Request) -> web.Response:
    """Send bot self-introduction to groups and/or DMs."""
    from .introduce import send_introduce

    # Parse query params: ?group=1&dm=1 (both default to true)
    to_group = request.query.get("group", "1") == "1"
    to_dm = request.query.get("dm", "1") == "1"

    result = await send_introduce(to_group=to_group, to_dm=to_dm)
    return web.json_response({"ok": True, **result})


def create_callback_app() -> web.Application:
    import os
    app = web.Application()
    app.router.add_post("/lark/callback", handle_lark_callback)
    app.router.add_post("/ingest", handle_ingest)
    app.router.add_get("/health", lambda _: web.json_response({"status": "ok"}))
    app.router.add_get("/init-topics", _init_topics)
    app.router.add_post("/broadcast-file", _broadcast_file)
    app.router.add_get("/broadcast-welcome", _broadcast_welcome)
    app.router.add_get("/introduce", _introduce)
    if os.environ.get("ENABLE_TEST_ENDPOINTS"):
        app.router.add_get("/test-card", _send_test_card)
    return app
