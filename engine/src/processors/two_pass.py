import asyncio
import json
import re
from anthropic import Anthropic
from datetime import datetime, timedelta
from ..sources.gmail_source import RawItem
from ..config import settings

client = Anthropic(api_key=settings.anthropic_api_key)

# ── 阶段一：Haiku 打分 prompt ──────────────────────────────────────
SCORE_PROMPT = """对以下邮件输出 JSON，不输出其他任何内容：
{{
  "score": 1-5,
  "reason": "一句话中文说明",
  "one_line": "内容摘要（中文，15字内）",
  "action_needed": true/false,
  "suggested_assignee_email": "邮箱或null",
  "client_name": "从邮件中提取的客户/联系人姓名",
  "project_address": "项目地址（如有）或null",
  "product_type": "产品类型（如有）或null"
}}

评分：5=紧急需立即处理 4=重要本周需跟进 3=了解即可 2=通知订阅 1=垃圾广告
action_needed=true 时，从 To/CC 推断最合适的负责人邮箱。

发件人：{sender}
收件人：{recipients}
主题：{subject}
正文：{body}"""

# ── 阶段二：Sonnet 结构化分析 prompt ────────────────────────────────
STRUCTURED_DIGEST_PROMPT = """你是一个邮件分析助手。请分析以下 {company} 公司的邮件数据（{date_range}），输出结构化 JSON。

## 公司成员列表
{members_info}

## 邮件数据（已按重要性排序）
{emails_json}

## 历史跟进状态
{followup_section}

请输出以下 JSON 结构（确保是合法 JSON，不要输出其他内容）：
{{
  "overview": {{
    "total_emails": {total_emails},
    "period": "{date_range}",
    "company": "{company}",
    "highlights": "2-3句话中文总结本期重点",
    "per_person_stats": [
      {{"name": "人名", "client_count": 0, "quoted": 0, "pending": 0, "resolved": 0}}
    ]
  }},
  "clients": [
    {{
      "client_name": "客户名称",
      "contact_email": "邮箱",
      "project_address": "地址或null",
      "product_type": "产品类型",
      "assigned_to": "负责人名",
      "status": "new_inquiry|quoting|quoted|negotiating|follow_up|closed|info_only",
      "status_label": "状态中文标签",
      "priority": 1-5,
      "email_count": 0,
      "latest_date": "最新邮件日期",
      "summary": "客户情况详细中文描述（50-100字）",
      "action_needed": "需要采取的具体行动或null",
      "action_deadline": "建议截止时间或null",
      "key_details": ["要点1", "要点2"]
    }}
  ],
  "priority_actions": [
    {{
      "priority": "high|medium|low",
      "action": "具体行动描述",
      "assigned_to": "负责人",
      "client": "相关客户",
      "deadline": "建议截止时间或null"
    }}
  ],
  "followup_update": {{
    "resolved": [{{"subject": "主题", "resolved_by": "解决方式"}}],
    "overdue": [{{"subject": "主题", "days": 0, "assigned_to": "负责人"}}],
    "still_pending": [{{"subject": "主题", "assigned_to": "负责人"}}]
  }},
  "trash_spam_review": [
    {{"sender": "发件人", "subject": "主题", "bucket": "trash或spam", "worth_checking": true, "reason": "原因"}}
  ]
}}"""

# ── 个人摘要 prompt（保持简洁文本输出）────────────────────────────
PERSONAL_DIGEST_PROMPT = """请生成 {name} 的个人邮件摘要（{company} · {date_range}），用中文，Telegram Markdown 格式。

只包含与 {name}（{email}）直接相关的邮件（To/CC 含此人，或内容与其职责相关）。

*👤 {name} 的摘要 · {company} · {date_range}*

*🔴 你需要处理*
{personal_high}

*🟡 你需要了解*
{personal_medium}

*⚠️ 你负责的未跟进项*
{personal_overdue}

*📝 小结*
（1-2句话）"""


async def score_email(item: RawItem) -> dict:
    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": SCORE_PROMPT.format(
            sender=item.sender,
            recipients=", ".join(item.recipients[:5]),
            subject=item.subject,
            body=item.body[:500],
        )}],
    )
    try:
        raw = resp.content[0].text
        json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        result = json.loads(json_match.group() if json_match else raw)
        result["item"] = item
        return result
    except Exception:
        return {"score": 3, "reason": "解析失败", "one_line": item.subject,
                "action_needed": False, "suggested_assignee_email": None,
                "client_name": "", "project_address": None, "product_type": None,
                "item": item}


