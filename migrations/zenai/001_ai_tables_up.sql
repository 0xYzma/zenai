-- 001_ai_tables_up.sql
-- ZenAI Integrated Mode Tables (Migration)
-- Applies schema for integrated conversations, messages, and feedback.

BEGIN;

-- Preflight checks could be run manually or by a script, ensuring pgcrypto exists.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Integrated Conversations
CREATE TABLE IF NOT EXISTS integrated_conversations (
    id UUID PRIMARY KEY,
    external_org_id UUID NOT NULL,
    external_user_id UUID NOT NULL,
    title TEXT NOT NULL,
    scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    archived BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_integrated_conversations_owner
    ON integrated_conversations(external_org_id, external_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_integrated_conversations_expiry
    ON integrated_conversations(expires_at);


-- 2. Integrated Messages
CREATE TABLE IF NOT EXISTS integrated_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES integrated_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    insights JSONB NOT NULL DEFAULT '[]'::jsonb,
    chart_type TEXT,
    chart_data JSONB,
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_integrated_messages_conversation
    ON integrated_messages(conversation_id, created_at);


-- 3. Integrated Feedback
CREATE TABLE IF NOT EXISTS integrated_feedback (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL UNIQUE REFERENCES integrated_messages(id) ON DELETE CASCADE,
    external_org_id UUID NOT NULL,
    external_user_id UUID NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Post-migration verification:
-- SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'integrated_%';

COMMIT;
