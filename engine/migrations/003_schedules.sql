-- 推送计划表
CREATE TABLE digest_schedules (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    cron_expression text NOT NULL,
    timezone        text NOT NULL DEFAULT 'America/Toronto',
    company_id      uuid REFERENCES companies(id),
    target_type     text NOT NULL CHECK (target_type IN ('group', 'person', 'all_members')),
    target_group_id text,
    target_person_id uuid REFERENCES people(id),
    report_type     text NOT NULL DEFAULT 'brief'
                    CHECK (report_type IN ('brief', 'full_docx', 'full_pdf', 'brief_with_docx')),
    include_sections text[] DEFAULT '{high_priority,followup,summary}',
    lookback_days   int NOT NULL DEFAULT 3,
    is_active       boolean NOT NULL DEFAULT true,
    last_run_at     timestamptz,
    last_run_status text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_schedules_active ON digest_schedules(is_active) WHERE is_active = true;
CREATE TRIGGER trg_schedules_updated BEFORE UPDATE ON digest_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
