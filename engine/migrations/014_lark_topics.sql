-- 014: Lark topic group support — store topic thread_ids per company
CREATE TABLE IF NOT EXISTS lark_topics (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    chat_id     text NOT NULL,
    topic_key   text NOT NULL,  -- 'report', 'urgent', 'alert'
    message_id  text NOT NULL,  -- the root message_id that starts this topic
    created_at  timestamptz DEFAULT now(),
    UNIQUE (company_id, topic_key)
);
