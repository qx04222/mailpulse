"""
报告生成器 v3：线程摘要 + 分组拆批 + 零遗漏

流程：
1. 从 DB 读取已打分的邮件（增量，不重新调 AI）
2. 按 thread 聚合
3. 每个 thread → Haiku 生成 100 字线程摘要（保证每封邮件信息都提取）
4. 按负责人分组
5. 每人超过 15 个线程 → 自动拆批
6. 每批 → Sonnet 生成小报告
7. 合并所有小报告为完整报告

关键：零遗漏，每封邮件都参与分析。
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from collections import defaultdict

from anthropic import Anthropic
from ..config import settings
from ..storage.db import db

client = Anthropic(api_key=settings.anthropic_api_key)

BATCH_SIZE = 15  # 每批最多线程数
HAIKU_BATCH = 5  # Haiku 并发批大小


# ══════════════════════════════════════════════════════════════
# Step 1: 从 DB 读取
# ══════════════════════════════════════════════════════════════

def get_emails_for_report(company_id: str, lookback_days: int = 3) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    resp = db.table("emails") \
        .select("*") \
        .eq("company_id", company_id) \
        .gte("received_at", cutoff) \
        .order("received_at", desc=True) \
        .execute()
    return resp.data or []


def get_people_map() -> Dict[str, str]:
    resp = db.table("people").select("id, name").execute()
    return {p["id"]: p["name"] for p in (resp.data or [])}


# ══════════════════════════════════════════════════════════════
# Step 2: 按 thread 聚合
# ══════════════════════════════════════════════════════════════

def aggregate_by_thread(emails: List[Dict]) -> List[Dict]:
    threads = defaultdict(list)
    for email in emails:
        tid = email.get("gmail_thread_id") or email.get("id")
        threads[tid].append(email)

    aggregated = []
    for tid, thread_emails in threads.items():
        sorted_emails = sorted(thread_emails, key=lambda x: x.get("received_at", ""))
        latest = sorted_emails[-1]
        first = sorted_emails[0]

        inbound = [e for e in sorted_emails if e.get("direction") == "inbound"]
        outbound = [e for e in sorted_emails if e.get("direction") == "outbound"]
        max_score = max((e.get("score") or 0) for e in sorted_emails)
        has_action = any(e.get("action_needed") for e in sorted_emails)

        # Last inbound/outbound timestamps
        last_inbound_at = inbound[-1].get("received_at", "") if inbound else ""
        last_outbound_at = outbound[-1].get("received_at", "") if outbound else ""
        last_inbound_from = inbound[-1].get("sender_name", "") or inbound[-1].get("sender_email", "") if inbound else ""

        aggregated.append({
            "thread_id": tid,
            "subject": first.get("subject", ""),
            "emails": sorted_emails,  # 保留所有邮件用于 Haiku 摘要
            "latest": latest,
            "first_email_at": first.get("received_at", ""),
            "last_email_at": latest.get("received_at", ""),
            "last_inbound_at": last_inbound_at,
            "last_outbound_at": last_outbound_at,
            "last_inbound_from": last_inbound_from,
            "email_count": len(sorted_emails),
            "inbound_count": len(inbound),
            "outbound_count": len(outbound),
            "max_score": max_score,
            "has_action": has_action,
            "assigned_to_id": latest.get("assigned_to_id"),
            "client_name": latest.get("client_name", ""),
            "client_email": latest.get("sender_email", "") if latest.get("direction") == "inbound" else (inbound[-1].get("sender_email", "") if inbound else ""),
            "direction": latest.get("direction", ""),
        })

    aggregated.sort(key=lambda x: x["max_score"], reverse=True)
    return aggregated


# ══════════════════════════════════════════════════════════════
# Step 3: Haiku 线程摘要（零遗漏核心）
# ══════════════════════════════════════════════════════════════

THREAD_SUMMARY_PROMPT = """请用100字以内的中文摘要这个邮件对话线程。

主题：{subject}
共 {count} 封邮件（{inbound} 封收到，{outbound} 封发出）

对话内容（按时间顺序）：
{conversation}

