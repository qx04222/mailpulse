# Email Digest System v2 — Claude Code 执行方案
## 新增：个人专属推送 + 跨期跟进追踪

> 执行方式：`claude "按照 EMAIL_DIGEST_PLAN_V2.md 构建这个系统"`

---

## 系统概述

- **公司群摘要**：每家公司推一条综合摘要到 Telegram 群
- **个人专属摘要**：每个员工收到只含自己相关邮件的私信
- **跟进追踪**：每次运行自动对比上期 action items，标注已解决/超期/新增
- **技术栈**：Python 3.11 · Railway Cron · Supabase · Gmail API · Claude API · Telegram Bot API

---

## 项目结构

```
email-digest/
├── pyproject.toml
├── railway.toml
├── .env.example
├── src/
│   ├── config.py              # 公司 + 人员配置
│   ├── main.py                # 入口（Railway Cron 调用）
│   │
│   ├── sources/
│   │   ├── base.py
│   │   └── gmail_source.py    # 含收件人解析
│   │
│   ├── processors/
│   │   ├── two_pass.py        # Haiku 打分 + Sonnet 汇总
│   │   ├── followup.py        # 跟进对比逻辑
│   │   └── person_filter.py   # 按人过滤邮件
│   │
│   ├── destinations/
│   │   ├── base.py
│   │   └── telegram.py        # Telegram Bot API
│   │
│   └── storage/
│       ├── supabase_client.py
│       └── action_items.py    # action item CRUD
└── scripts/
    └── setup_telegram.py      # 辅助脚本：获取 chat_id
```

---

## TASK 1 — 配置文件

### `pyproject.toml`

```toml
[project]
name = "email-digest"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "google-auth>=2.28.0",
    "google-auth-oauthlib>=1.2.0",
    "google-api-python-client>=2.120.0",
    "anthropic>=0.25.0",
    "httpx>=0.27.0",
    "supabase>=2.4.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "python-dotenv>=1.0.0",
]
```

### `railway.toml`

```toml
[build]
builder = "NIXPACKS"

[[services]]
name = "digest-cron"
startCommand = "python -m src.main"

[services.deploy]
restartPolicyType = "ON_FAILURE"

[services.cron]
# Toronto 时间周一、周四早 8:00，TZ 环境变量自动处理夏令时
schedule = "0 8 * * 1,4"

[services.env]
TZ = "America/Toronto"
```

### `.env.example`

```bash
# Gmail OAuth2
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=

# Claude API
ANTHROPIC_API_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=           # @BotFather 获取
# 各公司群 chat_id（负数，运行 scripts/setup_telegram.py 获取）
TELEGRAM_ARCVIEW_GROUP_ID=
TELEGRAM_ARCPATH_GROUP_ID=
TELEGRAM_TERRAX_GROUP_ID=
TELEGRAM_ARCTREK_GROUP_ID=
TELEGRAM_TORQUEMAX_GROUP_ID=
TELEGRAM_ARCNEXUS_GROUP_ID=

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_KEY=

# 系统行为
DIGEST_LOOKBACK_DAYS=3
FOLLOWUP_OVERDUE_DAYS=7       # 超过几天未处理标记为 overdue
```

---

## TASK 2 — 人员配置 `src/config.py`

