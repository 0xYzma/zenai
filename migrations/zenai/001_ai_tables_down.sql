-- 001_ai_tables_down.sql
-- Rolls back the ZenAI Integrated Mode tables.

BEGIN;

DROP TABLE IF EXISTS integrated_feedback CASCADE;
DROP TABLE IF EXISTS integrated_messages CASCADE;
DROP TABLE IF EXISTS integrated_conversations CASCADE;

COMMIT;