def _date_range(lookback_days: int) -> str:
    now = datetime.now()
    return f"{(now - timedelta(days=lookback_days)).strftime('%m/%d')}–{now.strftime('%m/%d')}"


def _dedup_by_thread(items: list[RawItem]) -> list[RawItem]:
    seen, result = set(), []
    for item in sorted(items, key=lambda x: x.received_at, reverse=True):
        tid = item.metadata.get("thread_id", item.id)
        if tid not in seen:
            seen.add(tid)
            result.append(item)
    return result


def _scored_to_json(scored_items: list, max_items: int = 30) -> str:
    """将打分后的邮件转为简洁 JSON 供 Sonnet 分析。
    只取 top N 高优先邮件，避免上下文过长导致输出截断。
    """
    # 按 score 降序排列，只取 top N
    sorted_items = sorted(scored_items, key=lambda x: x.get("score", 0), reverse=True)
    top_items = sorted_items[:max_items]

    entries = []
    for s in top_items:
        item = s["item"]
        entries.append({
            "sender": item.sender,
            "subject": item.subject,
            "body_preview": item.body[:200],
            "date": item.received_at.strftime("%Y-%m-%d %H:%M"),
            "bucket": item.metadata.get("bucket", "inbox"),
            "score": s["score"],
            "reason": s["reason"],
            "one_line": s["one_line"],
            "action_needed": s.get("action_needed", False),
            "suggested_assignee": s.get("suggested_assignee_email"),
            "client_name": s.get("client_name", ""),
        })
    return json.dumps(entries, ensure_ascii=False, indent=1)