```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import Optional


class PersonConfig(BaseModel):
    name: str
    email: str                          # 此人的邮箱地址（用于过滤 To/CC）
    telegram_user_id: str               # Telegram user ID（私信用）
    role: str = "member"                # owner | manager | member
    companies: list[str] = []           # 此人关联的公司名，空=全部


class CompanyConfig(BaseModel):
    name: str
    gmail_label: str
    telegram_group_id: str
    members: list[PersonConfig] = []    # 此公司的成员列表


class Settings(BaseSettings):
    anthropic_api_key: str
    gmail_client_id: str
    gmail_client_secret: str
    gmail_refresh_token: str
    telegram_bot_token: str
    telegram_arcview_group_id: str = ""
    telegram_arcpath_group_id: str = ""
    telegram_terrax_group_id: str = ""
    telegram_arctrek_group_id: str = ""
    telegram_torquemax_group_id: str = ""
    telegram_arcnexus_group_id: str = ""
    supabase_url: str
    supabase_service_key: str
    digest_lookback_days: int = 3
    followup_overdue_days: int = 7

    class Config:
        env_file = ".env"


settings = Settings()

# ============================================================
# 人员主数据 — 在这里维护所有成员信息
# ============================================================
XIN = PersonConfig(
    name="Xin",
    email="xqi@arcview.ca",             # 替换为实际 Gmail 地址
    telegram_user_id="XIN_TELEGRAM_ID", # 运行 setup_telegram.py 获取
    role="owner",
    companies=[],                        # 空 = 接收所有公司
)

NAHRAIN = PersonConfig(
    name="Nahrain",
    email="nahrain@arcview.ca",
    telegram_user_id="NAHRAIN_TELEGRAM_ID",
    role="manager",
    companies=["Arcview"],
)

WARREN = PersonConfig(
    name="Warren",
    email="warren@arctrek.ca",
    telegram_user_id="WARREN_TELEGRAM_ID",
    role="manager",
    companies=["Arctrek"],
)

# ============================================================
# 公司配置 — members 决定谁收到该公司的个人推送
# ============================================================
COMPANIES: list[CompanyConfig] = [
    CompanyConfig(
        name="Arcview",
        gmail_label="Arcview",
        telegram_group_id=settings.telegram_arcview_group_id,
        members=[XIN, NAHRAIN],
    ),
    CompanyConfig(
        name="Arcpath",
        gmail_label="Arcpath",
        telegram_group_id=settings.telegram_arcpath_group_id,
        members=[XIN],
    ),
    CompanyConfig(
        name="Terrax",
        gmail_label="Terrax",
        telegram_group_id=settings.telegram_terrax_group_id,
        members=[XIN],
    ),
    CompanyConfig(
        name="Arctrek",
        gmail_label="Arctrek",
        telegram_group_id=settings.telegram_arctrek_group_id,
        members=[XIN, WARREN],
    ),
    CompanyConfig(
        name="TorqueMax",
        gmail_label="TorqueMax",
        telegram_group_id=settings.telegram_torquemax_group_id,
        members=[XIN],
    ),
    CompanyConfig(
        name="ArcNexus",
        gmail_label="ArcNexus",
        telegram_group_id=settings.telegram_arcnexus_group_id,
        members=[XIN],
    ),
]

# 所有员工去重列表（用于个人推送）
ALL_MEMBERS: list[PersonConfig] = list(
    {p.name: p for c in COMPANIES for p in c.members}.values()
)
```

---

## TASK 3 — Supabase 数据库初始化

在 Supabase SQL Editor 执行：

```sql
-- 每次运行记录
CREATE TABLE IF NOT EXISTS digest_runs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at timestamptz DEFAULT now(),
    run_date date NOT NULL,
    company text NOT NULL,
    total_emails int DEFAULT 0,
    delivered boolean DEFAULT false
);

-- Action items 跟进追踪核心表
CREATE TABLE IF NOT EXISTS action_items (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),

    -- 来源信息
    company text NOT NULL,
    gmail_message_id text,
    gmail_thread_id text,
    subject text NOT NULL,
    sender text,
    received_at timestamptz,

    -- 分配信息
    assigned_to text,                  -- PersonConfig.name，null = 未指定
    priority int DEFAULT 3,            -- 1-5，来自 Haiku 打分

    -- 跟进状态
    -- pending: 待处理
    -- resolved: 已检测到回复
    -- overdue: 超期未处理
    -- manually_done: 手动标记完成
    -- dismissed: 忽略（低优先被归档）
    status text DEFAULT 'pending',
    resolved_at timestamptz,
    resolution_note text,

    -- 首次出现在哪次 run
    first_run_id uuid REFERENCES digest_runs(id),
    -- 最后出现在哪次 run（用于检测是否持续存在）
    last_seen_run_id uuid REFERENCES digest_runs(id),
    -- 连续出现次数
    seen_count int DEFAULT 1
);

CREATE INDEX idx_action_items_company ON action_items(company);
CREATE INDEX idx_action_items_status ON action_items(status);
CREATE INDEX idx_action_items_assigned ON action_items(assigned_to);
CREATE INDEX idx_action_items_thread ON action_items(gmail_thread_id);

-- 自动更新 updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER action_items_updated_at
BEFORE UPDATE ON action_items
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

---

## TASK 4 — Gmail 数据源（含收件人解析）`src/sources/gmail_source.py`

```python
import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass, field

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import settings, COMPANIES


