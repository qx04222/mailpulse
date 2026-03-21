-- Make Lark the primary push channel
ALTER TABLE digest_runs ADD COLUMN IF NOT EXISTS lark_delivered boolean NOT NULL DEFAULT false;

-- Update notification channels: telegram -> lark
UPDATE notification_rules SET channel = 'lark' WHERE channel = 'telegram';
UPDATE notification_rules SET channel = 'email_lark' WHERE channel = 'both';
