"""
报告生成器 v2：线程聚合 + 分组小报告 + 合并完整报告

流程：
1. 从 DB 读取已打分的邮件（增量分析，不重新调 AI）
2. 按 thread 聚合（同一对话合并）
3. 只保留需行动的（score >= 3）
4. 按负责人分组
5. 每组调 Sonnet 生成小报告
6. 合并所有小报告为完整报告
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from collections import defaultdict

from anthropic import Anthropic
from ..config import settings
from ..storage.db import db

client = Anthropic(api_key=settings.anthropic_api_key)


# ── Step 1: 从 DB 读取已有数据 ──────────────────────────────────

def get_emails_for_report(company_id: str, lookback_days: int = 3) -> List[Dict]:
    """从数据库读取已打分的邮件，不调 AI"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    resp = db.table("emails") \
        .select("*") \
        .eq("company_id", company_id) \
        .gte("received_at", cutoff) \
        .order("received_at", desc=True) \
        .execute()
    return resp.data or []


def get_people_map() -> Dict[str, str]:
    """获取 person_id → name 映射"""
    resp = db.table("people").select("id, name").execute()
    return {p["id"]: p["name"] for p in (resp.data or [])}


# ── Step 2: 按 thread 聚合 ──────────────────────────────────────

def aggregate_by_thread(emails: List[Dict]) -> List[Dict]:
    """
    将同一 thread 的邮件聚合为一条记录。
    返回每个 thread 的摘要：最新邮件、往来次数、参与者、最高分等。
    """
    threads = defaultdict(list)
    for email in emails:
        tid = email.get("gmail_thread_id") or email.get("id")
        threads[tid].append(email)

    aggregated = []
    for tid, thread_emails in threads.items():
        # 按时间排序
        sorted_emails = sorted(thread_emails, key=lambda x: x.get("received_at", ""))
        latest = sorted_emails[-1]
        first = sorted_emails[0]

        # 统计
        inbound = [e for e in sorted_emails if e.get("direction") == "inbound"]
        outbound = [e for e in sorted_emails if e.get("direction") == "outbound"]
        max_score = max((e.get("score") or 0) for e in sorted_emails)
        has_action = any(e.get("action_needed") for e in sorted_emails)

        # 参与者
        senders = list(set(e.get("sender_name") or e.get("sender_email", "") for e in sorted_emails))
        assignee_id = latest.get("assigned_to_id")

        # 构建线程摘要
        aggregated.append({
            "thread_id": tid,
            "subject": first.get("subject", ""),
            "latest_sender": latest.get("sender_name") or latest.get("sender_email", ""),
            "latest_date": latest.get("received_at", "")[:10],
            "latest_preview": (latest.get("body_preview") or "")[:150],
            "email_count": len(sorted_emails),
            "inbound_count": len(inbound),
            "outbound_count": len(outbound),
            "max_score": max_score,
            "has_action": has_action,
            "participants": senders[:5],
            "assigned_to_id": assignee_id,
            "score_reason": latest.get("score_reason", ""),
            "one_line": latest.get("one_line", ""),
            "client_name": latest.get("client_name", ""),
            "direction": latest.get("direction", ""),
            # 对话流向描述
            "flow": _describe_flow(sorted_emails),
        })

    # 按最高分降序
    aggregated.sort(key=lambda x: x["max_score"], reverse=True)
    return aggregated


def _describe_flow(emails: List[Dict]) -> str:
    """描述邮件往来流向"""
    if len(emails) == 1:
        d = emails[0].get("direction", "")
        return "收到客户邮件" if d == "inbound" else "我方发出邮件"

    last = emails[-1]
    if last.get("direction") == "inbound":
        return f"共{len(emails)}封往来，客户最新回复"
    else:
        return f"共{len(emails)}封往来，我方最新发出，等待回复"


# ── Step 3: 过滤需行动的 ────────────────────────────────────────

def filter_actionable(threads: List[Dict], min_score: int = 3) -> List[Dict]:
    """只保留需要关注的线程"""
    return [t for t in threads if t["max_score"] >= min_score]


# ── Step 4: 按负责人分组 ────────────────────────────────────────

def group_by_assignee(threads: List[Dict], people_map: Dict[str, str]) -> Dict[str, List[Dict]]:
    """按负责人分组，未分配的归入"待分配"组"""
    groups = defaultdict(list)
    for t in threads:
        assignee_id = t.get("assigned_to_id")
        assignee_name = people_map.get(assignee_id, "待分配") if assignee_id else "待分配"
        groups[assignee_name].append(t)
    return dict(groups)


# ── Step 5: 每组生成小报告 ──────────────────────────────────────

GROUP_REPORT_PROMPT = """你是邮件分析助手。请为 {company} 公司 {assignee} 负责的邮件生成中文周报摘要。

## {assignee} 负责的邮件线程（{count} 个）
{threads_text}

请用以下格式输出（纯文本，不要 JSON，不要 Markdown 标记）：

【{assignee} 负责 · {count} 个线程】

需立即处理：
（列出 score >= 4 的，每条一行：客户名 | 主题 | 原因 | 建议行动）

需要关注：
（列出 score = 3 的，每条一行：客户名 | 主题 | 一句话摘要）

对话进展：
（简要描述各线程的往来状态，哪些在等回复，哪些已回复）

小结：（1-2句话总结此人的工作重点）
"""


