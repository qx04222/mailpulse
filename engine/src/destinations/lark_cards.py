"""
Lark 消息卡片模板。
所有卡片中文输出，按钮只保留实用操作。
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


def _header(title: str, template: str = "blue") -> Dict:
    return {
        "title": {"tag": "plain_text", "content": title},
        "template": template,
    }


def _text(content: str) -> Dict:
    return {"tag": "div", "text": {"tag": "lark_md", "content": content}}


def _hr() -> Dict:
    return {"tag": "hr"}


def _note(text: str) -> Dict:
    return {"tag": "note", "elements": [{"tag": "plain_text", "content": text}]}


# ══════════════════════════════════════════════════════════════
# 1. 公司周报卡片
# ══════════════════════════════════════════════════════════════

def build_daily_digest_card(
    company_name: str,
    date_range: str,
    total_emails: int,
    total_threads: int,
    high_priority: int,
    actionable: int,
    low_priority: int,
    group_reports: Dict[str, str],
    top_actions: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """公司周报摘要卡片"""
    elements = []

    # 概览
    elements.append(_text(
        f"📊 **{company_name}** · {date_range}\n\n"
        f"📧 邮件总数：**{total_emails}**　|　💬 对话线程：**{total_threads}**\n"
        f"🔴 需立即处理：**{high_priority}**　|　🟡 需关注：**{actionable}**　|　⚪ 低优先：**{low_priority}**"
    ))
    elements.append(_hr())

    # 各负责人报告
    for assignee, report in group_reports.items():
        truncated = report[:800]
        if len(report) > 800:
            truncated += "\n..."
        elements.append(_text(truncated))
        elements.append(_hr())

    # 重点行动项
    if top_actions:
        actions_md = "📌 **重点行动项：**\n"
        for i, item in enumerate(top_actions[:5], 1):
            client = item.get("client", "")
            action = item.get("action", "")[:60]
            assigned = item.get("assigned_to", "")
            line = f"{i}. {action}"
            if client:
                line = f"{i}. {client} — {action}"
            if assigned:
                line += f" → {assigned}"
            actions_md += line + "\n"
        elements.append(_text(actions_md))

    elements.append(_note(f"MailPulse · {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(
            f"{'🔴 ' if high_priority > 0 else '📊 '}{company_name} 邮件周报 · {date_range}",
            "red" if high_priority > 0 else "blue",
        ),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 2. 客户线程卡片（高优先单独推送）
# ══════════════════════════════════════════════════════════════

def build_client_thread_card(
    thread_id: str,
    subject: str,
    client_name: str,
    score: int,
    summary: str,
    assignee: str = "",
    email_count: int = 0,
    direction: str = "",
    action_item_id: Optional[str] = None,
) -> Dict[str, Any]:
    """单个客户/线程卡片，带操作按钮"""
    template = "red" if score >= 5 else ("orange" if score >= 4 else "yellow")
    score_label = "🔴 紧急" if score >= 5 else ("🟠 重要" if score >= 4 else "🟡 关注")

    elements = []

    # 客户信息
    info = f"**客户：** {client_name}\n"
    info += f"**主题：** {subject}\n"
    info += f"**优先级：** {score_label}（{score}/5）\n"
    info += f"**邮件往来：** {email_count} 封"
    if direction:
        dir_label = "客户最新回复" if direction == "inbound" else "我方最新发出"
        info += f"　|　**状态：** {dir_label}"
    if assignee:
        info += f"\n**负责人：** {assignee}"
    elements.append(_text(info))
    elements.append(_hr())

    # 摘要
    elements.append(_text(f"**AI 分析：**\n{summary}"))

    # 操作按钮
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

    elements.append(_note(f"MailPulse · Thread {thread_id[:8]}"))

    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": _header(f"{score_label} | {subject[:50]}", template),
        "elements": elements,
    }


def build_escalation_card(
    title: str,
    assignee_name: str,
    hours_overdue: int,
    priority: str,
    action_item_id: str,
    client_name: str = "",
    company_name: str = "",
) -> Dict[str, Any]:
    """未确认任务升级卡片 — 推到群里"""
    elements = []
    info = f"**原负责人：** {assignee_name}（{hours_overdue}h 未确认）\n"
    info += f"**优先级：** {'🔴 高' if priority == 'high' else '🟡 中'}\n"
    if client_name:
        info += f"**客户：** {client_name}\n"
    if company_name:
        info += f"**公司：** {company_name}\n"
    elements.append(_text(info))

    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "🙋 我来处理"},
                "type": "primary",
                "value": {"action": "claim", "item_id": action_item_id},
            },
        ],
    })

    elements.append(_note(f"MailPulse 自动升级 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

    return {
        "config": {"wide_screen_mode": True, "update_multi": True},
        "header": _header(f"⚠️ 超时未处理 | {title[:50]}", "orange"),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 3. 告警卡片（超期/SLA 违规）
# ══════════════════════════════════════════════════════════════

def build_alert_card(
    title: str,
    items: List[Dict],
    severity: str = "warning",
) -> Dict[str, Any]:
    """紧急告警卡片"""
    template = "red" if severity == "critical" else "orange"
    emoji = "🚨" if severity == "critical" else "⚠️"

    elements = []
    for item in items[:10]:
        subject = item.get("subject", item.get("title", ""))[:50]
        assignee = item.get("assigned_to", "未指定")
        days = item.get("days", 0)
        elements.append(_text(f"• **{subject}**\n  负责人：{assignee}　|　已超期 {days} 天"))

    if len(items) > 10:
        elements.append(_text(f"... 及其他 {len(items) - 10} 项"))

    elements.append(_note(f"MailPulse 自动告警 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"{emoji} {title}", template),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 4. 任务卡片
# ══════════════════════════════════════════════════════════════

def build_task_card(
    title: str,
    description: str = "",
    assignee: str = "",
    priority: str = "medium",
    client: str = "",
    deadline: str = "",
) -> Dict[str, Any]:
    """任务/待办卡片"""
    priority_map = {
        "high": ("🔴 高", "red"),
        "medium": ("🟡 中", "yellow"),
        "low": ("🟢 低", "green"),
    }
    label, template = priority_map.get(priority, ("🟡 中", "yellow"))

    elements = []

    info = f"**优先级：** {label}\n"
    if client:
        info += f"**客户：** {client}\n"
    if assignee:
        info += f"**负责人：** {assignee}\n"
    if deadline:
        info += f"**截止：** {deadline}\n"
    if description:
        info += f"\n{description}"

    elements.append(_text(info))
    elements.append(_note(f"MailPulse · {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"📋 {title[:60]}", template),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 5. 每日待办卡片（私聊推送）
# ══════════════════════════════════════════════════════════════

def build_daily_todo_card(
    person_name: str,
    date_str: str,
    urgent_items: Optional[List[Dict]] = None,
    pending_items: Optional[List[Dict]] = None,
    followup_items: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """每日待办摘要卡片"""
    urgent = urgent_items or []
    pending = pending_items or []
    followups = followup_items or []
    total = len(urgent) + len(pending) + len(followups)

    elements = []

    if total == 0:
        elements.append(_text("✨ 今天没有待处理事项，状态良好！"))
        elements.append(_note(f"MailPulse · {date_str}"))
        return {
            "config": {"wide_screen_mode": True},
            "header": _header(f"📋 {person_name} · {date_str} · 无待办", "green"),
            "elements": elements,
        }

    # 紧急/超期 — 每项带独立按钮（最多3项）
    if urgent:
        urgent_md = "🔴 **需立即处理**\n"
        for i, item in enumerate(urgent[:5], 1):
            title = item.get("title", "")[:50]
            days = item.get("days_pending", 0)
            suffix = f" — 等待 {days} 天" if days else ""
            urgent_md += f"{i}. {title}{suffix}\n"
        elements.append(_text(urgent_md))
        # Per-item buttons for top 3 urgent items
        buttons = []
        for item in urgent[:3]:
            if item.get("id"):
                buttons.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": f"✅ {item.get('title', '')[:12]}"},
                    "type": "primary",
                    "value": {"action": "handled", "item_id": item["id"]},
                })
        if buttons:
            elements.append({"tag": "action", "actions": buttons})
        elements.append(_hr())

    # 需跟进
    if followups:
        followup_md = "📧 **需跟进**\n"
        for i, item in enumerate(followups[:5], 1):
            subject = item.get("subject", "")[:50]
            reason = item.get("reason", "")
            followup_md += f"{i}. {subject}\n"
            if reason:
                followup_md += f"   _{reason}_\n"
        elements.append(_text(followup_md))
        elements.append(_hr())

    # 进行中
    if pending:
        pending_md = "🟡 **进行中**\n"
        for i, item in enumerate(pending[:5], 1):
            title = item.get("title", "")[:50]
            pending_md += f"{i}. {title}\n"
        elements.append(_text(pending_md))

    elements.append(_note(
        f"MailPulse · {date_str} · "
        f"{'🔴' if urgent else '🟢'} {total} 项待办"
    ))

    color = "red" if urgent else ("yellow" if followups else "blue")
    return {
        "config": {"wide_screen_mode": True},
        "header": _header(
            f"📋 {person_name} 的今日待办 · {date_str}",
            color,
        ),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 6. 个人周报卡片
# ══════════════════════════════════════════════════════════════

def build_weekly_report_card(
    person_name: str,
    period: str,
    stats: Dict[str, Any],
    highlights: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """个人周报卡片 — 异常优先设计"""
    elements = []

    # 数据概览
    total = stats.get("emails_total", 0)
    inbound = stats.get("emails_inbound", 0)
    outbound = stats.get("emails_outbound", 0)
    high = stats.get("high_priority", 0)
    created = stats.get("action_items_created", 0)
    resolved = stats.get("action_items_resolved", 0)
    pending = stats.get("pending_items", 0)

    overview = (
        f"📧 邮件：**{total}** 封（收 {inbound} / 发 {outbound}）\n"
        f"🔴 高优先：**{high}** 封\n"
        f"📋 任务：创建 **{created}** / 完成 **{resolved}**"
    )
    if pending > 0:
        overview += f" / ⚠️ 待处理 **{pending}**"
    elements.append(_text(overview))
    elements.append(_hr())

    # AI 亮点 / 异常
    if highlights:
        highlights_md = "💡 **本周要点**\n"
        for h in highlights:
            highlights_md += f"• {h}\n"
        elements.append(_text(highlights_md))
        elements.append(_hr())

    # 主要客户
    top_clients = stats.get("top_clients", [])
    if top_clients:
        clients_md = "👥 **主要客户**\n"
        for c in top_clients[:3]:
            clients_md += f"• {c['name']}（{c['count']} 封）\n"
        elements.append(_text(clients_md))

    elements.append(_note(f"MailPulse 周报 · {period}"))

    color = "red" if pending > 3 or high > 5 else "blue"
    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"📊 {person_name} 周报 · {period}", color),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 7. 日历提案卡片
# ══════════════════════════════════════════════════════════════

def build_calendar_proposal_card(
    proposal_id: str,
    event_title: str,
    event_start: str,
    event_end: str = "",
    location: str = "",
    attendees: Optional[List[str]] = None,
    source_subject: str = "",
) -> Dict[str, Any]:
    """日历提案确认卡片 — 用户点击创建或忽略"""
    elements = []

    info = f"**主题：** {event_title}\n"
    info += f"**时间：** {event_start}"
    if event_end:
        info += f" ~ {event_end}"
    info += "\n"
    if location:
        info += f"**地点：** {location}\n"
    if attendees:
        info += f"**参与人：** {', '.join(attendees)}\n"
    if source_subject:
        info += f"\n_来源邮件：{source_subject}_"

    elements.append(_text(info))

    # Confirm / Reject buttons
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "✅ 添加到日历"},
                "type": "primary",
                "value": {"action": "calendar_accept", "proposal_id": proposal_id},
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "❌ 忽略"},
                "type": "default",
                "value": {"action": "calendar_reject", "proposal_id": proposal_id},
            },
        ],
    })

    elements.append(_note(f"MailPulse · 检测到日程安排"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"📅 日程提案 | {event_title[:40]}", "purple"),
        "elements": elements,
    }
