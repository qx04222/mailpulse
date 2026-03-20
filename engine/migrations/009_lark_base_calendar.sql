-- Lark Base (多维表格) and Calendar fields on companies
ALTER TABLE companies ADD COLUMN IF NOT EXISTS lark_base_app_token text;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS lark_base_table_id text;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS lark_calendar_id text;

-- Track synced records to avoid duplicates
CREATE TABLE IF NOT EXISTS lark_base_sync (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id),
    thread_id uuid REFERENCES threads(id),
    record_id text NOT NULL,  -- Lark Base record_id
    synced_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_lark_base_sync_thread
    ON lark_base_sync(company_id, thread_id);

-- Track calendar events to avoid duplicates
CREATE TABLE IF NOT EXISTS lark_calendar_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id),
    thread_id uuid REFERENCES threads(id),
    action_item_id uuid REFERENCES action_items(id),
    event_id text NOT NULL,  -- Lark calendar event_id
    summary text,
    event_time timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_lark_calendar_thread
    ON lark_calendar_events(company_id, thread_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_lark_calendar_action
    ON lark_calendar_events(company_id, action_item_id);
