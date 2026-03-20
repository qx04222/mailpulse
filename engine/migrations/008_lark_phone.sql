-- Lark integration fields
ALTER TABLE companies ADD COLUMN IF NOT EXISTS lark_group_id text;
ALTER TABLE people ADD COLUMN IF NOT EXISTS lark_user_id text;

-- Channel field for multi-channel support (email, phone, chat)
ALTER TABLE threads ADD COLUMN IF NOT EXISTS channel text DEFAULT 'email'
    CHECK (channel IN ('email', 'phone', 'chat', 'meeting'));

-- Call records (future phone AI)
CREATE TABLE IF NOT EXISTS call_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid REFERENCES threads(id),
    company_id uuid NOT NULL REFERENCES companies(id),
    caller text,
    callee text,
    duration_seconds int,
    recording_url text,
    transcript text,
    ai_summary text,
    action_items text[],
    sentiment text CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    created_at timestamptz DEFAULT now()
);

-- Lark message tracking
CREATE TABLE IF NOT EXISTS lark_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id text,
    chat_id text,
    company_id uuid REFERENCES companies(id),
    message_type text,
    card_data jsonb,
    callback_data jsonb,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lark_messages_company ON lark_messages(company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_call_records_company ON call_records(company_id, created_at DESC);