async def generate_group_report(
    company_name: str,
    assignee: str,
    threads: List[Dict],
) -> str:
    """为一个负责人生成小报告"""
    threads_text = ""
    for t in threads:
        threads_text += (
            f"- 主题: {t['subject']}\n"
            f"  客户: {t.get('client_name') or '未知'}\n"
            f"  评分: {t['max_score']}/5 | {t['score_reason']}\n"
            f"  往来: {t['flow']}（{t['email_count']}封）\n"
            f"  最新: {t['latest_sender']} @ {t['latest_date']}\n"
            f"  摘要: {t['one_line']}\n"
            f"  预览: {t['latest_preview']}\n\n"
        )

    prompt = GROUP_REPORT_PROMPT.format(
        company=company_name,
        assignee=assignee,
        count=len(threads),
        threads_text=threads_text,
    )

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ── Step 6: 合并完整报告 ────────────────────────────────────────

def _date_range(lookback_days: int) -> str:
    now = datetime.now()
    return f"{(now - timedelta(days=lookback_days)).strftime('%m/%d')}–{now.strftime('%m/%d')}"


async def generate_full_report(
    company_id: str,
    company_name: str,
    lookback_days: int = 3,
) -> tuple:
    """
    完整的报告生成流程（增量分析）。
    返回 (full_text, structured_data, telegram_brief)
    """
    date_range = _date_range(lookback_days)
    people_map = get_people_map()

    # Step 1: 从 DB 读取
    emails = get_emails_for_report(company_id, lookback_days)
    if not emails:
        brief = f"{company_name} 周报 · {date_range}\n本期无邮件。"
        return brief, {}, brief

    # Step 2: 按 thread 聚合
    threads = aggregate_by_thread(emails)

    # Step 3: 过滤
    actionable = filter_actionable(threads, min_score=3)
    low_priority = [t for t in threads if t["max_score"] < 3]

    # Step 4: 按负责人分组
    groups = group_by_assignee(actionable, people_map)

    # Step 5: 每组生成小报告
    group_reports = {}
    for assignee, group_threads in groups.items():
        try:
            report = await generate_group_report(company_name, assignee, group_threads)
            group_reports[assignee] = report
        except Exception as e:
            group_reports[assignee] = f"【{assignee}】报告生成失败: {str(e)[:100]}"

    # Step 6: 合并
    full_lines = [
        f"{'='*40}",
        f"{company_name} 邮件周报",
        f"统计周期：{date_range}",
        f"{'='*40}",
        "",
        f"总计 {len(emails)} 封邮件，{len(threads)} 个对话线程",
        f"需处理/关注：{len(actionable)} 个 | 低优先：{len(low_priority)} 个",
        "",
    ]

    # 各负责人报告
    for assignee, report in group_reports.items():
        full_lines.append(report)
        full_lines.append("")

    # 低优先概览
    if low_priority:
        full_lines.append(f"【低优先邮件 · {len(low_priority)} 个线程】")
        for t in low_priority[:10]:
            full_lines.append(f"  · {t['subject'][:40]} — {t.get('one_line', '')}")
        if len(low_priority) > 10:
            full_lines.append(f"  ... 及其他 {len(low_priority) - 10} 个")
        full_lines.append("")

    full_lines.append(f"报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    full_text = "\n".join(full_lines)

    # Telegram 简要摘要
    brief_lines = [
        f"{company_name} 周报 · {date_range}",
        f"共 {len(emails)} 封邮件，{len(threads)} 个对话",
        "",
    ]

    # 只列高优先
    high_threads = [t for t in actionable if t["max_score"] >= 4]
    if high_threads:
        brief_lines.append(f"需立即处理（{len(high_threads)}项）：")
        for t in high_threads[:5]:
            assignee = people_map.get(t.get("assigned_to_id"), "")
            assignee_str = f" → {assignee}" if assignee else ""
            brief_lines.append(f"  · {t['subject'][:35]}{assignee_str}")
        brief_lines.append("")

    med_threads = [t for t in actionable if t["max_score"] == 3]
    if med_threads:
        brief_lines.append(f"需关注（{len(med_threads)}项）：")
        for t in med_threads[:5]:
            brief_lines.append(f"  · {t['subject'][:35]}")

    telegram_brief = "\n".join(brief_lines)

    # structured_data for DOCX
    structured_data = {
        "overview": {
            "total_emails": len(emails),
            "period": date_range,
            "company": company_name,
            "highlights": f"共{len(threads)}个对话线程，{len(actionable)}个需处理",
            "per_person_stats": [
                {"name": k, "client_count": len(v), "quoted": 0, "pending": len(v), "resolved": 0}
                for k, v in groups.items()
            ],
        },
        "clients": [],
        "priority_actions": [
            {
                "priority": "high" if t["max_score"] >= 4 else "medium",
                "action": t.get("score_reason") or t["subject"],
                "assigned_to": people_map.get(t.get("assigned_to_id"), "待分配"),
                "client": t.get("client_name", ""),
                "deadline": None,
            }
            for t in actionable[:20]
        ],
        "followup_update": {"resolved": [], "overdue": [], "still_pending": []},
        "trash_spam_review": [],
        "group_reports": group_reports,
    }

    return full_text, structured_data, telegram_brief
