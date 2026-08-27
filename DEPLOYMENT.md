# ZenAI Deployment Guide

This document describes how to deploy ZenAI in integrated mode alongside the NexDokandar SaaS backend. It is a prerequisite for the production pilot.

> **Status:** Documentation complete. Execution against real infrastructure is required before marking provisioning done.

---

## Architecture overview

```
Browser → SaaS Backend (Node.js) → ZenAI (FastAPI, private)
                     ↑                       ↑
             PostgreSQL (SaaS DB)    PostgreSQL (ZenAI DB)
                                         Redis
```

ZenAI is **never reachable from the browser**. All AI traffic flows through the SaaS backend proxy, which mints a short-lived RS256 delegation token per request.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| PostgreSQL 15+ | Separate instance from the SaaS DB |
| Redis 7+ | Required for readiness probe in production |
| Private connectivity | VPC peering / Private Service Connect between SaaS and ZenAI hosts |
| RS256 key pair | Generated once; private key stays on SaaS backend only |

---

## Step 1 — Generate the RS256 key pair

Run once on a secure machine. Store the private key only in the SaaS backend secret manager.

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out ai_delegation_private.pem
openssl rsa -in ai_delegation_private.pem -pubout -out ai_delegation_public.pem
```

- Add `ai_delegation_private.pem` content → `AI_DELEGATION_PRIVATE_KEY` in SaaS backend secrets.
- Add `ai_delegation_public.pem` content → `SAAS_DELEGATION_PUBLIC_KEY` in ZenAI secrets.

---

## Step 2 — Provision ZenAI PostgreSQL and Redis

### PostgreSQL
- Create a dedicated database: `zenai_production`
- Create a dedicated role: `zenai_app` with `CONNECT`, `USAGE`, and table-level grants only
- Enable `pgcrypto`: `CREATE EXTENSION IF NOT EXISTS pgcrypto;`
- No public internet access; VPC-internal only

### Redis
- Single-node Redis 7 in the same VPC
- No public internet access
- Set `maxmemory-policy allkeys-lru`

---

## Step 3 — Apply ZenAI migrations

```bash
psql -h <ZENAI_DB_HOST> -U zenai_app -d zenai_production \
  -f migrations/zenai/001_ai_tables_up.sql
```

Postflight verification:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_name LIKE 'integrated_%';
-- Expected: integrated_conversations, integrated_messages, integrated_feedback
```

---

## Step 4 — Apply SaaS migrations

```bash
# Backup first
pg_dump -h <SAAS_DB_HOST> -U saas_app -d saas_production \
  --schema-only -f backup_pre_ai_$(date +%Y%m%d).sql

psql -h <SAAS_DB_HOST> -U saas_app -d saas_production \
  -f migrations/saas/001_ai_saas_tables_up.sql
```

Postflight verification:
```sql
SELECT table_name FROM information_schema.tables
WHERE table_name LIKE 'ai_%';
-- Expected: ai_org_settings, ai_usage_monthly, ai_active_requests, ai_action_audit

SELECT column_name, column_default
FROM information_schema.columns
WHERE table_name = 'plans'
  AND column_name IN ('max_ai_requests_per_month', 'max_ai_concurrent_requests');
-- Expected defaults: 500, 5
```

---

## Step 5 — Configure ZenAI environment

Copy `backend/.env.example` to the deployment secret manager and fill in:

```env
ZENAI_MODE=integrated
ZENAI_DATABASE_URL=postgresql+asyncpg://zenai_app:<password>@<host>:5432/zenai_production
GEMINI_API_KEY=<google_ai_studio_key>
REDIS_URL=redis://<host>:6379/0
REQUIRE_REDIS_FOR_READINESS=true
SAAS_DELEGATION_PUBLIC_KEY=<contents of ai_delegation_public.pem>
SAAS_DELEGATION_ISSUER=nexdokandar-backend
SAAS_DELEGATION_AUDIENCE=nexdokandar-ai
SAAS_INTERNAL_SERVICE_KEY=<long random string, same as SaaS ZENAI_INTERNAL_SERVICE_KEY>
SAAS_INTERNAL_TOOLS_URL=http://<saas-backend-internal-host>:<port>
ENABLE_CURATED_TOOLS=true
ENABLE_TEXT_TO_SQL=false
CONVERSATION_RETENTION_DAYS=30
AUDIT_RETENTION_DAYS=90
```

---

## Step 6 — Configure SaaS backend environment

Add to the SaaS backend secret manager (reference `.env.ai.example`):

```env
ZENAI_ENABLED=true
ZENAI_INTERNAL_URL=http://<zenai-internal-host>:8000
ZENAI_INTERNAL_SERVICE_KEY=<same long random string as above>
AI_DELEGATION_PRIVATE_KEY=<contents of ai_delegation_private.pem>
AI_DELEGATION_KEY_ID=nexdokandar-ai-1
AI_DEFAULT_MONTHLY_REQUEST_LIMIT=500
AI_DEFAULT_ORG_CONCURRENCY=5
AI_MAX_USER_CONCURRENCY=1
AI_REQUEST_TIMEOUT_MS=60000
```

---

## Step 7 — Node.js streaming tuning

The SaaS backend proxies NDJSON streams. Configure the Node.js HTTP server:

```js
// In server startup
server.keepAliveTimeout = 65_000;  // > load balancer idle timeout (usually 60s)
server.headersTimeout = 66_000;
```

Without this, the load balancer drops long-running AI streams mid-response.

---

## Step 8 — Private connectivity

Ensure ZenAI is **not** reachable from the public internet:

- Deploy ZenAI in the same VPC as the SaaS backend
- Use internal DNS for `ZENAI_INTERNAL_URL`
- Firewall rule: allow inbound TCP 8000 only from SaaS backend IP range
- No public IP on the ZenAI host

---

## Step 9 — Health check verification

```bash
# ZenAI liveness (public)
curl http://<zenai-host>:8000/health/live

# ZenAI readiness (service-key protected)
curl -H "X-ZenAI-Service-Key: <SAAS_INTERNAL_SERVICE_KEY>" \
  http://<zenai-host>:8000/health/ready
# Expected: {"status":"ready","dependencies":{"postgres":"ok","redis":"ok"}}

# SaaS → ZenAI connectivity test
curl -H "X-ZenAI-Service-Key: <key>" \
  http://<zenai-internal-host>:8000/health/ready
```

---

## Rollback

See `ROLLBACK_DRILL.md` for the full rollback procedure and kill-switch commands.

---

## Retention scheduling

Schedule `scripts/prune_retention.py` to run daily from a ZenAI worker:

```bash
# crontab or cloud scheduler
0 2 * * * cd /app && python -m scripts.prune_retention
```

For SaaS-side audit retention, add via pg_cron on the SaaS database:
```sql
SELECT cron.schedule('prune-ai-audit', '0 3 * * *',
  $$DELETE FROM ai_action_audit WHERE created_at < NOW() - INTERVAL '90 days'$$);

SELECT cron.schedule('prune-ai-leases', '*/10 * * * *',
  $$DELETE FROM ai_active_requests WHERE expires_at <= NOW()$$);
```
