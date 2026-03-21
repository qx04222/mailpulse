# MailPulse 改进方案：AI 秘书 + 精准分类

> 全栈工程师 + 资深产品经理视角
> 2026-03-21

---

## 一、问题诊断

### 问题 1：邮件公司归属不准（跨域名问题）

**实际场景**：
```
1. 客户发邮件到 info@arcnexus.ca
2. 该邮件通过转发规则 → 到达中央 Gmail 邮箱 → 被打上 "ArcNexus" Label ✓
3. Belle 用她的主邮箱 belle@arcview.ca 回复这个客户
4. 回复邮件到达 Gmail → 被打上 "Arcview" Label ✗
5. 结果：
   - ArcNexus 群看不到 Belle 的回复
   - Arcview 群收到了一封不相关的 ArcNexus 业务邮件
```

**根因**：
- 所有公司邮件通过转发汇集到一个 Gmail 邮箱
- 转发地址是员工的主域名邮箱（如 arcview.ca）
- Gmail 按转发地址/Label 规则分类 → 回复邮件被归到主域名对应的公司
- 代码按 `gmail_label` 拉取邮件 → 无法跨公司修正

**影响**：每个员工回复其他公司业务的邮件，都会被归错

### 问题 2：AI 分类不 100% 准确时的安全网

**现状**：
- AI 打分 + 分配负责人 → 准确率约 80-90%
- 错误分配 → 该收到的人没收到 → 客户被遗漏
- 正确分配 → 但员工没看到 DM → 也会遗漏

**矛盾**：不增加员工负担 vs 不能错过重要信息

---

## 二、解决方案

### 方案 A：线程级跨公司修正（解决问题 1）

**核心思路**：每封邮件处理时，检查它所属的 Gmail thread 是否已经在其他公司下有记录。如果有，将这封邮件"复制"到正确的公司。

#### 原理

```
公司 A 处理 Arcview Label 下的邮件：
  → 遇到一封 Belle 回复 ArcNexus 客户的邮件
  → 检查 gmail_thread_id → 发现 threads 表里这个 thread 属于 ArcNexus
  → 将这封邮件也关联到 ArcNexus（双重归属）
  → ArcNexus 的 digest 中包含这封邮件
```

#### 检测规则（优先级从高到低）

1. **线程历史绑定**（最可靠）：
   - 该 `gmail_thread_id` 在 `threads` 表中已存在 → 使用已有的 `company_id`
   - 适用场景：客户先发到 arcnexus → 建了 thread → Belle 用 arcview 回复 → thread 已知属于 ArcNexus

2. **收件人域名检测**：
   - 邮件的 To/CC 中包含某公司域名的邮箱（如 CC: info@arcnexus.ca）
   - 用 `company_domains` 映射反查公司

3. **`person_emails` 表反查**：
   - 发件人 belle@arcview.ca → 查 `person_emails` 表 → 发现 Belle 也有 belle@arcnexus.ca
   - 结合邮件上下文（收件人、主题）判断真实公司

4. **Gmail Label 兜底**：
   - 以上都无法判断 → 保持原始 Label 分类

#### 实现：跨公司邮件桥接

```python
# 在 main.py 每封邮件处理后执行
def bridge_email_to_true_company(
    gmail_thread_id: str,
    email_row: dict,
    current_company_id: str,
    item: RawItem,
    company_domains: dict,
):
    """检查邮件是否应该同时属于另一个公司"""

    # 规则 1：线程历史
    existing_thread = get_thread_by_gmail_id(gmail_thread_id)
    if existing_thread and existing_thread["company_id"] != current_company_id:
        true_company_id = existing_thread["company_id"]
        # 在真实公司下也创建/更新邮件记录
        _mirror_email_to_company(email_row, item, true_company_id, existing_thread["id"])
        return true_company_id

    # 规则 2：收件人域名
    for recip in item.recipients:
        domain = recip.split("@")[-1].lower()
        if domain in company_domains:
            detected_company = company_domains[domain]
            if detected_company != current_company_id:
                # 在检测到的公司下也创建 thread + 邮件记录
                _mirror_email_to_company(email_row, item, detected_company)
                return detected_company

    return current_company_id  # 无需桥接
```

