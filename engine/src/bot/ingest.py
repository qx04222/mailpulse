"""
外部 SaaS 数据摄入端点 — POST /ingest
接收来自 ArcView、TorqueMax 等外部系统的事件，转化为 action_items 并触发 Lark 通知。
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from aiohttp import web

from ..storage.db import db
from ..storage.identity import resolve_person, get_person_lark_open_id
from ..storage.action_items import mark_resolved
from ..destinations.lark import send_user_card
from ..destinations.lark_cards import _header, _text, _hr, _note

logger = logging.getLogger(__name__)

# Valid event types
VALID_EVENT_TYPES = {
    "quote_created", "task_due", "task_completed",
    "project_update", "reminder", "invoice_created",
}

VALID_PRIORITIES = {"high", "medium", "low"}


async def handle_ingest(request: web.Request) -> web.Response:
    """
    POST /ingest
    Receive events from external SaaS systems, create/update action_items,
    and send Lark DM for high-priority items.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"[Ingest] Invalid JSON body: {e}")
        return web.json_response({"error": "invalid JSON body"}, status=400)

    source = body.get("source", "").strip()
    event_type = body.get("event_type", "").strip()
    actor = body.get("actor", "").strip()
    title = body.get("title", "").strip()
    priority = body.get("priority", "medium").strip()
    due_date = body.get("due_date")
    description = body.get("description", "")
    source_event_id = body.get("source_event_id", "").strip()
    source_url = body.get("source_url", "")
    metadata = body.get("metadata", {})

    # ── Validate required fields ──────────────────────────
    if not source or not event_type or not actor:
        return web.json_response(
            {"error": "missing required fields: source, event_type, actor"},
            status=400,
        )
    if not title and event_type != "task_completed":
        return web.json_response(
            {"error": "missing required field: title"},
            status=400,
        )
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    # ── 1. Resolve actor → person ─────────────────────────
    person = resolve_person(source, actor)
    if not person:
        # Fallback: try as gmail address
        person = resolve_person("gmail", actor)
    if not person:
        logger.warning(f"[Ingest] Actor not found: {source}:{actor}")
        return web.json_response(
            {"error": f"actor '{actor}' not found for source '{source}'. "
                      f"Register the identity first via the admin panel or API."},
            status=404,
        )

    person_id = person.get("id")
    person_name = person.get("name", "")
    logger.info(f"[Ingest] Resolved {source}:{actor} → {person_name} ({person_id})")

    # ── 2. Dedup check ────────────────────────────────────
    existing_item = None
    if source_event_id:
        existing_item = _find_by_source_event(source, source_event_id)

    # ── 3. Handle task_completed ──────────────────────────
    if event_type == "task_completed":
        if existing_item:
            mark_resolved(existing_item["id"], note=f"Completed via {source}")
            # Delete associated Lark calendar event if exists
            _delete_calendar_event(existing_item)
            logger.info(f"[Ingest] Marked resolved: {existing_item['id']}")
            return web.json_response({
                "ok": True,
                "action": "resolved",
                "action_item_id": existing_item["id"],
            })
        else:
            logger.info(f"[Ingest] task_completed but no matching action_item for {source}:{source_event_id}")
            return web.json_response({
                "ok": True,
                "action": "no_match",
                "message": "No matching action_item found to resolve.",
            })

    # ── 4. Get company_id from person ─────────────────────
    company_id = _get_person_company_id(person_id)

    # ── 5. Create or update action_item ───────────────────
    if existing_item:
        # Update existing
        updates: Dict[str, Any] = {
            "title": title[:200],
            "priority": priority,
            "assigned_to_id": person_id,
        }
        if description:
            updates["description"] = description
        if due_date:
            updates["due_date"] = due_date
        if source_url:
            updates["source_url"] = source_url

        try:
            db.table("action_items") \
                .update(updates) \
                .eq("id", existing_item["id"]) \
                .execute()
        except Exception as e:
            logger.error(f"[Ingest] Error updating action_item: {e}")

        action_item_id = existing_item["id"]
        action = "updated"
        logger.info(f"[Ingest] Updated action_item {action_item_id}")
    else:
        # Create new
        data: Dict[str, Any] = {
            "title": title[:200],
            "priority": priority,
            "status": "pending",
            "assigned_to_id": person_id,
            "source": source,
            "source_event_id": source_event_id or None,
            "source_url": source_url or None,
            "seen_count": 1,
        }
        if company_id:
            data["company_id"] = company_id
        if description:
            data["description"] = description
        if due_date:
            data["due_date"] = due_date

        try:
            resp = db.table("action_items").insert(data).execute()
            action_item_id = resp.data[0]["id"] if resp.data else None
        except Exception as e:
            logger.error(f"[Ingest] Error creating action_item: {e}")
            return web.json_response({"error": f"failed to create action_item: {e}"}, status=500)

        action = "created"
        logger.info(f"[Ingest] Created action_item {action_item_id}")

    # ── 6. Send Lark DM for high priority ─────────────────
    notification_sent = False
    if priority == "high" and action_item_id:
        open_id = get_person_lark_open_id(person_id)
        if open_id:
            card = _build_ingest_card(
                title=title,
                source=source,
                priority=priority,
                description=description,
                source_url=source_url,
                action_item_id=action_item_id,
            )
            msg_id = send_user_card(open_id, card)
            if msg_id:
                notification_sent = True
                try:
                    db.table("action_items").update({
                        "dm_sent_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", action_item_id).execute()
                except Exception:
                    pass
                logger.info(f"[Ingest] Sent Lark DM to {person_name} for {title[:40]}")
            else:
                logger.warning(f"[Ingest] Failed to send Lark DM to {person_name}")
        else:
            logger.info(f"[Ingest] No Lark open_id for {person_name}, skipping DM")

    return web.json_response({
        "ok": True,
        "action": action,
        "action_item_id": action_item_id,
        "notification_sent": notification_sent,
    })


# ══════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════

def _find_by_source_event(source: str, source_event_id: str) -> Optional[Dict[str, Any]]:
    """Find an existing action_item by source + source_event_id."""
    try:
        resp = db.table("action_items") \
            .select("*") \
            .eq("source", source) \
            .eq("source_event_id", source_event_id) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        logger.warning(f"[Ingest] Error querying action_items by source_event: {e}")
    return None


def _get_person_company_id(person_id: str) -> Optional[str]:
    """Get the first company_id for a person via company_members."""
    if not person_id:
        return None
    try:
        resp = db.table("company_members") \
            .select("company_id") \
            .eq("person_id", person_id) \
            .limit(1) \
            .execute()
        if resp.data:
            return resp.data[0].get("company_id")
    except Exception as e:
        logger.warning(f"[Ingest] Error querying company_members: {e}")
    return None


def _delete_calendar_event(action_item: Dict[str, Any]):
    """Delete the Lark calendar event associated with an action_item, if any."""
    event_id = action_item.get("lark_calendar_event_id")
    if not event_id:
        return
    try:
        from ..destinations.lark_calendar import _api_call
        _api_call(
            "DELETE",
            f"/open-apis/calendar/v4/calendars/primary/events/{event_id}",
        )
        logger.info(f"[Ingest] Deleted calendar event {event_id}")
    except Exception as e:
        logger.warning(f"[Ingest] Failed to delete calendar event {event_id}: {e}")


def _build_ingest_card(
    title: str,
    source: str,
    priority: str,
    description: str = "",
    source_url: str = "",
    action_item_id: str = "",
) -> Dict[str, Any]:
    """Build a Lark card for an ingested event notification."""
    template = "red" if priority == "high" else "yellow"
    priority_label = "🔴 紧急" if priority == "high" else "🟡 中"

    elements = []

    info = f"**{title}**\n"
    info += f"**来源：** {source}\n"
    info += f"**优先级：** {priority_label}\n"
    if description:
        info += f"\n{description[:300]}\n"
    if source_url:
        info += f"\n[🔗 查看详情]({source_url})"
    elements.append(_text(info))
    elements.append(_hr())

    # Action buttons
    if action_item_id:
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "✅ 已处理"},
                    "type": "primary",
                    "value": {"action": "handled", "item_id": action_item_id},
                },
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "⏰ 稍后处理"},
                    "type": "default",
                    "value": {"action": "snooze", "item_id": action_item_id},
                },
            ],
        })

    elements.append(_note(f"MailPulse · {source} · {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": _header(f"📋 {title[:50]}", template),
        "elements": elements,
    }
