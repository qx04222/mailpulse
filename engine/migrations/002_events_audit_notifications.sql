-- =============================================================
-- Events, Audit Log, Notification Rules
-- =============================================================

-- 事件系统：邮件触发的业务事件
CREATE TABLE events (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),
    event_type      text NOT NULL CHECK (event_type IN (
        'new_client', 'new_inquiry', 'quote_sent', 'quote_followup',
        'client_replied', 'overdue_warning', 'overdue_escalation',
        'complaint', 'deal_closed', 'deal_lost',
        'assignment_changed', 'sla_breach', 'digest_completed',
        'custom'
    )),
    severity        text NOT NULL DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    title           text NOT NULL,
    description     text,

    -- 关联实体（可选）
    thread_id       uuid REFERENCES threads(id),
    email_id        uuid REFERENCES emails(id),
    client_id       uuid REFERENCES clients(id),
    person_id       uuid REFERENCES people(id),
    action_item_id  uuid REFERENCES action_items(id),

    -- 元数据
    metadata        jsonb DEFAULT '{}',

    -- 是否已读/已处理
    is_read         boolean NOT NULL DEFAULT false,
    is_resolved     boolean NOT NULL DEFAULT false,
    resolved_by_id  uuid REFERENCES people(id),
    resolved_at     timestamptz,

    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_company ON events(company_id, created_at DESC);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_severity ON events(severity) WHERE severity IN ('warning', 'critical');
CREATE INDEX idx_events_unread ON events(company_id, is_read) WHERE is_read = false;
CREATE INDEX idx_events_person ON events(person_id);
CREATE INDEX idx_events_client ON events(client_id);

-- 审计日志：谁在什么时候做了什么
CREATE TABLE audit_logs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id        uuid REFERENCES people(id),     -- 操作人，null=系统
    actor_name      text NOT NULL DEFAULT 'System',
    action          text NOT NULL CHECK (action IN (
        'create', 'update', 'delete',
        'login', 'logout',
        'assign', 'unassign',
        'role_change', 'status_change',
        'report_generated', 'digest_run',
        'telegram_bind', 'telegram_unbind',
        'export', 'import'
    )),
    entity_type     text NOT NULL,                   -- 'person', 'company', 'client', 'action_item', etc.
    entity_id       uuid,
    entity_name     text,                            -- 可读名称，方便显示

    -- 变更内容
    changes         jsonb,                           -- {"field": {"old": "x", "new": "y"}}
    description     text,                            -- 人类可读描述

    -- 上下文
    ip_address      text,
    user_agent      text,

    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_actor ON audit_logs(actor_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_action ON audit_logs(action, created_at DESC);
CREATE INDEX idx_audit_time ON audit_logs(created_at DESC);

-- 通知规则：每人自定义通知偏好
CREATE TABLE notification_rules (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,

    -- 通知渠道
    channel         text NOT NULL CHECK (channel IN ('telegram', 'web', 'both')),

    -- 规则条件
    event_types     text[] DEFAULT '{}',              -- 空=所有类型
    min_severity    text DEFAULT 'info' CHECK (min_severity IN ('info', 'warning', 'critical')),
    companies       uuid[] DEFAULT '{}',              -- 空=按权限自动
    only_assigned   boolean NOT NULL DEFAULT false,   -- true=只通知分配给自己的

    -- 时间控制
    quiet_hours_start time,                           -- 免打扰开始
    quiet_hours_end   time,                           -- 免打扰结束

    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notification_rules_person ON notification_rules(person_id);
CREATE TRIGGER trg_notification_rules_updated BEFORE UPDATE ON notification_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- SLA 配置
CREATE TABLE sla_configs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),

    -- 响应时间目标（小时）
    first_response_hours  int NOT NULL DEFAULT 24,     -- 首次回复 SLA
    followup_response_hours int NOT NULL DEFAULT 48,   -- 跟进回复 SLA

    -- 升级规则
    escalate_after_hours  int NOT NULL DEFAULT 72,     -- 超过多少小时升级
    escalate_to_id        uuid REFERENCES people(id),  -- 升级给谁

    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_sla_company ON sla_configs(company_id) WHERE is_active = true;
CREATE TRIGGER trg_sla_configs_updated BEFORE UPDATE ON sla_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 站内通知（web 通知中心用）
CREATE TABLE web_notifications (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    event_id        uuid REFERENCES events(id),

    title           text NOT NULL,
    body            text,
    link            text,                              -- 点击跳转的路径

    is_read         boolean NOT NULL DEFAULT false,
    read_at         timestamptz,

    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_web_notifications_person ON web_notifications(person_id, is_read, created_at DESC);

-- 邮件模板
CREATE TABLE email_templates (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid REFERENCES companies(id),    -- null=全局模板

    name            text NOT NULL,
    subject         text NOT NULL,
    body            text NOT NULL,
    category        text DEFAULT 'general',            -- 'quote', 'followup', 'greeting', 'general'

    -- 变量支持：{{client_name}}, {{company_name}}, {{product_type}} 等
    variables       text[] DEFAULT '{}',

    created_by_id   uuid REFERENCES people(id),
    is_active       boolean NOT NULL DEFAULT true,
    use_count       int NOT NULL DEFAULT 0,

    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_email_templates_company ON email_templates(company_id);
CREATE TRIGGER trg_email_templates_updated BEFORE UPDATE ON email_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
