import json
import re
from anthropic import Anthropic
from ..sources.gmail_source import GmailSource, RawItem
from ..config import settings

client = Anthropic(api_key=settings.anthropic_api_key)

CONFIDENCE_THRESHOLD = 0.7

CLASSIFY_PROMPT = """你是邮件分类助手。根据发件人、主题和正文判断这封邮件属于哪家公司。

可选公司列表：
{company_list}

如果无法确定属于任何公司，返回 "none"。

输出 JSON，不输出其他内容：
{{"company": "公司名或none", "confidence": 0.0-1.0, "reason": "一句话说明"}}

发件人：{sender}
主题：{subject}
正文：{body}"""


async def reclassify_unlabeled(
    gmail: GmailSource,
    companies: list,
    lookback_days: int = 3,
) -> dict:
    """
    扫描未归类邮件，用 Haiku 判断属于哪家公司，自动打标签。
    返回 {"reclassified": int, "skipped": int, "details": list}
    """
    # 拉取不属于任何公司标签的收件箱邮件
    items = gmail.fetch_personal(lookback_days=lookback_days)
    if not items:
        return {"reclassified": 0, "skipped": 0, "details": []}

    company_names = [c["name"] if isinstance(c, dict) else c.name for c in companies]
    company_list = "\n".join(
        f"- {c['name'] if isinstance(c, dict) else c.name} (Gmail label: {c['gmail_label'] if isinstance(c, dict) else c.gmail_label})"
        for c in companies
    )

    # 构建 label name -> label id 映射
    label_map = {}
    for c in companies:
        name = c["name"] if isinstance(c, dict) else c.name
        label = c["gmail_label"] if isinstance(c, dict) else c.gmail_label
        label_id = gmail.get_label_id(label)
        if label_id:
            label_map[name] = label_id

    reclassified = 0
    skipped = 0
    details = []

    for item in items:
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=100,
                messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(
                    company_list=company_list,
                    sender=item.sender,
                    subject=item.subject,
                    body=item.body[:500],
                )}],
            )
            raw_text = resp.content[0].text
            # 提取 JSON（Haiku 有时会包裹在 markdown code block 里）
            json_match = re.search(r'\{[^}]+\}', raw_text)
            if not json_match:
                skipped += 1
                continue
            result = json.loads(json_match.group())
            company = result.get("company", "none")
            confidence = result.get("confidence", 0)

            if company != "none" and confidence >= CONFIDENCE_THRESHOLD and company in label_map:
                gmail.apply_label(item.id, label_map[company])
                reclassified += 1
                details.append({
                    "subject": item.subject,
                    "sender": item.sender,
                    "assigned_to": company,
                    "confidence": confidence,
                    "reason": result.get("reason", ""),
                })
                print(f"  → Reclassified: {item.subject[:40]} → {company} ({confidence:.0%})")
            else:
                skipped += 1
        except Exception as e:
            print(f"  → Reclassify error: {item.subject[:40]} — {e}")
            skipped += 1

    return {"reclassified": reclassified, "skipped": skipped, "details": details}
