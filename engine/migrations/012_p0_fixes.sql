-- 012: P0 fixes — snooze tracking columns
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS snoozed_at timestamptz;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS snooze_count int DEFAULT 0;
