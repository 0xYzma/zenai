# ZenAI + NexDokandar: Claude Continuation Plan

**Prepared:** 2026-08-19  
**Purpose:** Continue the integration after Codex slices 1-9 without redoing completed work.  
**Required slices remaining:** 7  
**Optional slices remaining:** 1 (hardened text-to-SQL)

## 1. Repository locations

| Component | Absolute path |
|---|---|
| ZenAI | `D:\PieceOfShit\Projects\AI\ZenAI\zenai` |
| SaaS backend | `D:\PieceOfShit\SaaS\saas-backend-v1\saas-backend-v1` |
| SaaS frontend | `D:\PieceOfShit\SaaS\saas-admin-frontend-v1\saas-admin-frontend-v1` |

Read these documents before editing:

1. `ZENAI_SAAS_INTEGRATION_IMPLEMENTATION_PLAN.md`
2. `ZENAI_SAAS_INTEGRATION_TASKLIST.md`
3. This continuation plan

## 2. Current verified baseline

Slices 1-9 are complete. Do not recreate them.

- ZenAI is a private FastAPI service behind the SaaS Node/Express gateway.
- The browser never calls ZenAI directly.
- RS256 delegation, service-key authentication, organization/user/location scope, permissions, features, and token-age checks exist.
- Nine curated read-only tools exist.
- Text-to-SQL is disabled for integrated mode.
- Chat streaming, cancellation, history, feedback, CSV export, charts, filters, proactive cards, quota, concurrency, audit, usage, health, and metrics foundations exist.
- ZenAI test baseline: **26 passing**.
- SaaS backend AI policy baseline: **7 passing**.
- SaaS backend TypeScript build passes.
- SaaS frontend Vite production build passes.

Known non-blocking frontend build warnings:

- The main Vite bundle is large.
- Axios and `baseUrl.jsx` have both static and dynamic imports.

## 3. Non-negotiable safety rules

1. Never trust organization, user, role, permission, feature, or allowed-location values from the browser.
2. Never let the browser call ZenAI directly or receive service/delegation secrets.
3. Every business-data query must be scoped by server-derived `org_id` and authorized location.
4. Do not enable arbitrary SQL or text-to-SQL during the required production slices.
5. Do not add write actions to AI tools. Recommendations must use existing SaaS confirmation workflows.
6. Do not log questions, delegation tokens, service keys, returned business rows, or PII in tool audit records.
7. Do not apply a database migration without explicit approval, backup confirmation, target database confirmation, and a rollback plan.
8. Preserve unrelated user changes, especially existing SaaS backend `package-lock.json` and `readme.md` changes.
9. Run verification after every slice and update `ZENAI_SAAS_INTEGRATION_TASKLIST.md`.

## 4. Definition of production-ready

The required work is complete only when:

- Ordered migrations are reviewed and applied successfully in staging.
- Cross-tenant and cross-location tests demonstrate no data leakage.
- Every curated tool passes scope, PII, timeout, cancellation, and audit tests.
- Frontend unit and E2E tests cover the critical user journeys.
- Production secrets, connectivity, health checks, streaming, alerts, retention, and budgets are configured.
- A limited pilot and rollback drill succeed.
- Product owners approve plans, roles, quotas, retention, PII policy, and runtime.

---

## Slice 10: Product decisions and staging fixtures

### Objective

Remove configuration ambiguity and create a safe test environment with visibly different tenant data.

### Decisions required from the owner

- Canonical feature key: use `ai_features` unless there is a confirmed reason not to.
- Eligible subscription plans.
- Eligible roles and whether branch-restricted staff may use AI Insights.
- Default monthly request limit.
- Organization and user concurrency limits.
- Conversation retention duration.
- Audit retention duration.
- Whether questions may be stored and for how long.
- PII fields that must never appear in prompts, answers, exports, or logs.
- Production runtime for the Node streaming gateway.
- Whether Redis is required for readiness.
- Pilot organizations and pilot duration.

### Implementation tasks

- Record decisions in an ADR or a clearly labeled section of the implementation plan.
- Convert chosen defaults into documented environment variables and plan defaults.
- Create at least two staging organizations with deliberately different:
  - sales totals
  - products
  - locations
  - inventory risks
  - order statuses
- Create administrator, allowed branch user, forbidden branch user, and user without AI permission fixtures.
- Ensure fixture creation is repeatable and staging-only.

### Acceptance criteria

- No unresolved product decision changes authorization, retention, cost, or deployment behavior.
- A tester can identify tenant leakage immediately because tenant values are intentionally different.
- Fixture scripts cannot target production accidentally.

### Deliverables

- Decision record.
- Staging fixture instructions/script.
- Updated environment documentation.
- Updated tasklist.

---

## Slice 11: Ordered production migrations

