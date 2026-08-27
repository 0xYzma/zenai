-- 001_ai_saas_tables_down.sql
-- Rolls back the SaaS Backend AI tables.

BEGIN;

DROP TABLE IF EXISTS ai_action_audit CASCADE;
DROP TABLE IF EXISTS ai_active_requests CASCADE;
DROP TABLE IF EXISTS ai_usage_monthly CASCADE;
DROP TABLE IF EXISTS ai_org_settings CASCADE;

-- Note: We generally don't drop columns in rollback to prevent data loss, 
-- but if strictly required, uncomment the following block:
/*
DO $$
BEGIN
    ALTER TABLE plans DROP COLUMN IF EXISTS max_ai_requests_per_month;
    ALTER TABLE plans DROP COLUMN IF EXISTS max_ai_concurrent_requests;
END $$;
*/

COMMIT;
