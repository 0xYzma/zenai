-- 001_ai_saas_tables_up.sql
-- SaaS Backend AI Tables (Migration)

BEGIN;

-- Preflight checks could be run manually or by a script, ensuring pgcrypto exists.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Plans limit columns (If they don't already exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='plans' AND column_name='max_ai_requests_per_month'
    ) THEN
        ALTER TABLE plans ADD COLUMN max_ai_requests_per_month INT DEFAULT 500;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='plans' AND column_name='max_ai_concurrent_requests'
    ) THEN
        ALTER TABLE plans ADD COLUMN max_ai_concurrent_requests INT DEFAULT 5;
    END IF;
END $$;


-- 2. AI Org Settings
CREATE TABLE IF NOT EXISTS ai_org_settings (
    org_id UUID PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    monthly_request_limit INT,
    max_concurrent_requests INT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ai_monthly_limit CHECK (monthly_request_limit IS NULL OR monthly_request_limit >= 0),
    CONSTRAINT chk_ai_concurrency CHECK (max_concurrent_requests IS NULL OR max_concurrent_requests >= 0)
);


-- 3. AI Usage Monthly
CREATE TABLE IF NOT EXISTS ai_usage_monthly (
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    request_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    failure_count INT NOT NULL DEFAULT 0,
    total_latency_ms BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, period_start)
);


-- 4. AI Active Requests
CREATE TABLE IF NOT EXISTS ai_active_requests (
    request_id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_active_requests_org ON ai_active_requests (org_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_ai_active_requests_user ON ai_active_requests (user_id, expires_at);


-- 5. AI Action Audit
CREATE TABLE IF NOT EXISTS ai_action_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(128) NOT NULL,
    token_id VARCHAR(128),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    location_id UUID REFERENCES locations(id) ON DELETE SET NULL,
    action_type VARCHAR(40) NOT NULL DEFAULT 'tool_read',
    tool_name VARCHAR(80) NOT NULL,
    arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'rejected', 'error')),
    result_rows INT NOT NULL DEFAULT 0 CHECK (result_rows >= 0),
    duration_ms INT NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_action_audit_org_created
    ON ai_action_audit (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_action_audit_request
    ON ai_action_audit (request_id);


-- Post-migration verification:
-- SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'ai_%';

COMMIT;
