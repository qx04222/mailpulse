-- 手动触发表：admin 写入，engine 消费
CREATE TABLE manual_triggers (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id uuid REFERENCES digest_schedules(id) ON DELETE CASCADE,
    company_id  uuid REFERENCES companies(id),
    status      text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX idx_manual_triggers_pending ON manual_triggers(status) WHERE status = 'pending';
