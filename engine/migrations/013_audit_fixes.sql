-- 013: DB Audit fixes — missing columns, CHECK constraints, indexes
-- Run in Supabase SQL Editor

-- ═══════════════════════════════════════════════════════════
-- 1. action_items: 5 missing columns for DM tracking & escalation
-- ═══════════════════════════════════════════════════════════
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS dm_sent_at timestamptz;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS dm_acknowledged boolean DEFAULT false;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS dm_acknowledged_at timestamptz;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS escalated_to_group boolean DEFAULT false;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS escalated_at timestamptz;
ALTER TABLE action_items ADD COLUMN IF NOT EXISTS dm_message_id text;

-- Index for escalation query (filtered by dm_sent_at + dm_acknowledged)
CREATE INDEX IF NOT EXISTS idx_action_items_dm_pending
  ON action_items(company_id, dm_sent_at)
  WHERE dm_acknowledged = false AND escalated_to_group = false AND dm_sent_at IS NOT NULL;

-- ═══════════════════════════════════════════════════════════
-- 2. emails: 2 missing columns for cross-company bridging
-- ═══════════════════════════════════════════════════════════
ALTER TABLE emails ADD COLUMN IF NOT EXISTS true_company_id uuid REFERENCES companies(id);
ALTER TABLE emails ADD COLUMN IF NOT EXISTS bridged_from_company_id uuid REFERENCES companies(id);

-- Index for gmail_thread_id (used in thread counting + dedup)
CREATE INDEX IF NOT EXISTS idx_emails_gmail_thread ON emails(gmail_thread_id);

-- ═══════════════════════════════════════════════════════════
-- 3. people: 5 missing columns for Lark sync
-- ═══════════════════════════════════════════════════════════
ALTER TABLE people ADD COLUMN IF NOT EXISTS lark_departments text[];
ALTER TABLE people ADD COLUMN IF NOT EXISTS lark_job_title text;
ALTER TABLE people ADD COLUMN IF NOT EXISTS lark_mobile text;
ALTER TABLE people ADD COLUMN IF NOT EXISTS lark_employee_no text;
ALTER TABLE people ADD COLUMN IF NOT EXISTS lark_synced_at timestamptz;

-- ═══════════════════════════════════════════════════════════
-- 4. events.event_type: add 'urgent_notify' to CHECK constraint
-- Drop old constraint and recreate with new value
-- ═══════════════════════════════════════════════════════════
ALTER TABLE events DROP CONSTRAINT IF EXISTS events_event_type_check;
ALTER TABLE events ADD CONSTRAINT events_event_type_check CHECK (
  event_type IN (
    'new_client', 'new_inquiry', 'quote_sent', 'quote_followup',
    'client_replied', 'overdue_warning', 'overdue_escalation',
    'complaint', 'deal_closed', 'deal_lost',
    'assignment_changed', 'sla_breach', 'digest_completed',
    'urgent_notify', 'custom'
  )
);

-- ═══════════════════════════════════════════════════════════
-- 5. notification_rules.channel: update CHECK for Lark values
-- ═══════════════════════════════════════════════════════════
ALTER TABLE notification_rules DROP CONSTRAINT IF EXISTS notification_rules_channel_check;
ALTER TABLE notification_rules ADD CONSTRAINT notification_rules_channel_check CHECK (
  channel IN ('telegram', 'web', 'both', 'lark', 'email_lark', 'email')
);

-- ═══════════════════════════════════════════════════════════
-- 6. Missing index: events.email_id (for hourly sync dedup)
-- ═══════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_events_email ON events(email_id) WHERE email_id IS NOT NULL;

-- ═══════════════════════════════════════════════════════════
-- 7. Missing index: calendar_proposals.email_id (for dedup)
-- ═══════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_calendar_proposals_email ON calendar_proposals(email_id) WHERE email_id IS NOT NULL;