**关键**：不是"移动"邮件，而是"桥接"——邮件同时出现在原始公司和真实公司的 digest 中。这样不会遗漏。

#### DB 改动

```sql
-- emails 表加字段
ALTER TABLE emails
  ADD COLUMN bridged_from_company_id uuid REFERENCES companies(id),
  ADD COLUMN true_company_id uuid REFERENCES companies(id);

-- 索引
CREATE INDEX idx_emails_true_company ON emails(true_company_id);
```

#### 推送改动

报告生成时，按 `true_company_id`（如果有）或 `company_id` 汇总：
- ArcNexus 的 digest → 包含所有 `true_company_id = arcnexus` 的邮件
- 即使这些邮件是从 Arcview Label 下拉取的

---

### 方案 B：三级通知 + 兜底安全网（解决问题 2）

#### Level 1：群汇总（已完成 ✅）
- 只发概览卡片 + DOCX 报告
- 不发个人任务卡片

#### Level 2：个人 DM（已完成 ✅）
- 分配给该人的线程卡片（带交互按钮）
- 个人文本摘要

#### Level 3：兜底升级机制（新增）

```
AI 分配给 Belle → DM 发给 Belle
  ├── Belle 标记"已处理" → 完成
  └── Belle 超时没反应（下次 digest 运行时检查）→ 自动升级：
      ├── 再次 DM 提醒 Belle（加 ⚠️ 标记）
      └── 同时推送到群里（所有人可见）
          └── 任何人可以"认领"

AI 无法确定负责人 → 直接推到群
  └── 任何人可以"认领"
```

**实现**：

```python
# 每次 digest 开头，检查上次推送但未确认的高优任务
def check_unacknowledged_tasks(company_id, lark_group_id):
    """升级未确认的任务到群"""
    pending = db.table("action_items") \
        .select("*, people(name, lark_user_id)") \
        .eq("company_id", company_id) \
        .eq("dm_acknowledged", False) \
        .eq("escalated_to_group", False) \
        .not_.is_("dm_sent_at", None) \
        .gte("priority", "high") \
        .execute()

    for item in pending.data:
        dm_sent = datetime.fromisoformat(item["dm_sent_at"])
        hours_since = (now - dm_sent).total_seconds() / 3600

        if hours_since >= 24:
            # 升级到群
            card = build_escalation_card(item)
            send_card_message(lark_group_id, card)

            db.table("action_items").update({
                "escalated_to_group": True
            }).eq("id", item["id"]).execute()
```

**卡片交互按钮**：
```
┌─────────────────────────────────────────┐
│ ⚠️ 超时未处理 | 客户询价 - Niall        │
│                                         │
│ 原负责人：Belle Ren（24h 未确认）         │
│ 优先级：🔴 紧急                          │
│                                         │
│ [✅ 我来处理]  [👤 重新分配]              │
└─────────────────────────────────────────┘
```

需要 Lark Bot 事件回调（webhook）来处理按钮点击。

#### DB 迁移

```sql
ALTER TABLE action_items
  ADD COLUMN dm_sent_at timestamptz,
  ADD COLUMN dm_acknowledged boolean DEFAULT false,
  ADD COLUMN escalated_to_group boolean DEFAULT false;
```

---

### 方案 C：智能分配持续优化

提高 AI 分配准确率，从根源减少需要兜底的次数。

#### C1：客户-负责人绑定

```sql
-- clients 表已有，可以加 primary_contact_id
ALTER TABLE clients
  ADD COLUMN primary_contact_id uuid REFERENCES people(id);
```

逻辑：某客户的历史邮件大多是 Belle 处理的 → 新邮件自动分配给 Belle。

```python
# 在 scoring 前，先查客户历史分配
def get_preferred_assignee(client_id):
    """根据历史记录找到该客户的常用负责人"""
    resp = db.table("emails") \
        .select("assigned_to_id") \
        .eq("client_id", client_id) \
        .not_.is_("assigned_to_id", None) \
        .order("received_at", desc=True) \
        .limit(10) \
        .execute()

    # 找出出现最多的 assigned_to_id
    counts = Counter(r["assigned_to_id"] for r in resp.data)
    if counts:
        return counts.most_common(1)[0][0]
    return None
```