@dataclass
class RawItem:
    id: str
    source_label: str
    subject: str
    body: str
    sender: str
    recipients: list[str]              # To + CC 解析出的所有收件人邮箱
    received_at: datetime
    metadata: dict = field(default_factory=dict)


class GmailSource:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        creds = Credentials(
            token=None,
            refresh_token=settings.gmail_refresh_token,
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
        creds.refresh(Request())
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch(
        self,
        label: str,
        lookback_days: int = 3,
        include_trash: bool = True,
        include_spam: bool = True,
        max_results: int = 100,
    ) -> list[RawItem]:
        service = self._get_service()
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        after_unix = int(cutoff.timestamp())
        items = []

        queries = [(f"label:{label} after:{after_unix}", "inbox", False)]
        if include_trash:
            queries.append((f"label:{label} in:trash after:{after_unix}", "trash", True))
        if include_spam:
            queries.append((f"label:{label} in:spam after:{after_unix}", "spam", True))

        for query, bucket, include_spam_trash in queries:
            result = service.users().messages().list(
                userId="me", q=query,
                maxResults=max_results,
                includeSpamTrash=include_spam_trash,
            ).execute()
            for msg_ref in result.get("messages", []):
                try:
                    msg = service.users().messages().get(
                        userId="me", id=msg_ref["id"], format="full",
                        includeSpamTrash=include_spam_trash,
                    ).execute()
                    item = self._parse(msg, label, bucket)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[Gmail] Error {msg_ref['id']}: {e}")
        return items

    def fetch_personal(self, lookback_days: int = 3) -> list[RawItem]:
        service = self._get_service()
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        after_unix = int(cutoff.timestamp())
        exclude = " ".join(f"-label:{c.gmail_label}" for c in COMPANIES)
        query = f"in:inbox {exclude} after:{after_unix}"
        result = service.users().messages().list(
            userId="me", q=query, maxResults=50
        ).execute()
        items = []
        for msg_ref in result.get("messages", []):
            try:
                msg = service.users().messages().get(
                    userId="me", id=msg_ref["id"], format="full"
                ).execute()
                item = self._parse(msg, "personal", "inbox")
                if item:
                    items.append(item)
            except Exception as e:
                print(f"[Gmail] Error {msg_ref['id']}: {e}")
        return items

    def _parse(self, msg: dict, label: str, bucket: str) -> Optional[RawItem]:
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "(无主题)")
        sender = headers.get("From", "unknown")
        date_str = headers.get("Date", "")

        # 解析收件人（To + CC）
        recipients = []
        for field in ["To", "Cc"]:
            val = headers.get(field, "")
            if val:
                emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', val)
                recipients.extend([e.lower() for e in emails])

        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_str).astimezone(timezone.utc)
        except Exception:
            received_at = datetime.now(timezone.utc)

        body = self._extract_body(msg["payload"])
        return RawItem(
            id=msg["id"],
            source_label=label,
            subject=subject,
            body=body[:3000],
            sender=sender,
            recipients=recipients,
            received_at=received_at,
            metadata={
                "bucket": bucket,
                "thread_id": msg.get("threadId"),
            },
        )

    def _extract_body(self, payload: dict) -> str:
        if "parts" in payload:
            for part in payload["parts"]:
                body = self._extract_body(part)
                if body:
                    return body
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        if payload.get("mimeType") == "text/html":
            data = payload.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                return re.sub(r"<[^>]+>", "", html)
        return ""
```

---

## TASK 5 — Action Items 存储层 `src/storage/action_items.py`

```python
from datetime import datetime, timezone, timedelta
from supabase import create_client
from ..config import settings

db = create_client(settings.supabase_url, settings.supabase_service_key)


def get_pending_items(company: str) -> list[dict]:
    """取本公司所有未解决的 action items"""
    resp = db.table("action_items") \
        .select("*") \
        .eq("company", company) \
        .in_("status", ["pending", "overdue"]) \
        .order("created_at") \
        .execute()
    return resp.data or []


