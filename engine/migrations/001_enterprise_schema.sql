-- =============================================================
-- Email Digest Enterprise Schema v2
-- 执行前请备份现有数据
-- =============================================================

-- 先删除旧表的冲突 triggers
DROP TRIGGER IF EXISTS action_items_updated_at ON action_items;
DROP TABLE IF EXISTS email_summaries CASCADE;
DROP TABLE IF EXISTS action_items CASCADE;
DROP TABLE IF EXISTS digest_runs CASCADE;

-- =============================================================
-- 1. PEOPLE & PERMISSIONS
-- =============================================================

CREATE TABLE people (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    email           text NOT NULL UNIQUE,
    telegram_user_id text UNIQUE,
    role            text NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'manager', 'member')),
    is_active       boolean NOT NULL DEFAULT true,
    avatar_url      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE companies (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL UNIQUE,
    gmail_label     text NOT NULL UNIQUE,
    telegram_group_id text,
    logo_url        text,
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE company_members (
    company_id      uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    person_id       uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (company_id, person_id)
);
CREATE INDEX idx_company_members_person ON company_members(person_id);

-- =============================================================
-- 2. CLIENTS (auto-extracted from emails)
-- =============================================================

CREATE TABLE clients (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           text NOT NULL,
    name            text,
    organization    text,
    phone           text,
    status          text NOT NULL DEFAULT 'lead'
                    CHECK (status IN ('lead', 'active', 'quoted', 'negotiating', 'closed', 'inactive')),
    notes           text,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_clients_email_lower ON clients(lower(email));

CREATE TABLE client_company_links (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    company_id      uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    primary_contact_id uuid REFERENCES people(id),
    email_count     int NOT NULL DEFAULT 0,
    last_email_at   timestamptz,
    UNIQUE (client_id, company_id)
);

CREATE INDEX idx_ccl_client ON client_company_links(client_id);
CREATE INDEX idx_ccl_company ON client_company_links(company_id);

-- =============================================================
-- 3. DIGEST RUNS (audit trail)
-- =============================================================

CREATE TABLE digest_runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),
    run_date        date NOT NULL,
    lookback_days   int NOT NULL DEFAULT 3,
    total_emails    int NOT NULL DEFAULT 0,
    new_emails      int NOT NULL DEFAULT 0,
    high_priority   int NOT NULL DEFAULT 0,
    action_items_created int NOT NULL DEFAULT 0,
    telegram_delivered boolean NOT NULL DEFAULT false,
    report_docx_url text,
    report_pdf_url  text,
    started_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz,
    status          text NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'failed')),
    error_message   text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_digest_runs_company_date ON digest_runs(company_id, run_date DESC);

-- =============================================================
-- 4. THREADS (conversation-level tracking)
-- =============================================================

CREATE TABLE threads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_thread_id text NOT NULL UNIQUE,
    company_id      uuid NOT NULL REFERENCES companies(id),
    subject         text,
    status          text NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'waiting_reply', 'resolved', 'stale')),
    initiated_by    text CHECK (initiated_by IN ('us', 'them')),
    client_id       uuid REFERENCES clients(id),
    assigned_to_id  uuid REFERENCES people(id),
    email_count     int NOT NULL DEFAULT 0,
    inbound_count   int NOT NULL DEFAULT 0,
    outbound_count  int NOT NULL DEFAULT 0,
    first_email_at  timestamptz,
    last_email_at   timestamptz,
    last_inbound_at timestamptz,
    last_outbound_at timestamptz,
    avg_our_response_secs int,
    avg_their_response_secs int,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_threads_company ON threads(company_id);
CREATE INDEX idx_threads_status ON threads(status);
CREATE INDEX idx_threads_client ON threads(client_id);
CREATE INDEX idx_threads_last_email ON threads(last_email_at DESC);
CREATE INDEX idx_threads_company_status ON threads(company_id, status);
CREATE INDEX idx_threads_assigned ON threads(assigned_to_id);

-- =============================================================
-- 5. EMAILS (rich per-message storage)
-- =============================================================

