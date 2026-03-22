-- 011: Secretary features — feature flags, follow-up reminders, weekly reports, calendar proposals
-- Run against Supabase SQL editor

-- 1. Per-company feature toggles
CREATE TABLE IF NOT EXISTS company_features (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    feature_key     text NOT NULL,
    is_enabled      boolean NOT NULL DEFAULT true,
    config          jsonb DEFAULT '{}',
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now(),
    UNIQUE (company_id, feature_key)
);
-- Valid feature_keys: lark_qa, daily_todo, follow_up_reminders, email_search, weekly_report, calendar_sync

-- 2. Follow-up reminders
CREATE TABLE IF NOT EXISTS follow_up_reminders (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),
    thread_id       uuid REFERENCES threads(id),
    email_id        uuid REFERENCES emails(id),
    person_id       uuid NOT NULL REFERENCES people(id),
    client_id       uuid REFERENCES clients(id),
    subject         text NOT NULL,
    reason          text,
    remind_at       timestamptz NOT NULL,
    status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'cancelled', 'done')),
    cancelled_reason text,
    source_email_at timestamptz,
    created_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_followup_pending ON follow_up_reminders(status, remind_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_followup_person ON follow_up_reminders(person_id, status);
CREATE INDEX IF NOT EXISTS idx_followup_thread ON follow_up_reminders(thread_id);

-- 3. Weekly report log
CREATE TABLE IF NOT EXISTS weekly_reports (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),
    person_id       uuid REFERENCES people(id),
    report_type     text NOT NULL DEFAULT 'personal' CHECK (report_type IN ('personal', 'company')),
    period_start    date NOT NULL,
    period_end      date NOT NULL,
    content_json    jsonb,
    lark_message_id text,
    created_at      timestamptz DEFAULT now()
);

-- 4. Calendar event proposals
CREATE TABLE IF NOT EXISTS calendar_proposals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),
    email_id        uuid REFERENCES emails(id),
    person_id       uuid NOT NULL REFERENCES people(id),
    event_title     text NOT NULL,
    event_start     timestamptz,
    event_end       timestamptz,
    location        text,
    attendees       text[],
    raw_text        text,
    status          text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'confirmed', 'rejected', 'created')),
    lark_event_id   text,
    lark_message_id text,
    created_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_calendar_person ON calendar_proposals(person_id, status);

-- 5. Person-level secretary preferences
ALTER TABLE people ADD COLUMN IF NOT EXISTS quiet_hours_start time;
ALTER TABLE people ADD COLUMN IF NOT EXISTS quiet_hours_end time;
ALTER TABLE people ADD COLUMN IF NOT EXISTS daily_todo_time time DEFAULT '09:30';
ALTER TABLE people ADD COLUMN IF NOT EXISTS weekly_report_day int DEFAULT 6;
ALTER TABLE people ADD COLUMN IF NOT EXISTS weekly_report_time time DEFAULT '09:30';
ALTER TABLE people ADD COLUMN IF NOT EXISTS followup_default_days int DEFAULT 3;

-- 6. Seed default features for all active companies
INSERT INTO company_features (company_id, feature_key, is_enabled, config)
SELECT c.id, f.key, true, '{}'::jsonb
FROM companies c
CROSS JOIN (VALUES ('lark_qa'), ('daily_todo'), ('follow_up_reminders'), ('email_search'), ('weekly_report'), ('calendar_sync')) AS f(key)
WHERE c.is_active = true
ON CONFLICT (company_id, feature_key) DO NOTHING;