def upsert_action_item(
    company: str,
    gmail_message_id: str,
    gmail_thread_id: str,
    subject: str,
    sender: str,
    received_at: datetime,
    priority: int,
    assigned_to: str | None,
    run_id: str,
) -> dict:
    """
    插入或更新 action item。
    同一 thread_id 视为同一条，更新 seen_count 和 last_seen_run_id。
    """
    existing = db.table("action_items") \
        .select("id, seen_count, status") \
        .eq("gmail_thread_id", gmail_thread_id) \
        .eq("company", company) \
        .in_("status", ["pending", "overdue"]) \
        .execute()

    if existing.data:
        item = existing.data[0]
        overdue = item["status"] == "pending" and _is_overdue(item)
        db.table("action_items").update({
            "seen_count": item["seen_count"] + 1,
            "last_seen_run_id": run_id,
            "status": "overdue" if overdue else item["status"],
            "priority": priority,
        }).eq("id", item["id"]).execute()
        return item
    else:
        new_item = {
            "company": company,
            "gmail_message_id": gmail_message_id,
            "gmail_thread_id": gmail_thread_id,
            "subject": subject,
            "sender": sender,
            "received_at": received_at.isoformat(),
            "priority": priority,
            "assigned_to": assigned_to,
            "status": "pending",
            "first_run_id": run_id,
            "last_seen_run_id": run_id,
            "seen_count": 1,
        }
        resp = db.table("action_items").insert(new_item).execute()
        return resp.data[0]


def mark_resolved_by_thread(gmail_thread_id: str, note: str = "auto: thread replied"):
    """检测到 thread 有新回复，自动标记为已解决"""
    db.table("action_items").update({
        "status": "resolved",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolution_note": note,
    }).eq("gmail_thread_id", gmail_thread_id) \
      .in_("status", ["pending", "overdue"]) \
      .execute()


def create_run(company: str, total_emails: int) -> str:
    """创建本次运行记录，返回 run_id"""
    resp = db.table("digest_runs").insert({
        "run_date": datetime.now(timezone.utc).date().isoformat(),
        "company": company,
        "total_emails": total_emails,
        "delivered": False,
    }).execute()
    return resp.data[0]["id"]


def mark_run_delivered(run_id: str):
    db.table("digest_runs").update({"delivered": True}).eq("id", run_id).execute()


def _is_overdue(item: dict) -> bool:
    created = datetime.fromisoformat(item["created_at"])
    threshold = timedelta(days=settings.followup_overdue_days)
    return (datetime.now(timezone.utc) - created) > threshold
```

---

## TASK 6 — 跟进对比逻辑 `src/processors/followup.py`

```python
from ..sources.gmail_source import RawItem
from ..storage.action_items import get_pending_items, mark_resolved_by_thread


def check_and_update_followups(
    company: str,
    new_items: list[RawItem],
) -> dict:
    """
    对比上期 pending items 与本期新邮件：
    - 如果 thread 在新邮件中出现过（有回复），标记 resolved
    - 返回分类后的跟进状态供摘要使用
    """
    pending = get_pending_items(company)
    if not pending:
        return {"resolved": [], "overdue": [], "still_pending": []}

    # 本期所有 thread_id 集合
    current_threads = {
        item.metadata.get("thread_id")
        for item in new_items
        if item.metadata.get("thread_id")
    }

    resolved = []
    overdue = []
    still_pending = []

    for action in pending:
        tid = action.get("gmail_thread_id")
        if tid and tid in current_threads:
            # thread 有新活动，视为已回复
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


def format_followup_section(followup_status: dict) -> str:
    """格式化跟进状态，供 Sonnet 摘要 prompt 使用"""
    lines = []

    if followup_status["resolved"]:
        lines.append("【本期已解决】")
        for item in followup_status["resolved"]:
            lines.append(f"  ✅ {item['subject']} (来自 {item['sender']})")

    if followup_status["overdue"]:
        lines.append("【超期未处理 🚨】")
        for item in followup_status["overdue"]:
            days = item.get("seen_count", 1) * 3  # 估算天数
            assignee = item.get("assigned_to") or "未指定"
            lines.append(f"  🚨 [{days}天+] {item['subject']} — 负责人：{assignee}")

    if followup_status["still_pending"]:
        lines.append("【上期待处理（持续跟进）】")
        for item in followup_status["still_pending"]:
            assignee = item.get("assigned_to") or "未指定"
            lines.append(f"  ⏳ {item['subject']} — 负责人：{assignee}")

    return "\n".join(lines) if lines else "（无历史待跟进项目）"