#### C2：线程延续分配

同一个 thread 的后续邮件 → 继续分配给之前的负责人（已部分实现在 `upsert_thread` 中）。

#### C3：AI Prompt 增强

在 scoring prompt 中注入该公司的员工列表和常见分配规则：
```
团队成员：
- Belle Ren (belle@arcview.ca) — 负责 Arcview 和 ArcNexus 客户报价
- Sage Cui (sage@arcview.ca) — 负责 TorqueMax 和 Arcpath 技术支持
- Liliana Lei — 负责 Arcview 客户售后

请根据邮件内容，从以上成员中选择最合适的负责人。
```

---

## 三、实施路线图

### Phase 1：跨公司线程桥接（2-3 天）⭐ 最高优先

直接解决"回复邮件归错公司"的核心问题。

**步骤**：
1. DB 迁移：`emails` 加 `true_company_id`, `bridged_from_company_id`
2. 新增 `bridge_email_to_true_company()` 函数
3. 修改 `main.py`：每封邮件处理后执行桥接检测
4. 修改报告生成：按 `true_company_id` 汇总
5. 修改推送逻辑：桥接的邮件推送到正确的公司群

### Phase 2：卡片交互按钮（1-2 天）

**步骤**：
1. 更新 `lark_cards.py`：线程卡片加 "✅ 已处理" / "👤 转交" 按钮
2. 设置 Lark Bot 事件回调 URL
3. 新增回调处理路由（在 engine bot server 中）
4. 按钮点击 → 更新 `action_items` 状态

### Phase 3：兜底升级机制（1-2 天）

**步骤**：
1. DB 迁移：`action_items` 加 `dm_sent_at`, `dm_acknowledged`, `escalated_to_group`
2. 推送 DM 后记录 `dm_sent_at`
3. Digest 开头检查未确认任务 → 升级到群
4. 新增升级卡片模板

### Phase 4：智能分配优化（持续）

**步骤**：
1. 客户-负责人绑定：历史数据分析 → 自动设置
2. AI Prompt 增强：注入团队成员信息
3. 线程延续分配：已有基础，完善边界情况

---

## 四、效果预期

| 改进 | 解决问题 | 预期效果 |
|------|---------|---------|
| 线程桥接 | 邮件归错公司 | 回复邮件出现在正确的公司群 |
| 个人 DM 任务卡片 | 群里太吵 | 群消息减少 60%+ |
| 兜底升级 | AI 分配不准 | 重要信息 0 遗漏率 |
| 客户-负责人绑定 | 分配不准 | 分配准确率 80% → 95%+ |

---

## 五、数据流改进后全景

```
Gmail (所有公司邮件汇集)
  │
  ├── Label: Arcview    ─→ fetch ─→ 处理每封邮件
  ├── Label: ArcNexus   ─→ fetch ─→ 处理每封邮件
  ├── Label: TorqueMax  ─→ fetch ─→ 处理每封邮件
  └── ...
                                      │
                              ┌───────┴────────┐
                              │ 线程桥接检测     │  ← 新增
                              │                │
                              │ thread 已存在？  │
                              │ → 使用已有公司   │
                              │                │
                              │ 收件人域名？     │
                              │ → 检测真实公司   │
                              └───────┬────────┘
                                      │
                          ┌───────────┴───────────┐
                          │ true_company_id        │
                          │ (可能 ≠ gmail_label)    │
                          └───────────┬───────────┘
                                      │
                    ┌─────────────────┬┴──────────────────┐
                    │                 │                    │
                    ▼                 ▼                    ▼
          ┌──────────────┐ ┌──────────────┐    ┌──────────────┐
          │ 群：汇总      │ │ 个人 DM      │    │ 兜底升级      │
          │              │ │              │    │              │
          │ 概览卡片      │ │ 分配的任务    │    │ 24h 未确认    │
          │ DOCX 报告    │ │ (带按钮)     │    │ → 推到群      │
          │ 未分配的紧急  │ │ 个人摘要     │    │ 任何人可认领  │
          └──────────────┘ └──────────────┘    └──────────────┘
```

---

*MailPulse = 每个员工的 AI 邮件秘书 × 跨公司信息桥 × 团队安全网*
