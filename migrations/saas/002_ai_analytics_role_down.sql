-- migrations/saas/002_ai_analytics_role_down.sql
-- Rolls back the ai_analytics role created by 002_ai_analytics_role.sql.
-- Safe to run if the role was never granted any real views.

BEGIN;

-- Drop any policies that were granted to ai_analytics
-- (No-op if the role was never used in real RLS policies)
-- If real policies were added, list and drop them here before dropping the role.

COMMIT;

-- Drop the role outside the transaction (roles cannot be dropped inside a transaction block)
DROP ROLE IF EXISTS ai_analytics;