```

---

## TASK 7 — 两阶段处理器（含个人过滤）`src/processors/two_pass.py`

```python
import asyncio
import json
from anthropic import Anthropic
from datetime import datetime, timedelta
from ..sources.gmail_source import RawItem
from ..config import PersonConfig

client = Anthropic()

# ── 阶段一：Haiku 打分 prompt ──────────────────────────────────────
SCORE_PROMPT = """对以下邮件输出 JSON，不输出其他任何内容：
{{
  "score": 1-5,
  "reason": "一句话中文说明",
  "one_line": "内容摘要（中文，15字内）",
  "action_needed": true/false,
  "suggested_assignee_email": "邮箱或null"
}}

评分：5=紧急需立即处理 4=重要本周需跟进 3=了解即可 2=通知订阅 1=垃圾广告
action_needed=true 时，从 To/CC 推断最合适的负责人邮箱。

发件人：{sender}
收件人：{recipients}
主题：{subject}
正文：{body}"""

# ── 阶段二：Sonnet 公司摘要 prompt ────────────────────────────────
COMPANY_DIGEST_PROMPT = """请生成 {company} 的邮件汇报（{date_range}），用中文，Telegram Markdown 格式。

*📊 {company} 邮件汇报 · {date_range}*

*🔴 需立即处理*
{high_priority}

*🟡 需要关注*
{medium_priority}

*📋 跟进状态*
{followup_section}

*⚠️ 删除/垃圾箱审查*
{trash_review}

*📝 总结*
（2-3句话）"""

# ── 阶段二：Sonnet 个人摘要 prompt ────────────────────────────────
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
        max_tokens=150,
        messages=[{"role": "user", "content": SCORE_PROMPT.format(
            sender=item.sender,
            recipients=", ".join(item.recipients[:5]),
            subject=item.subject,
            body=item.body[:500],
        )}],
    )
    try:
        result = json.loads(resp.content[0].text)
        result["item"] = item
        return result
    except Exception:
        return {"score": 3, "reason": "解析失败", "one_line": item.subject,
                "action_needed": False, "suggested_assignee_email": None, "item": item}


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


def _fmt_high(entries: list[dict]) -> str:
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


def _fmt_medium(entries: list[dict]) -> str:
    if not entries:
        return "（无）"
    return "\n".join(
        f"• `{e['item'].sender}` | {e['item'].subject} — {e['one_line']}"
        for e in entries
    )


def _fmt_trash(entries: list[dict]) -> str:
    trash = [e for e in entries if e["item"].metadata.get("bucket") in ("trash", "spam")]
    if not trash:
        return "（无需关注）"
    return "\n".join(
        f"• [{e['item'].metadata['bucket'].upper()}] `{e['item'].sender}` | {e['item'].subject} — {e['one_line']}"
        for e in trash
    )


async def generate_company_digest(
    company_name: str,
    items: list[RawItem],
    followup_section: str,
    lookback_days: int = 3,
) -> tuple[str, list[dict]]:
    """
    返回 (摘要文本, 需要写入 action_items 的高优先条目列表)
    """
    deduped = _dedup_by_thread(items)
    scored = await asyncio.gather(*[score_email(item) for item in deduped])

    high   = [s for s in scored if s["score"] >= 4]
    medium = [s for s in scored if s["score"] == 3]
    low    = [s for s in scored if s["score"] <= 2]

    prompt = COMPANY_DIGEST_PROMPT.format(
        company=company_name,
        date_range=_date_range(lookback_days),
        high_priority=_fmt_high(high),
        medium_priority=_fmt_medium(medium),
        followup_section=followup_section,
        trash_review=_fmt_trash(low),
    )

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    # 返回需要追踪的 action items（score >= 4 且 action_needed=True）
    action_items_to_save = [
        s for s in high if s.get("action_needed", False)
    ]
    return resp.content[0].text, action_items_to_save