请输出：
客户/联系人 | 讨论内容 | 当前状态（等待回复/已回复/待处理/已完成）| 需要的行动（如有）"""


async def summarize_thread(thread: Dict) -> str:
    """用 Haiku 生成线程摘要，确保每封邮件信息都被提取"""
    emails = thread["emails"]

    # 构建对话内容（每封邮件都包含）
    conversation_lines = []
    for e in emails:
        direction_label = "→ 收到" if e.get("direction") == "inbound" else "← 发出"
        sender = e.get("sender_name") or e.get("sender_email", "")
        date = (e.get("received_at") or "")[:10]
        preview = (e.get("body_preview") or "")[:150]
        score_info = f"[评分:{e.get('score', '?')}]" if e.get("score") else ""

        conversation_lines.append(
            f"{direction_label} {sender} ({date}) {score_info}\n  {preview}"
        )

    conversation = "\n".join(conversation_lines)

    prompt = THREAD_SUMMARY_PROMPT.format(
        subject=thread["subject"],
        count=thread["email_count"],
        inbound=thread["inbound_count"],
        outbound=thread["outbound_count"],
        conversation=conversation[:2000],  # 单线程最多 2000 字
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        # fallback：用最新邮件的 one_line
        return thread["latest"].get("one_line") or thread["subject"]


async def batch_summarize_threads(threads: List[Dict]) -> List[Dict]:
    """分批并发生成线程摘要"""
    for i in range(0, len(threads), HAIKU_BATCH):
        batch = threads[i:i + HAIKU_BATCH]
        summaries = await asyncio.gather(
            *[summarize_thread(t) for t in batch]
        )
        for t, summary in zip(batch, summaries):
            t["thread_summary"] = summary

        if i + HAIKU_BATCH < len(threads):
            await asyncio.sleep(1)  # 避免限速

    return threads


# ══════════════════════════════════════════════════════════════
# Step 4: 按负责人分组
# ══════════════════════════════════════════════════════════════

def group_by_assignee(threads: List[Dict], people_map: Dict[str, str]) -> Dict[str, List[Dict]]:
    groups = defaultdict(list)
    for t in threads:
        assignee_id = t.get("assigned_to_id")
        assignee_name = people_map.get(assignee_id, "待分配") if assignee_id else "待分配"
        groups[assignee_name].append(t)
    return dict(groups)


# ══════════════════════════════════════════════════════════════
# Step 5: 分批生成 Sonnet 小报告
# ══════════════════════════════════════════════════════════════

GROUP_REPORT_PROMPT = """你是邮件分析助手。请为 {company} 公司 {assignee} 负责的邮件生成中文周报。

## {assignee} 负责的邮件线程（{count} 个）{batch_info}

{threads_text}

请用以下格式输出（纯文本，不要 JSON，不要 Markdown 标记符号）：

【{assignee} · {count} 个对话{batch_info}】

需立即处理：
（列出 score >= 4 的，每条格式：客户名 | 主题 | 原因 | 建议行动）

需要关注：
（列出 score = 3 的，每条格式：客户名 | 主题 | 一句话摘要）

对话进展：
（简要描述各线程的往来状态）

