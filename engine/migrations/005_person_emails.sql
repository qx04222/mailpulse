-- 人员多邮箱支持
CREATE TABLE person_emails (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id   uuid NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    email       text NOT NULL,
    is_primary  boolean NOT NULL DEFAULT false,
    company_id  uuid REFERENCES companies(id),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_person_emails_email ON person_emails(lower(email));
CREATE INDEX idx_person_emails_person ON person_emails(person_id);

-- people 表增加类型字段（区分人员和公共邮箱）
ALTER TABLE people ADD COLUMN IF NOT EXISTS person_type text DEFAULT 'employee'
    CHECK (person_type IN ('employee', 'shared_mailbox', 'system'));

-- 迁移现有数据：把 people.email 写入 person_emails 作为主邮箱
INSERT INTO person_emails (person_id, email, is_primary)
SELECT id, email, true FROM people
ON CONFLICT DO NOTHING;
