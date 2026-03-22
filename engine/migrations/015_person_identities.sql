-- 015: Unified person identities — link people to external providers (email, lark, telegram, SaaS)
-- Run against Supabase SQL editor

-- 1. Person identities table — one row per provider+external_id pair
CREATE TABLE IF NOT EXISTS person_identities (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id    uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    provider     text NOT NULL,        -- 'gmail', 'zoho', 'lark', 'arcview_saas', 'arcnexus_saas', 'torquemax_saas', etc.
    external_id  text NOT NULL,        -- email address / SaaS user_id / lark open_id / etc.
    display_name text,                 -- name in that system
    metadata     jsonb DEFAULT '{}',   -- extensible (role, department, etc.)
    is_verified  boolean DEFAULT false,
    created_at   timestamptz DEFAULT now(),
    UNIQUE (provider, external_id)
);
CREATE INDEX IF NOT EXISTS idx_person_identities_person ON person_identities(person_id);
CREATE INDEX IF NOT EXISTS idx_person_identities_lookup ON person_identities(provider, external_id);

-- 2. Migrate existing identity data into person_identities

-- 2a. Lark user IDs
INSERT INTO person_identities (person_id, provider, external_id, display_name, is_verified)
SELECT id, 'lark', lark_user_id, name, true
FROM people
WHERE lark_user_id IS NOT NULL AND lark_user_id != ''
ON CONFLICT (provider, external_id) DO NOTHING;

-- 2b. Primary email from people table
INSERT INTO person_identities (person_id, provider, external_id, display_name, is_verified)
SELECT id, 'gmail', email, name, true
FROM people
WHERE email IS NOT NULL AND email != ''
ON CONFLICT (provider, external_id) DO NOTHING;

-- 2c. Additional emails from person_emails table (skip duplicates)
INSERT INTO person_identities (person_id, provider, external_id, is_verified)
SELECT person_id, 'gmail', email, true
FROM person_emails
WHERE email IS NOT NULL AND email != ''
ON CONFLICT (provider, external_id) DO NOTHING;

-- 2d. Telegram user IDs
INSERT INTO person_identities (person_id, provider, external_id, display_name, is_verified)
SELECT id, 'telegram', telegram_user_id, name, true
FROM people
WHERE telegram_user_id IS NOT NULL AND telegram_user_id != ''
ON CONFLICT (provider, external_id) DO NOTHING;

-- 3. Extend action_items for multi-source ingestion (email, calendar, lark, etc.)
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS source text DEFAULT 'email';
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS source_url text;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS source_event_id text;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS lark_calendar_event_id text;

-- 4. Prevent duplicate ingestion from the same source event
CREATE UNIQUE INDEX IF NOT EXISTS idx_action_items_source_event
ON action_items(source, source_event_id) WHERE source_event_id IS NOT NULL;