### Objective

Replace runtime-only schema assumptions with reviewed, versioned, reversible migrations.

### Required schema inventory

SaaS database:

- `plans` AI limit columns, if not already migration-backed.
- `ai_org_settings`
- `ai_usage_monthly`
- `ai_active_requests`
- `ai_action_audit`
- All related constraints and indexes.

ZenAI database:

- Integrated conversations.
- Integrated messages.
- Integrated feedback.
- External organization/user identity fields and indexes.
- Retention/archive fields.

### Implementation tasks

1. Inspect the actual existing schemas before writing SQL.
2. Choose the migration mechanism already used by each repository; do not introduce a second framework without approval.
3. Create forward migrations with idempotency only where the existing migration convention requires it.
4. Create explicit rollback migrations where safe.
5. Add preflight queries for:
   - table/column existence
   - duplicate or invalid data
   - foreign-key targets
   - expected extension availability, including `pgcrypto` if `gen_random_uuid()` is used
6. Add post-migration verification queries.
7. Document lock and downtime risks.
8. Test on a disposable/staging database populated with representative data.

### Migration execution gate

Stop after generating and reviewing migrations unless the owner explicitly authorizes execution. Before execution, report:

- exact database host/name/environment
- exact migration files
- backup status
- expected locks/downtime
- rollback procedure

### Acceptance criteria

- Fresh database migration succeeds.
- Upgrade from the current staging schema succeeds.
- Rollback is tested where supported.
- No existing SaaS data is overwritten.
- Application startup no longer needs to be the only mechanism that creates AI tables.
- Backend builds and all existing tests pass.

### Verification

- SaaS backend: `npm run build`
- SaaS AI tests: `npm run test:ai`
- ZenAI: `.\venv\Scripts\python.exe -m unittest discover -s tests -v`

---

## Slice 12: Security and tenant-isolation integration tests

### Objective

Prove that model behavior, crafted IDs, and malformed requests cannot bypass SaaS authorization or tenant scope.

### Test matrix

Delegation and service authentication:

- missing/wrong service key
- HS256 and `none` algorithm rejection
- wrong issuer/audience
- expired/not-yet-valid token
- excessive token age
- missing claims
- malformed UUID claims
- selected location outside allowed locations
- optional replay test if replay protection is approved

Authorization:

- missing `insights` permission
- missing plan feature
- global kill switch
- organization kill switch
- branch-restricted user requesting all branches
- user requesting another branch
- unauthorized conversation/message/export IDs

Every curated tool:

- organization A never receives organization B data
- location A never receives forbidden location B data
- omitted location follows role rules
- date and integer windows enforce bounds
- results enforce row caps
- PII fields are excluded/redacted
- unknown tools fail closed
- tool errors do not expose SQL, connection strings, stack traces, or secrets

Streaming and resilience:

- NDJSON split across arbitrary chunks
- multiple events in one chunk
- malformed event handling
- browser cancellation propagates upstream
- ZenAI timeout
- SaaS tool timeout
- Gemini outage
- database outage
- quota/concurrency exhaustion
- audit success/rejected/error outcomes

Prompt attacks:

- request another tenant
- ask to ignore permissions
- request raw SQL
- request unsupported customer/staff PII
- request write actions
- inject instructions through product names or report fields

### Implementation guidance

- Prefer database-backed HTTP integration tests for scope boundaries.
- Keep pure policy tests for fast deterministic checks.
- Never assert only that a status code is successful; assert returned tenant-specific values.
- Add sanitized snapshots only when they cannot contain production data.

### Acceptance criteria

- The complete test matrix passes.
- Cross-tenant and cross-location leakage tests fail before a deliberate fix and pass afterward.
- No secret or PII appears in test logs or error bodies.
- Tasklist security gates are updated with exact coverage.

---

## Slice 13: Frontend extraction, unit tests, accessibility, and Playwright

### Objective

Make the AI Insights UI maintainable and verify critical browser behavior.

### Refactoring tasks

- Extract streaming behavior into a dedicated hook, such as `useAIInsightsStream`.
- Keep the chunk-safe NDJSON parser independently unit-testable.
- Split large page sections into focused components where this reduces risk:
  - proactive cards
  - conversation history
  - filters
  - message/result rendering
  - chart/table
  - composer
- Preserve current behavior and styling.

### Unit tests

- NDJSON chunk boundaries and malformed events.
- Retry does not duplicate the user message.
- Stop aborts the request.
- Access failure disables prompts and composer.
- Date validation.
- Chart selection and table fallback.
- CSV download error handling.
- Feedback state.
- English/Bengali strings for critical states.

### Playwright E2E journeys

