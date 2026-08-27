-- Staging Fixtures for AI Insights
-- Matches the actual NexDokandar SaaS schema (db.ts).
--
-- PRODUCTION GUARD: abort immediately if running against a non-staging DB.
DO $$
BEGIN
  IF current_database() NOT LIKE '%staging%'
     AND current_database() NOT LIKE '%test%'
     AND current_database() NOT LIKE '%dev%'
     AND current_database() NOT LIKE '%local%' THEN
    RAISE EXCEPTION
      'Refusing to seed fixtures into database "%". '
      'Name must contain staging/test/dev/local.',
      current_database();
  END IF;
END $$;

BEGIN;

-- ── 1. Plans (ensure AI quotas match ADR: 500/month, 5 concurrent) ────────────
-- Insert a minimal AI-enabled plan if not already present.
INSERT INTO plans (
  id, name, description,
  monthly_price, three_month_price, six_month_price, yearly_price,
  max_ai_requests_per_month, max_ai_concurrent_requests,
  features, is_active
)
VALUES (
  'ai_staging_plan',
  'AI Staging Plan',
  'Used only for AI Insights staging tests',
  0, 0, 0, 0,
  500, 5,
  '{"ai_features": true}'::jsonb,
  true
)
ON CONFLICT (id) DO UPDATE SET
  max_ai_requests_per_month  = 500,
  max_ai_concurrent_requests = 5,
  features = '{"ai_features": true}'::jsonb;

-- ── 2. Subscriptions ───────────────────────────────────────────────────────────
INSERT INTO saas_subscriptions (id, plan_id, status, is_trial)
VALUES
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ai_staging_plan', 'active', false),
  ('bbbbbbbb-0000-0000-0000-000000000001', 'ai_staging_plan', 'active', false)
ON CONFLICT (id) DO NOTHING;

-- ── 3. Organizations ───────────────────────────────────────────────────────────
-- Org A: High-revenue, multi-branch (tests cross-branch scope + isolation).
-- Org B: Low-volume, single branch, high stockout risk (tests different AI answers).
INSERT INTO organizations (id, name, saas_subs_id, default_language, created_at, updated_at)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'AI Staging Org A - High Volume',
   'aaaaaaaa-0000-0000-0000-000000000001', 'en', NOW(), NOW()),
  ('22222222-2222-2222-2222-222222222222', 'AI Staging Org B - Low Volume',
   'bbbbbbbb-0000-0000-0000-000000000001', 'en', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- ── 4. AI org-level settings ───────────────────────────────────────────────────
INSERT INTO ai_org_settings (org_id, is_enabled, monthly_request_limit, max_concurrent_requests)
VALUES
  ('11111111-1111-1111-1111-111111111111', true, 500, 5),
  ('22222222-2222-2222-2222-222222222222', true, 500, 5)
ON CONFLICT (org_id) DO UPDATE SET
  is_enabled              = true,
  monthly_request_limit   = 500,
  max_concurrent_requests = 5;

-- ── 5. Locations ───────────────────────────────────────────────────────────────
INSERT INTO locations (id, org_id, name, is_active, created_at, updated_at)
VALUES
  -- Org A (3 branches — tests multi-branch scope)
  ('10000000-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111',
   'Org A - Main Branch', true, NOW(), NOW()),
  ('10000000-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111',
   'Org A - Second Branch', true, NOW(), NOW()),
  ('10000000-0000-0000-0000-000000000003', '11111111-1111-1111-1111-111111111111',
   'Org A - Third Branch', true, NOW(), NOW()),
  -- Org B (1 branch)
  ('20000000-0000-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222',
   'Org B - Only Branch', true, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- ── 6. Users ───────────────────────────────────────────────────────────────────
-- All passwords are bcrypt of the literal string "StagingPass123!"
-- Generated with bcrypt cost=10. NEVER use these hashes outside staging.
INSERT INTO users (
  id, org_id, full_name, email, password_hash,
  role, assigned_location_id, is_active, created_at, updated_at
)
VALUES
  -- Org A: admin (all branches)
  ('10000000-1000-0000-0000-000000000000',
   '11111111-1111-1111-1111-111111111111',
   'Org A Admin', 'admin@orga.test',
   '$2a$10$8/Qy5BPX.ue5GDf9QW5cROQVCEXUPBQzElJqKxDnhqKHG.8Wse/7i',
   'admin', null, true, NOW(), NOW()),

  -- Org A: manager scoped to Main Branch only (tests location isolation)
  ('10000000-2000-0000-0000-000000000000',
   '11111111-1111-1111-1111-111111111111',
   'Org A Manager - Main', 'manager.main@orga.test',
   '$2a$10$8/Qy5BPX.ue5GDf9QW5cROQVCEXUPBQzElJqKxDnhqKHG.8Wse/7i',
   'manager', '10000000-0000-0000-0000-000000000001', true, NOW(), NOW()),

  -- Org A: manager scoped to Second Branch (should NOT see Main Branch data)
  ('10000000-3000-0000-0000-000000000000',
   '11111111-1111-1111-1111-111111111111',
   'Org A Manager - Second', 'manager.second@orga.test',
   '$2a$10$8/Qy5BPX.ue5GDf9QW5cROQVCEXUPBQzElJqKxDnhqKHG.8Wse/7i',
   'manager', '10000000-0000-0000-0000-000000000002', true, NOW(), NOW()),

  -- Org A: staff with no AI permission in menu_permissions (tests permission denial)
  ('10000000-4000-0000-0000-000000000000',
   '11111111-1111-1111-1111-111111111111',
   'Org A Staff', 'staff@orga.test',
   '$2a$10$8/Qy5BPX.ue5GDf9QW5cROQVCEXUPBQzElJqKxDnhqKHG.8Wse/7i',
   'staff', '10000000-0000-0000-0000-000000000001', true, NOW(), NOW()),

  -- Org B: admin (completely separate tenant — tests cross-tenant isolation)
  ('20000000-1000-0000-0000-000000000000',
   '22222222-2222-2222-2222-222222222222',
   'Org B Admin', 'admin@orgb.test',
   '$2a$10$8/Qy5BPX.ue5GDf9QW5cROQVCEXUPBQzElJqKxDnhqKHG.8Wse/7i',
   'admin', null, true, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- ── Verification queries ───────────────────────────────────────────────────────
-- Run these manually after seeding to confirm correctness:
--
-- SELECT id, name FROM organizations WHERE id IN (
--   '11111111-1111-1111-1111-111111111111',
--   '22222222-2222-2222-2222-222222222222'
-- );
--
-- SELECT id, full_name, email, role, assigned_location_id
-- FROM users WHERE org_id IN (
--   '11111111-1111-1111-1111-111111111111',
--   '22222222-2222-2222-2222-222222222222'
-- );
--
-- SELECT org_id, is_enabled, monthly_request_limit, max_concurrent_requests
-- FROM ai_org_settings WHERE org_id IN (
--   '11111111-1111-1111-1111-111111111111',
--   '22222222-2222-2222-2222-222222222222'
-- );
