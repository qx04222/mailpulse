"""
Lark interactive message card templates.
Each function takes data and returns a Lark card JSON dict.

Card format reference:
https://open.larksuite.com/document/common-capabilities/message-card/getting-started/card-structure
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


def _header(title: str, template: str = "blue") -> Dict:
    """Build a card header."""
    return {
        "title": {"tag": "plain_text", "content": title},
        "template": template,
    }


def _text_element(content: str) -> Dict:
    """Build a plain text div element."""
    return {
        "tag": "div",
        "text": {"tag": "lark_md", "content": content},
    }


def _divider() -> Dict:
    """Build a horizontal divider."""
    return {"tag": "hr"}


def _button(text: str, action: str, value: Optional[Dict] = None, btn_type: str = "default") -> Dict:
    """Build a button action element."""
    return {
        "tag": "button",
        "text": {"tag": "plain_text", "content": text},
        "type": btn_type,
        "value": value or {"action": action},
    }


def _note(text: str) -> Dict:
    """Build a note element (small text at bottom)."""
    return {
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": text},
        ],
    }


# ══════════════════════════════════════════════════════════════
# 1. Daily Digest Card
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
    """
    Build the daily/weekly digest summary card.
    Shows overview stats with expandable per-assignee sections.
    """
    elements: List[Dict] = []

    # Overview stats
    stats_md = (
        f"**{company_name}** - {date_range}\n"
        f"- Total emails: **{total_emails}**  |  Threads: **{total_threads}**\n"
        f"- High priority: **{high_priority}**  |  Needs attention: **{actionable}**  |  Low: **{low_priority}**"
    )
    elements.append(_text_element(stats_md))
    elements.append(_divider())

    # Per-assignee sections (collapsible via markdown)
    for assignee, report in group_reports.items():
        # Truncate long reports for card display
        truncated = report[:600]
        if len(report) > 600:
            truncated += "\n..."
        elements.append(_text_element(f"**{assignee}**\n{truncated}"))
        elements.append(_divider())

    # Top action items
    if top_actions:
        actions_md = "**Top Action Items:**\n"
        for i, item in enumerate(top_actions[:5], 1):
            client = item.get("client", "")
            action = item.get("action", "")[:80]
            assigned = item.get("assigned_to", "")
            actions_md += f"{i}. {client}: {action}"
            if assigned:
                actions_md += f" -> {assigned}"
            actions_md += "\n"
        elements.append(_text_element(actions_md))

    # Footer
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    elements.append(_note(f"MailPulse Report | Generated {now}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(
            f"{company_name} Digest | {date_range}",
            "blue" if high_priority == 0 else "red",
        ),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 2. Client Thread Card
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
    """
    Build a card for a single client/thread with action buttons.
    Used for high-priority thread alerts.
    """
    # Score-based color
    template = "red" if score >= 5 else ("orange" if score >= 4 else "yellow")

    elements: List[Dict] = []

    # Thread info
    info_md = (
        f"**Client:** {client_name}\n"
        f"**Subject:** {subject}\n"
        f"**Score:** {'*' * score} ({score}/5)\n"
        f"**Emails:** {email_count}  |  **Direction:** {direction}\n"
    )
    if assignee:
        info_md += f"**Assignee:** {assignee}\n"

    elements.append(_text_element(info_md))
    elements.append(_divider())

    # Summary
    elements.append(_text_element(f"**Summary:**\n{summary}"))

    # Action buttons
    elements.append({
        "tag": "action",
        "actions": [
            _button("Mark Done", "mark_done",
                    {"action": "mark_done", "thread_id": thread_id},
                    "primary"),
            _button("Assign", "assign",
                    {"action": "assign", "thread_id": thread_id}),
            _button("Create Calendar", "create_calendar",
                    {"action": "create_calendar", "thread_id": thread_id}),
            _button("View Details", "view_details",
                    {"action": "view_details", "thread_id": thread_id}),
        ],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"[{score}/5] {subject[:60]}", template),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 3. Weekly Report Card
# ══════════════════════════════════════════════════════════════

def build_weekly_report_card(
    company_name: str,
    date_range: str,
    total_emails: int,
    total_threads: int,
    resolved_count: int,
    new_clients: int,
    top_priorities: Optional[List[Dict]] = None,
    per_person_stats: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Build a weekly report overview card.
    Shows higher-level stats and top priorities.
    """
    elements: List[Dict] = []

    # Stats overview
    stats_md = (
        f"**Period:** {date_range}\n"
        f"**Emails:** {total_emails}  |  **Threads:** {total_threads}\n"
        f"**Resolved:** {resolved_count}  |  **New Clients:** {new_clients}"
    )
    elements.append(_text_element(stats_md))
    elements.append(_divider())

    # Per person workload
    if per_person_stats:
        workload_md = "**Team Workload:**\n"
        for ps in per_person_stats:
            name = ps.get("name", "Unassigned")
            count = ps.get("client_count", 0)
            pending = ps.get("pending", 0)
            workload_md += f"- {name}: {count} clients, {pending} pending\n"
        elements.append(_text_element(workload_md))
        elements.append(_divider())

    # Top priorities
    if top_priorities:
        prio_md = "**Top Priorities:**\n"
        for i, p in enumerate(top_priorities[:8], 1):
            client = p.get("client", "")
            action = p.get("action", "")[:60]
            prio_md += f"{i}. **{client}**: {action}\n"
        elements.append(_text_element(prio_md))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    elements.append(_note(f"MailPulse Weekly Report | {now}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(f"{company_name} Weekly Report | {date_range}", "purple"),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 4. Alert Card
# ══════════════════════════════════════════════════════════════

def build_alert_card(
    title: str,
    items: List[Dict],
    alert_type: str = "overdue",
) -> Dict[str, Any]:
    """
    Build an alert card for urgent/overdue items.
    alert_type: "overdue" | "sla_breach" | "urgent"
    """
    template_map = {
        "overdue": "red",
        "sla_breach": "orange",
        "urgent": "red",
    }
    icon_map = {
        "overdue": "Overdue Alert",
        "sla_breach": "SLA Breach Alert",
        "urgent": "Urgent Alert",
    }

    elements: List[Dict] = []

    for item in items[:10]:
        item_title = item.get("title", "")
        client = item.get("client", "")
        assignee = item.get("assignee", "Unassigned")
        days = item.get("days_overdue", 0)

        line = f"- **{item_title}**"
        if client:
            line += f"  ({client})"
        line += f"\n  Assignee: {assignee}"
        if days:
            line += f"  |  {days} days overdue"
        elements.append(_text_element(line))

    if len(items) > 10:
        elements.append(_text_element(f"... and {len(items) - 10} more"))

    now = datetime.now().strftime("%H:%M")
    elements.append(_note(f"MailPulse Alert | {now}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(
            f"{icon_map.get(alert_type, 'Alert')} | {title}",
            template_map.get(alert_type, "red"),
        ),
        "elements": elements,
    }


# ══════════════════════════════════════════════════════════════
# 5. Task Card
# ══════════════════════════════════════════════════════════════

def build_task_card(
    task_id: str,
    title: str,
    description: str = "",
    assignee: str = "",
    deadline: Optional[str] = None,
    priority: str = "medium",
    client: str = "",
) -> Dict[str, Any]:
    """
    Build an action item / task card with assignee and deadline.
    """
    template_map = {"high": "red", "medium": "orange", "low": "green"}

    elements: List[Dict] = []

    info_md = f"**Priority:** {priority.upper()}\n"
    if client:
        info_md += f"**Client:** {client}\n"
    if assignee:
        info_md += f"**Assignee:** {assignee}\n"
    if deadline:
        info_md += f"**Deadline:** {deadline}\n"

    elements.append(_text_element(info_md))

    if description:
        elements.append(_text_element(description[:300]))

    elements.append({
        "tag": "action",
        "actions": [
            _button("Complete", "resolve_task",
                    {"action": "resolve_task", "task_id": task_id},
                    "primary"),
            _button("Dismiss", "dismiss_task",
                    {"action": "dismiss_task", "task_id": task_id},
                    "default"),
        ],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": _header(
            f"[{priority.upper()}] {title[:60]}",
            template_map.get(priority, "orange"),
        ),
        "elements": elements,
    }