1. Authorized admin opens AI Insights and asks a supported question.
2. Branch-restricted user cannot select or retrieve another branch.
3. Date filters reach the backend correctly.
4. Streaming status, answer, chart, and table render.
5. Stop cancels a request.
6. Failure shows retry; retry succeeds without duplicate user content.
7. History opens the correct scoped conversation.
8. Rename/archive/delete behavior, if exposed by UI.
9. Feedback persists.
10. CSV export downloads a safe file.
11. Quota exhaustion displays a useful message and retry timing.
12. User without access sees the access state and cannot submit.
13. Proactive inventory card opens Smart Inventory.
14. Bengali layout and text remain usable.

### Accessibility/security review

- Keyboard-only operation.
- Visible focus.
- Correct labels and accessible names.
- Live-region behavior for streaming status/errors.
- Color contrast in light/dark themes.
- Responsive checks at phone, tablet, and desktop widths.
- React text rendering remains escaped; do not introduce unsafe HTML rendering.

### Acceptance criteria

- Unit and E2E suites are stable and documented.
- No regression in SaaS frontend production build.
- Critical journeys pass in Chromium; add other browsers if supported by the SaaS.

---

## Slice 14: Production deployment and private connectivity

### Objective

Deploy the curated-tools integration securely with reversible configuration.

### Secrets and keys

- Generate a production RS256 key pair.
- SaaS backend holds the private signing key.
- ZenAI holds only the public verification key.
- Both services receive the shared internal service key through a secret manager.
- Define key rotation and emergency revocation steps.
- Never commit secrets or print them during verification.

### Connectivity

- ZenAI should not be publicly callable from browsers.
- Restrict ZenAI ingress to the SaaS backend/platform network where supported.
- Require TLS.
- Configure SaaS-to-ZenAI timeouts and keep-alive behavior.
- Confirm CORS remains disabled in integrated mode.

### Runtime validation

- Confirm the chosen Node platform supports streamed NDJSON responses for the maximum configured duration.
- Confirm proxy/load-balancer buffering is disabled for the stream.
- Confirm client disconnect cancellation reaches ZenAI and internal tools.
- Validate readiness/liveness paths and authenticated metrics scraping.
- Set `ENABLE_TEXT_TO_SQL=false`.
- Set `ENABLE_CURATED_TOOLS=true`.
- Configure kill switches, quotas, retention, and readiness requirements.

### Data services

- Provision ZenAI PostgreSQL.
- Provision Redis only if used/required by the chosen production configuration.
- Decide whether Chroma is needed for curated-only production; do not expose or populate unrestricted SaaS schema metadata.
- Defer pgvector/Chroma changes unless required.

### Acceptance criteria

- Browser network traffic contains only SaaS API calls.
- ZenAI rejects missing service authentication.
- Staging streaming survives the expected request duration.
- Health, metrics, key rotation, and kill-switch procedures are tested.
- Rollback can disable AI without affecting POS/orders/authentication.

---

## Slice 15: Operations, retention, alerts, and budgets

### Objective

Make failures, cost, abuse, and stale data visible and manageable.

### Implementation tasks

- Add scheduled cleanup for expired conversations/messages/feedback.
- Define and implement audit retention cleanup separately.
- Clean expired `ai_active_requests` leases safely.
- Implement SaaS organization/user deletion cleanup for ZenAI integrated records.
- Add structured signals for:
  - request count
  - success/failure
  - latency
  - tool calls by tool/status
  - quota rejection
  - concurrency rejection
  - cancellation
  - readiness failure
  - model/tool timeout
- Add alerts for sustained error rate, latency, readiness, unusual usage, and budget thresholds.
- Add dashboards segmented by environment and organization where privacy policy allows.
- Confirm logs exclude questions, tool results, tokens, keys, PII, and connection strings.
- Document monthly budget and emergency shutdown procedure.

### Acceptance criteria

- Cleanup jobs are idempotent and tested.
- Retention matches the approved policy.
- An intentional staging failure triggers the expected alert.
- Operators can identify a failing dependency using correlation IDs without seeing sensitive business data.
- Global and organization kill switches are documented and tested.

---

## Slice 16: Adversarial review, pilot, and rollback drill

### Objective

Validate the whole system with real operational procedures before general availability.

### Pre-pilot gate

- All required migration, security, frontend, deployment, and operations acceptance criteria pass.
- Product decisions are signed off.
- Text-to-SQL remains disabled.
- Support and incident owners are named.

### Pilot plan

- Start with internal users.
- Enable one or two selected organizations.
- Use conservative quotas.
- Monitor answer usefulness, latency, failure rate, quota usage, and feedback.
- Manually review representative answers for numerical accuracy and PII.
- Compare proactive cards to source reports.
- Collect false-positive/unsupported-intent cases without expanding tool scope automatically.

### Adversarial review

