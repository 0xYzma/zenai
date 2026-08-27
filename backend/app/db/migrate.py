"""
ZenAI Database Schema — §11

Run this script to create all ZenAI tables in your own Postgres database.
Usage: python -m app.db.migrate
"""
import asyncio
import asyncpg
from app.core.config import get_settings

SCHEMA_SQL = """
-- §11 Database Schema (ZenAI's own data)

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
    schema_version INT DEFAULT 1,
    timezone TEXT DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'viewer')),
    invited_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    host TEXT NOT NULL,
    port INT NOT NULL DEFAULT 5432,
    db_name TEXT NOT NULL,
    encrypted_credentials TEXT NOT NULL,
    read_only_role TEXT,
    status TEXT DEFAULT 'connected',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS schema_maps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    is_nullable BOOLEAN DEFAULT true,
    is_primary_key BOOLEAN DEFAULT false,
    is_foreign_key BOOLEAN DEFAULT false,
    references_table TEXT,
    references_column TEXT,
    sample_values JSONB DEFAULT '[]'::jsonb,
    column_comment TEXT,
    description TEXT,
    embedding_id TEXT,
    last_synced_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(workspace_id, table_name, column_name)
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    summary TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    generated_sql TEXT,
    result_summary JSONB,
    chart_type TEXT,
    chart_data JSONB,
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    sql_text TEXT NOT NULL,
    row_count INT DEFAULT 0,
    execution_ms INT DEFAULT 0,
    estimated_cost NUMERIC,
    status TEXT CHECK (status IN ('success', 'blocked', 'error', 'retried')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS query_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    cache_key TEXT NOT NULL,
    answer JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    UNIQUE(workspace_id, cache_key)
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_type TEXT NOT NULL,
    version TEXT NOT NULL,
    template TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(prompt_type, version)
);

CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES chat_messages(id) ON DELETE CASCADE,
    rating TEXT CHECK (rating IN ('up', 'down')),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Integrated SaaS conversations use external immutable identities and never
-- depend on standalone ZenAI users/workspaces.
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

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces(owner_id);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_members_workspace ON workspace_members(workspace_id);
CREATE INDEX IF NOT EXISTS idx_connections_workspace ON connections(workspace_id);
CREATE INDEX IF NOT EXISTS idx_schema_maps_workspace ON schema_maps(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace ON chat_sessions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_workspace ON query_logs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_query_cache_key ON query_cache(workspace_id, cache_key);
CREATE INDEX IF NOT EXISTS idx_integrated_conversations_owner
    ON integrated_conversations(external_org_id, external_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_integrated_conversations_expiry
    ON integrated_conversations(expires_at);
CREATE INDEX IF NOT EXISTS idx_integrated_messages_conversation
    ON integrated_messages(conversation_id, created_at);
"""


async def migrate():
    settings = get_settings()
    # Use the ZenAI database URL (not the target client DB)
    db_url = settings.zenai_database_url
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(SCHEMA_SQL)
        print("Migration complete — all §11 tables created.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