async def generate_personal_digest(
    person: PersonConfig,
    company_name: str,
    scored_items: list[dict],
    pending_overdue: list[dict],
    lookback_days: int = 3,
) -> str:
    """
    为某个人生成只含其相关邮件的摘要。
    相关性判断：收件人包含此人邮箱，或 Haiku 建议 assignee 是此人。
    """
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
        return ""  # 此人本期无相关邮件，不推送

    personal_high   = [s for s in relevant if s["score"] >= 4]
    personal_medium = [s for s in relevant if s["score"] == 3]

    # 此人负责的超期项
    personal_overdue = [
        item for item in pending_overdue
        if (item.get("assigned_to") or "").lower() == person.name.lower()
    ]

    def fmt_personal_overdue(items: list[dict]) -> str:
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
        personal_overdue=fmt_personal_overdue(personal_overdue),
    )

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
```

---

## TASK 8 — Telegram 推送 `src/destinations/telegram.py`

```python
import httpx
from ..config import settings


def send_message(chat_id: str, text: str) -> bool:
    """
    发消息到 Telegram 群组或个人。
    chat_id: 群组为负数字符串（如 "-1001234567890"），个人为正数字符串。
    支持 Markdown 格式（*粗体* `代码` _斜体_）。
    消息超 4096 字符自动分段发送。
    """
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]

    for chunk in chunks:
        try:
            resp = httpx.post(url, json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
            }, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Telegram] Error sending to {chat_id}: {e}")
            return False
    return True
```

---

## TASK 9 — 主运行器 `src/main.py`

```python
import asyncio
from datetime import datetime

from .config import COMPANIES, ALL_MEMBERS, settings
from .sources.gmail_source import GmailSource
from .processors.two_pass import (
    generate_company_digest,
    generate_personal_digest,
    score_email,
)
from .processors.followup import check_and_update_followups, format_followup_section
from .destinations.telegram import send_message
from .storage.action_items import (
    create_run, mark_run_delivered, upsert_action_item
)

gmail = GmailSource()


async def run_company(company) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {company.name}...")

    # 1. 拉取邮件
    items = gmail.fetch(
        label=company.gmail_label,
        lookback_days=settings.digest_lookback_days,
        include_trash=True,
        include_spam=True,
    )
    print(f"  → {len(items)} emails fetched")

    # 2. 创建本次运行记录
    run_id = create_run(company.name, len(items))

    # 3. 检查跟进状态（对比上期 pending items）
    followup_status = check_and_update_followups(company.name, items)
    followup_section = format_followup_section(followup_status)

    # 4. 生成公司摘要（含 Haiku 打分 + Sonnet 汇总）
    company_summary, action_items_to_save = await generate_company_digest(
        company_name=company.name,
        items=items,
        followup_section=followup_section,
        lookback_days=settings.digest_lookback_days,
    )

    # 5. 存储新的 action items
    for scored in action_items_to_save:
        item = scored["item"]
        # 推断负责人（从 Haiku 建议的 assignee email 匹配到人名）
        suggested_email = (scored.get("suggested_assignee_email") or "").lower()
        assigned_to = None
        for member in company.members:
            if member.email.lower() == suggested_email:
                assigned_to = member.name
                break

        upsert_action_item(
            company=company.name,
            gmail_message_id=item.id,
            gmail_thread_id=item.metadata.get("thread_id", item.id),
            subject=item.subject,
            sender=item.sender,
            received_at=item.received_at,
            priority=scored["score"],
            assigned_to=assigned_to,
            run_id=run_id,
        )

    # 6. 推送公司群摘要
    if company.telegram_group_id:
        success = send_message(company.telegram_group_id, company_summary)
        if success:
            mark_run_delivered(run_id)
        print(f"  → Company group: {'✓' if success else '✗'}")

    # 7. 生成并推送个人摘要
    # 需要 scored items，重新 gather（公司级已做过，这里复用）
    from .processors.two_pass import score_email, _dedup_by_thread
    deduped = _dedup_by_thread(items)
    all_scored = await asyncio.gather(*[score_email(item) for item in deduped])

    overdue_items = followup_status["overdue"] + followup_status["still_pending"]

    for member in company.members:
        personal_summary = await generate_personal_digest(
            person=member,
            company_name=company.name,
            scored_items=list(all_scored),
            pending_overdue=overdue_items,
            lookback_days=settings.digest_lookback_days,
        )
        if personal_summary and member.telegram_user_id:
            ok = send_message(member.telegram_user_id, personal_summary)
            print(f"  → Personal ({member.name}): {'✓' if ok else '✗'}")

    return {"company": company.name, "emails": len(items)}


