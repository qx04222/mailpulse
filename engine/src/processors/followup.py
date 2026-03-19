"""
Followup checker — compares pending action items with new emails
to detect which threads have new activity (resolved) and which are still pending.
"""
from typing import List, Dict, Any

from ..sources.gmail_source import RawItem
from ..storage.action_items import get_pending_items, mark_resolved_by_thread
from ..storage.threads import get_thread_by_gmail_id


def check_and_update_followups(
    company_id: str,
    new_items: List[RawItem],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compare pending action items with new email data:
    - If an action item's thread has new activity, mark it resolved
    - Return categorized followup status for the digest prompt

    Args:
        company_id: UUID of the company
        new_items: List of RawItem from Gmail fetch
    """
    pending = get_pending_items(company_id)
    if not pending:
        return {"resolved": [], "overdue": [], "still_pending": []}

    # Build set of thread UUIDs that have new email activity
    current_thread_ids = set()
    for item in new_items:
        gmail_thread_id = item.metadata.get("thread_id")
        if gmail_thread_id:
            thread = get_thread_by_gmail_id(gmail_thread_id)
            if thread:
                current_thread_ids.add(thread["id"])

    resolved = []
    overdue = []
    still_pending = []

    for action in pending:
        tid = action.get("thread_id")
        if tid and tid in current_thread_ids:
            # Thread has new activity — resolve the action item
            mark_resolved_by_thread(tid, note="auto: new activity in thread")
            resolved.append(action)
        elif action["status"] == "overdue":
            overdue.append(action)
        else:
            still_pending.append(action)

    return {
        "resolved": resolved,
        "overdue": overdue,
        "still_pending": still_pending,
    }


def format_followup_section(followup_status: Dict[str, List[Dict[str, Any]]]) -> str:
    """Format followup status for the Sonnet analysis prompt."""
    lines = []

    if followup_status["resolved"]:
        lines.append("【本期已解决】")
        for item in followup_status["resolved"]:
            title = item.get("title", "(untitled)")
            lines.append(f"  OK {title}")

    if followup_status["overdue"]:
        lines.append("【超期未处理】")
        for item in followup_status["overdue"]:
            days = item.get("seen_count", 1) * 3  # Estimate days
            title = item.get("title", "(untitled)")
            lines.append(f"  [{days} days+] {title}")

    if followup_status["still_pending"]:
        lines.append("【上期待处理（持续跟进）】")
        for item in followup_status["still_pending"]:
            title = item.get("title", "(untitled)")
            lines.append(f"  {title}")

    return "\n".join(lines) if lines else "（无历史待跟进项目）"
