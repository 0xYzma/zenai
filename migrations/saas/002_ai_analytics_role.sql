-- 002_ai_analytics_role.sql
-- Run this on the SaaS Database to configure the hardened text-to-SQL role.

-- 1. Create a highly restricted role (cannot log in directly, must be assumed via SET ROLE)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ai_analytics') THEN
        CREATE ROLE ai_analytics WITH NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END
$$;

-- 2. Revoke all default privileges
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ai_analytics;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM ai_analytics;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM ai_analytics;

-- 3. Grant explicit read-only access ONLY to necessary analytic views/tables
-- Example: Assuming views `vw_sales_summary`, `vw_inventory` exist for analytics
-- GRANT SELECT ON vw_sales_summary, vw_inventory TO ai_analytics;

-- 4. Enforce Row-Level Security (RLS) on these views/tables
-- Example implementation for a hypothetical `vw_sales_summary`:
-- ALTER TABLE vw_sales_summary ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_isolation_policy ON vw_sales_summary 
--     FOR SELECT TO ai_analytics
--     USING (
--         org_id = current_setting('rls.tenant_id')::uuid 
--         AND location_id = ANY(string_to_array(current_setting('rls.location_ids'), ',')::uuid[])
--     );

-- Note: The exact GRANT and POLICY statements will depend on the final approved
-- analytics views designed by the database team. The core requirement is that
-- 'ai_analytics' MUST be subjected to NOBYPASSRLS and read-only operations.