- Run the Slice 12 attack suite against staging.
- Perform manual IDOR, prompt-injection, scope, export, and log review.
- Verify service endpoints cannot be reached directly from an untrusted browser/network.
- Confirm unsupported write requests remain recommendations only.

### Rollback drill

1. Disable AI globally.
2. Confirm POS, orders, inventory, and authentication remain healthy.
3. Stop/rollback ZenAI deployment.
4. Roll back application code if necessary.
5. Roll back database changes only through reviewed migration procedures.
6. Confirm no stuck active-request leases or broken navigation remain.

### Acceptance criteria

- Pilot success metrics are documented and met.
- Rollback drill succeeds.
- No severity-high security finding remains open.
- General availability requires explicit owner approval.

---

## Slice 17 (optional): Hardened text-to-SQL

### Default status

Disabled and out of scope for the curated-tools production release.

### Mandatory prerequisites

- Create an approved `ai_analytics` schema containing views only.
- Use a dedicated login role with:
  - read-only privileges
  - `NOBYPASSRLS`
  - no access to base transaction tables
  - no dangerous function execution
- Enable and FORCE RLS.
- Set organization/location context transaction-locally.
- Run validation, EXPLAIN, and execution in the same scoped transaction.
- Parse SQL with a real PostgreSQL AST parser.
- Allowlist every relation, column, function, operator, and statement form.
- Reject DDL, DML, multiple statements, comments used for bypass, dangerous functions, unbounded joins, and excessive complexity.
- Enforce statement timeout, row cap, cost cap, and concurrency limits.
- Introspect only approved analytics views.
- Prefer a read replica.
- Ensure cache keys contain every authorization and data-scope dimension.

### Required malicious test classes

- joins/CTEs/subqueries crossing tenant boundaries
- UNION and lateral joins
- function/schema qualification tricks
- quoted identifiers and Unicode confusion
- comment/semicolon bypasses
- `SET`, `COPY`, system catalogs, file/network functions
- pooled connection context leakage
- stale cache cross-tenant leakage
- EXPLAIN/execution transaction mismatch

### Acceptance criteria

Text-to-SQL may be enabled only after an independent security review and explicit owner approval. Failure of any isolation test keeps it disabled.

---

## 5. Required verification after each slice

ZenAI:

```powershell
Set-Location "D:\PieceOfShit\Projects\AI\ZenAI\zenai\backend"
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

SaaS backend:

```powershell
Set-Location "D:\PieceOfShit\SaaS\saas-backend-v1\saas-backend-v1"
npm run test:ai
npm run build
```

SaaS frontend:

```powershell
Set-Location "D:\PieceOfShit\SaaS\saas-admin-frontend-v1\saas-admin-frontend-v1"
npm run build
```

Also run any new integration/unit/E2E commands introduced by the slice.

## 6. Claude execution protocol

For each slice:

1. Read the relevant existing code before proposing edits.
2. State assumptions and any decision needed from the owner.
3. Create a small task checklist for that slice.
4. Implement only that slice.
5. Do not silently broaden tool access, data access, or authorization.
6. Run the required verification.
7. Report exact tests/builds and any warnings.
8. Update `ZENAI_SAAS_INTEGRATION_TASKLIST.md`.
9. Stop before destructive or externally consequential actions unless explicitly authorized.

## 7. Suggested first prompt for Claude

```text
You are continuing an existing ZenAI + NexDokandar SaaS integration.

Repositories:
- ZenAI: D:\PieceOfShit\Projects\AI\ZenAI\zenai
- SaaS backend: D:\PieceOfShit\SaaS\saas-backend-v1\saas-backend-v1
- SaaS frontend: D:\PieceOfShit\SaaS\saas-admin-frontend-v1\saas-admin-frontend-v1

First read completely:
1. ZENAI_SAAS_INTEGRATION_IMPLEMENTATION_PLAN.md
2. ZENAI_SAAS_INTEGRATION_TASKLIST.md
3. CLAUDE_ZENAI_CONTINUATION_PLAN.md

Slices 1-9 are already implemented. Do not redo them. Begin with Slice 10 from the continuation plan. Inspect current code before editing, preserve unrelated changes, keep text-to-SQL disabled, never trust browser scope, and do not execute database migrations without my explicit approval. After the slice, run all specified tests/builds and update the tasklist.
```

## 8. Final slice count

- Slice 10: decisions and staging fixtures
- Slice 11: ordered migrations
- Slice 12: security/integration tests
- Slice 13: frontend tests and accessibility
- Slice 14: production deployment
- Slice 15: operations and retention
- Slice 16: pilot and rollback
- Slice 17: optional hardened text-to-SQL

Therefore, **7 required slices remain**, or **8 total including the optional text-to-SQL slice**.