def _parse_structured_json(text: str) -> dict:
    """从 Sonnet 响应中提取 JSON，带容错"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取 code block 中的 JSON
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*\})\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试找最大的 {} 块
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


async def generate_company_digest(
    company_name: str,
    items: list[RawItem],
    followup_section: str,
    lookback_days: int = 3,
    company=None,
) -> tuple:
    """
    返回 (structured_data: dict, telegram_brief: str, action_items: list[dict], scored: list[dict])
    """
    deduped = _dedup_by_thread(items)
    # 分批打分，避免 429 限速（每批 10 个，间隔 2 秒）
    scored = []
    batch_size = 10
    for i in range(0, len(deduped), batch_size):
        batch = deduped[i:i + batch_size]
        batch_results = await asyncio.gather(*[score_email(item) for item in batch])
        scored.extend(batch_results)
        if i + batch_size < len(deduped):
            await asyncio.sleep(2)
    scored = list(scored)

    # 成员信息
    members_info = "无成员信息"
    if company and company.members:
        members_info = "\n".join(
            f"- {m.name} ({m.email}) — {m.role}"
            for m in company.members
        )

    # 构建结构化分析 prompt
    date_range = _date_range(lookback_days)
    emails_json = _scored_to_json(scored)

    prompt = STRUCTURED_DIGEST_PROMPT.format(
        company=company_name,
        date_range=date_range,
        members_info=members_info,
        emails_json=emails_json,
        followup_section=followup_section,
        total_emails=len(items),
    )

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    structured_data = _parse_structured_json(resp.content[0].text)

    # fallback: 如果 JSON 解析失败，用打分数据构建干净的摘要
    if not structured_data:
        # 生成可读的 fallback 摘要
        high = [s for s in scored if s.get("score", 0) >= 4]
        medium = [s for s in scored if s.get("score", 0) == 3]
        highlights = f"本期共 {len(items)} 封邮件，{len(high)} 封高优先，{len(medium)} 封需关注。"
        if high:
            top3 = high[:3]
            highlights += " 重点: " + "; ".join(
                f"{s['item'].subject[:30]}({s.get('reason', '')})" for s in top3
            )

        structured_data = {
            "overview": {
                "total_emails": len(items),
                "period": date_range,
                "company": company_name,
                "highlights": highlights,
                "per_person_stats": [],
            },
            "clients": [],
            "priority_actions": [
                {
                    "priority": "high",
                    "action": s.get("reason", s["item"].subject),
                    "assigned_to": s.get("suggested_assignee_email", ""),
                    "client": s.get("client_name", ""),
                    "deadline": None,
                }
                for s in high[:10]
            ],
            "followup_update": {"resolved": [], "overdue": [], "still_pending": []},
            "trash_spam_review": [],
        }

    # 生成 Telegram 简要摘要
    telegram_brief = _format_telegram_brief(structured_data, company_name, date_range)

    # action items
    action_items_to_save = [
        s for s in scored if s["score"] >= 4 and s.get("action_needed", False)
    ]

    return structured_data, telegram_brief, action_items_to_save, scored


def _format_telegram_brief(data: dict, company: str, date_range: str) -> str:
    """从结构化数据生成 Telegram 简要消息"""
    overview = data.get("overview", {})
    lines = [
        f"*📊 {company} 邮件周报 · {date_range}*",
        f"本期共 {overview.get('total_emails', 0)} 封邮件",
        "",
    ]

    # 总结
    highlights = overview.get("highlights", "")
    if highlights:
        lines.append(f"📝 {highlights}")
        lines.append("")

    # 高优先行动
    actions = data.get("priority_actions", [])
    high_actions = [a for a in actions if a.get("priority") == "high"]
    if high_actions:
        lines.append("*🔴 需立即处理*")
        for a in high_actions[:5]:
            assigned = a.get("assigned_to", "")
            assigned_str = f" → {assigned}" if assigned else ""
            lines.append(f"• {a['action']}{assigned_str}")
        lines.append("")

    # 中优先
    med_actions = [a for a in actions if a.get("priority") == "medium"]
    if med_actions:
        lines.append("*🟡 需要关注*")
        for a in med_actions[:5]:
            lines.append(f"• {a['action']}")
        lines.append("")

    # 跟进
    followup = data.get("followup_update", {})
    overdue = followup.get("overdue", [])
    if overdue:
        lines.append("*⚠️ 超期未处理*")
        for item in overdue[:3]:
            lines.append(f"• 🚨 {item['subject']} — {item.get('assigned_to', '未指定')}")
        lines.append("")

    return "\n".join(lines)


# ── 旧版格式化函数（个人摘要仍使用）──────────────────────────────
def _fmt_high(entries: list) -> str:
    if not entries:
        return "（无）"
    lines = []
    for e in entries:
        item = e["item"]
        bucket = item.metadata.get("bucket", "inbox")
        assignee = e.get("suggested_assignee_email") or ""
        assignee_str = f" → {assignee}" if assignee else ""
        lines.append(
            f"• [{bucket}] `{item.sender}` | *{item.subject}*{assignee_str}\n"
            f"  {e['reason']}\n"
            f"  _{item.body[:400]}_"
        )
    return "\n\n".join(lines)


def _fmt_medium(entries: list) -> str:
    if not entries:
        return "（无）"
    return "\n".join(
        f"• `{e['item'].sender}` | {e['item'].subject} — {e['one_line']}"
        for e in entries
    )


async def generate_personal_digest(
    person,
    company_name: str,
    scored_items: list,
    pending_overdue: list,
    lookback_days: int = 3,
) -> str:
    person_email = person.email.lower()

    def is_relevant(s: dict) -> bool:
        item = s["item"]
        if person_email in item.recipients:
            return True
        suggested = (s.get("suggested_assignee_email") or "").lower()
        if suggested == person_email:
            return True
        return False

    relevant = [s for s in scored_items if is_relevant(s)]
    if not relevant:
        return ""

    personal_high = [s for s in relevant if s["score"] >= 4]
    personal_medium = [s for s in relevant if s["score"] == 3]

    personal_overdue_items = [
        item for item in pending_overdue
        if (item.get("assigned_to") or "").lower() == person.name.lower()
    ]

    def fmt_personal_overdue(items: list) -> str:
        if not items:
            return "（无）"
        return "\n".join(
            f"• 🚨 {item['subject']} — 已 {item.get('seen_count', 1) * 3}天+"
            for item in items
        )

    prompt = PERSONAL_DIGEST_PROMPT.format(
        name=person.name,
        email=person.email,
        company=company_name,
        date_range=_date_range(lookback_days),
        personal_high=_fmt_high(personal_high),
        personal_medium=_fmt_medium(personal_medium),
        personal_overdue=fmt_personal_overdue(personal_overdue_items),
    )

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