async def run_all():
    print(f"\n{'='*50}")
    print(f"Email Digest Run — {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"{'='*50}")

    # 并发处理所有公司（各公司独立，互不影响）
    results = await asyncio.gather(
        *[run_company(company) for company in COMPANIES],
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            print(f"ERROR: {r}")
        else:
            print(f"Done: {r['company']} ({r['emails']} emails)")

    print(f"\nRun complete.")


if __name__ == "__main__":
    asyncio.run(run_all())
```

---

## TASK 10 — 辅助脚本 `scripts/setup_telegram.py`

```python
"""
运行此脚本获取 Telegram chat_id：
1. 在 Telegram 搜索 @BotFather → /newbot → 获取 bot token
2. 把 bot 加入各公司群，并发一条消息（任何内容）
3. python scripts/setup_telegram.py
会打印出所有群的 chat_id，填入 .env 即可
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")

resp = httpx.get(f"https://api.telegram.org/bot{token}/getUpdates")
updates = resp.json().get("result", [])

seen = set()
for update in updates:
    msg = update.get("message", {})
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    chat_title = chat.get("title") or chat.get("username") or "private"
    if chat_id and chat_id not in seen:
        seen.add(chat_id)
        print(f"{chat_title}: {chat_id}")
```

---

## TASK 11 — 部署到 Railway

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置 .env（复制 .env.example 填写）
cp .env.example .env

# 3. 初始化 Supabase 表（在 Supabase dashboard SQL Editor 执行 TASK 3 的 SQL）

# 4. 获取 Telegram chat_id
python scripts/setup_telegram.py
# 把输出的 chat_id 填入 .env

# 5. 本地测试一次
python -m src.main

# 6. 推送到 Railway
railway login
railway link
railway up

# 7. 设置环境变量
railway variables set ANTHROPIC_API_KEY=sk-ant-xxx
railway variables set GMAIL_CLIENT_ID=xxx
railway variables set GMAIL_CLIENT_SECRET=xxx
railway variables set GMAIL_REFRESH_TOKEN=xxx
railway variables set TELEGRAM_BOT_TOKEN=xxx
railway variables set TELEGRAM_ARCVIEW_GROUP_ID=-100xxxxxxxxx
# ... 其余公司 group id
railway variables set SUPABASE_URL=https://xxx.supabase.co
railway variables set SUPABASE_SERVICE_KEY=xxx
```

---

## 系统行为总结

### 每次运行（周一/周四 08:00 Toronto）

**公司群收到：**
```
📊 Arcview 邮件汇报 · 03/15–03/18

🔴 需立即处理
• [inbox] cathy@xxx.com | 安装纠纷追款 → nahrain@arcview.ca
  客户要求退款，需要本周内回复

🟡 需要关注
• supplier@xxx.com | Q2 铝型材报价单 — 新报价等待确认

📋 跟进状态
【超期未处理 🚨】
  🚨 [10天+] Warren 物流对接 — 负责人：Nahrain
【本期已解决】
  ✅ Winnipeg 展厅电费账单

📝 总结
本期 8 封邮件，1 条紧急，安装纠纷需优先处理。
```

**Nahrain 私信收到：**
```
👤 Nahrain 的摘要 · Arcview · 03/15–03/18

🔴 你需要处理
• [inbox] cathy@xxx.com | 安装纠纷追款
  客户要求退款，你在 CC，需要本周内回复

⚠️ 你负责的未跟进项
• 🚨 Warren 物流对接 — 已 10天+

📝 小结
1 封需要你直接回复，1 条超期请尽快处理。
```

**Xin 私信收到（跨公司汇总版）：**
```
👤 Xin 的摘要 · Arcview · 03/15–03/18
[Arcview 相关内容...]

👤 Xin 的摘要 · Arcpath · 03/15–03/18
[Arcpath 相关内容...]
```

---

## 成本估算（每次运行）

| 项目 | 用量 | 成本 |
|---|---|---|
| Haiku 打分（6公司 × 约30封去重） | ~180封 × ~300 token | ~$0.003 |
| Sonnet 公司摘要 × 6 | ~4000 token/次 | ~$0.072 |
| Sonnet 个人摘要 × 约5人 × 6公司 | ~800 token/次 | ~$0.036 |
| **合计** | | **~$0.11/次，$0.88/月** |