CREATE TABLE emails (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_message_id text NOT NULL UNIQUE,
    gmail_thread_id text NOT NULL,
    thread_id       uuid REFERENCES threads(id),
    company_id      uuid NOT NULL REFERENCES companies(id),
    subject         text,
    sender_email    text NOT NULL,
    sender_name     text,
    recipients_to   text[] DEFAULT '{}',
    recipients_cc   text[] DEFAULT '{}',
    received_at     timestamptz NOT NULL,
    body_preview    text,
    body_full       text,
    direction       text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    is_reply        boolean NOT NULL DEFAULT false,
    bucket          text NOT NULL DEFAULT 'inbox'
                    CHECK (bucket IN ('inbox', 'trash', 'spam')),
    client_id       uuid REFERENCES clients(id),
    assigned_to_id  uuid REFERENCES people(id),
    score           smallint CHECK (score BETWEEN 1 AND 5),
    score_reason    text,
    one_line        text,
    action_needed   boolean NOT NULL DEFAULT false,
    client_name     text,
    client_org      text,
    project_address text,
    product_type    text,
    run_id          uuid REFERENCES digest_runs(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_emails_thread ON emails(thread_id);
CREATE INDEX idx_emails_company ON emails(company_id);
CREATE INDEX idx_emails_received ON emails(received_at DESC);
CREATE INDEX idx_emails_company_received ON emails(company_id, received_at DESC);
CREATE INDEX idx_emails_client ON emails(client_id);
CREATE INDEX idx_emails_assigned ON emails(assigned_to_id);
CREATE INDEX idx_emails_action ON emails(company_id, action_needed) WHERE action_needed = true;
CREATE INDEX idx_emails_score ON emails(company_id, score DESC);
CREATE INDEX idx_emails_fts ON emails
    USING gin(to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(body_preview, '')));

-- =============================================================
-- 6. ACTION ITEMS
-- =============================================================

CREATE TABLE action_items (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),
    thread_id       uuid REFERENCES threads(id),
    email_id        uuid REFERENCES emails(id),
    client_id       uuid REFERENCES clients(id),
    title           text NOT NULL,
    description     text,
    priority        text NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('high', 'medium', 'low')),
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'in_progress', 'overdue', 'resolved', 'dismissed')),
    assigned_to_id  uuid REFERENCES people(id),
    due_date        date,
    resolved_at     timestamptz,
    resolution_note text,
    first_seen_run_id uuid REFERENCES digest_runs(id),
    last_seen_run_id  uuid REFERENCES digest_runs(id),
    seen_count      int NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_action_items_company_status ON action_items(company_id, status);
CREATE INDEX idx_action_items_assigned ON action_items(assigned_to_id, status);
CREATE INDEX idx_action_items_thread ON action_items(thread_id);
CREATE INDEX idx_action_items_due ON action_items(due_date) WHERE status IN ('pending', 'in_progress');

-- =============================================================
-- 7. AI ANALYSIS CACHE
-- =============================================================

CREATE TABLE ai_company_analyses (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      uuid NOT NULL REFERENCES companies(id),
    run_id          uuid NOT NULL REFERENCES digest_runs(id),
    analysis_json   jsonb NOT NULL,
    highlights      text,
    period          text,
    telegram_brief  text,
    model_used      text DEFAULT 'claude-sonnet-4-5',
    token_count     int,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_company_latest ON ai_company_analyses(company_id, created_at DESC);
CREATE UNIQUE INDEX idx_ai_company_run ON ai_company_analyses(company_id, run_id);

CREATE TABLE ai_client_summaries (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       uuid NOT NULL REFERENCES clients(id),
    company_id      uuid NOT NULL REFERENCES companies(id),
    run_id          uuid NOT NULL REFERENCES digest_runs(id),
    summary         text NOT NULL,
    status          text,
    action_needed   text,
    priority        smallint CHECK (priority BETWEEN 1 AND 5),
    key_details     text[],
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_client_summary ON ai_client_summaries(client_id, created_at DESC);
CREATE INDEX idx_ai_client_company ON ai_client_summaries(company_id, run_id);

-- =============================================================
-- 8. AUTO-UPDATE TRIGGERS
-- =============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_people_updated BEFORE UPDATE ON people
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_companies_updated BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_clients_updated BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_threads_updated BEFORE UPDATE ON threads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_action_items_updated BEFORE UPDATE ON action_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================
-- 9. SEED DATA
-- =============================================================

INSERT INTO companies (name, gmail_label) VALUES
    ('Arcview', 'Arcview'),
    ('Arcpath', 'Arcpath'),
    ('Terrax', 'Terrax'),
    ('Arctrek', 'Arctrek'),
    ('TorqueMax', 'TorqueMax'),
    ('ArcNexus', 'ArcNexus');

INSERT INTO people (name, email, role) VALUES
    ('Xin', 'xqi@arcview.ca', 'owner'),
    ('Nahrain', 'nahrain@arcview.ca', 'manager'),
    ('Warren', 'warren@arctrek.ca', 'manager');

-- Xin → all companies
INSERT INTO company_members (company_id, person_id)
SELECT c.id, p.id FROM companies c, people p WHERE p.name = 'Xin';

-- Nahrain → Arcview
INSERT INTO company_members (company_id, person_id)
SELECT c.id, p.id FROM companies c, people p
WHERE p.name = 'Nahrain' AND c.name = 'Arcview';

-- Warren → Arctrek
INSERT INTO company_members (company_id, person_id)
SELECT c.id, p.id FROM companies c, people p
WHERE p.name = 'Warren' AND c.name = 'Arctrek';