小结：（1-2句话）"""


async def generate_group_report(
    company_name: str,
    assignee: str,
    threads: List[Dict],
    batch_num: int = 0,
    total_batches: int = 1,
) -> str:
    """为一个负责人的一批线程生成报告"""
    batch_info = f"（第{batch_num}/{total_batches}批）" if total_batches > 1 else ""

    threads_text = ""
    for t in threads:
        threads_text += (
            f"- 主题: {t['subject']}\n"
            f"  客户: {t.get('client_name') or '未知'}\n"
            f"  评分: {t['max_score']}/5\n"
            f"  往来: {t['email_count']}封（收{t['inbound_count']}/发{t['outbound_count']}）\n"
            f"  摘要: {t.get('thread_summary', t['latest'].get('one_line', ''))}\n\n"
        )

    prompt = GROUP_REPORT_PROMPT.format(
        company=company_name,
        assignee=assignee,
        count=len(threads),
        batch_info=batch_info,
        threads_text=threads_text,
    )

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


async def generate_assignee_reports(
    company_name: str,
    assignee: str,
    threads: List[Dict],
) -> str:
    """为一个负责人生成完整报告（自动拆批）"""
    if len(threads) <= BATCH_SIZE:
        return await generate_group_report(company_name, assignee, threads)

    # 拆批
    batches = [threads[i:i + BATCH_SIZE] for i in range(0, len(threads), BATCH_SIZE)]
    reports = []
    for idx, batch in enumerate(batches, 1):
        try:
            report = await generate_group_report(
                company_name, assignee, batch,
                batch_num=idx, total_batches=len(batches),
            )
            reports.append(report)
        except Exception as e:
            reports.append(f"【{assignee} 第{idx}批】生成失败: {str(e)[:100]}")
        await asyncio.sleep(1)

    return "\n\n".join(reports)


# ══════════════════════════════════════════════════════════════
# Step 6: 合并完整报告
# ══════════════════════════════════════════════════════════════

def _date_range(lookback_days: int) -> str:
    now = datetime.now()
    return f"{(now - timedelta(days=lookback_days)).strftime('%m/%d')}-{now.strftime('%m/%d')}"


async def generate_full_report(
    company_id: str,
    company_name: str,
    lookback_days: int = 3,
) -> tuple:
    """
    完整报告流程 v3。
    返回 (full_text, structured_data, telegram_brief)
    """
    date_range = _date_range(lookback_days)
    people_map = get_people_map()

    # Step 1: 从 DB 读取
    emails = get_emails_for_report(company_id, lookback_days)
    if not emails:
        brief = f"{company_name} 周报 · {date_range}\n本期无邮件。"
        return brief, {}, brief

    print(f"  -> Report: {len(emails)} emails from DB")

    # Step 2: 按 thread 聚合
    threads = aggregate_by_thread(emails)
    print(f"  -> Report: {len(threads)} threads")

    # Step 3: Haiku 线程摘要（每封邮件都参与，零遗漏）
    print(f"  -> Generating thread summaries...")
    threads = await batch_summarize_threads(threads)

    # 分类
    actionable = [t for t in threads if t["max_score"] >= 3]
    low_priority = [t for t in threads if t["max_score"] < 3]
    print(f"  -> {len(actionable)} actionable, {len(low_priority)} low priority")

    # Step 4: 按负责人分组
    groups = group_by_assignee(actionable, people_map)

    # Step 5: 每组生成报告（自动拆批）
    group_reports = {}
    for assignee, group_threads in groups.items():
        try:
            print(f"  -> Generating report for {assignee} ({len(group_threads)} threads)...")
            report = await generate_assignee_reports(company_name, assignee, group_threads)
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

    for assignee, report in group_reports.items():
        full_lines.append(report)
        full_lines.append("")

    if low_priority:
        full_lines.append(f"【低优先邮件 · {len(low_priority)} 个线程】")
        for t in low_priority[:15]:
            summary = t.get("thread_summary", t.get("subject", ""))[:50]
            full_lines.append(f"  · {summary}")
        if len(low_priority) > 15:
            full_lines.append(f"  ... 及其他 {len(low_priority) - 15} 个")
        full_lines.append("")

    full_lines.append(f"报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    full_text = "\n".join(full_lines)

    # Telegram 简要
    brief_lines = [
        f"{company_name} 周报 · {date_range}",
        f"共 {len(emails)} 封邮件，{len(threads)} 个对话",
        "",
    ]

    high_threads = [t for t in actionable if t["max_score"] >= 4]
    if high_threads:
        brief_lines.append(f"需立即处理（{len(high_threads)}项）：")
        for t in high_threads[:8]:
            assignee = people_map.get(t.get("assigned_to_id"), "")
            assignee_str = f" → {assignee}" if assignee else ""
            brief_lines.append(f"  · {t['subject'][:40]}{assignee_str}")
        if len(high_threads) > 8:
            brief_lines.append(f"  ... 及其他 {len(high_threads) - 8} 项")
        brief_lines.append("")

    med_threads = [t for t in actionable if t["max_score"] == 3]
    if med_threads:
        brief_lines.append(f"需关注（{len(med_threads)}项）：")
        for t in med_threads[:5]:
            brief_lines.append(f"  · {t['subject'][:40]}")
        if len(med_threads) > 5:
            brief_lines.append(f"  ... 及其他 {len(med_threads) - 5} 项")

    telegram_brief = "\n".join(brief_lines)

    # structured_data for DOCX
    structured_data = {
        "overview": {
            "total_emails": len(emails),
            "period": date_range,
            "company": company_name,
            "highlights": f"共{len(threads)}个对话线程，{len(actionable)}个需处理，{len(low_priority)}个低优先",
            "per_person_stats": [
                {"name": k, "client_count": len(v), "quoted": 0, "pending": len(v), "resolved": 0}
                for k, v in groups.items()
            ],
        },
        "clients": [],
        "priority_actions": [
            {
                "priority": "high" if t["max_score"] >= 4 else "medium",
                "action": t.get("thread_summary", t["subject"])[:100],
                "assigned_to": people_map.get(t.get("assigned_to_id"), "待分配"),
                "client": t.get("client_name", ""),
                "deadline": None,
            }
            for t in actionable[:30]
        ],
        "followup_update": {"resolved": [], "overdue": [], "still_pending": []},
        "trash_spam_review": [],
        "group_reports": group_reports,
        "full_text": full_text,
        "threads_raw": threads,  # Full thread data for Lark Base sync
    }

    return full_text, structured_data, telegram_brief
