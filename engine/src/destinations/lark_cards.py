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
) -> Dict[str, Any]:
    """单个客户/线程卡片"""
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

    elements.append(_note(f"MailPulse · Thread {thread_id[:8]}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"{score_label} | {subject[:50]}", template),
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
