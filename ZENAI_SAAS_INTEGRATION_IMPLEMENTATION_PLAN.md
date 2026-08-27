# ZenAI + NexDokandar SaaS Integration Implementation Plan

**Document status:** Proposed for manual review  
**Prepared:** 2026-08-19  
**ZenAI root:** `D:\PieceOfShit\Projects\AI\ZenAI\zenai`  
**SaaS frontend:** `D:\PieceOfShit\SaaS\saas-admin-frontend-v1\saas-admin-frontend-v1`  
**SaaS backend:** `D:\PieceOfShit\SaaS\saas-backend-v1\saas-backend-v1`

---

## 1. Executive decision

Integrate ZenAI as a **private AI service** behind the existing NexDokandar Node/Express backend. Build `/admin/insights` as a native React page in the SaaS frontend. Do not embed the standalone ZenAI frontend, do not require a second login, and do not allow the browser to call ZenAI directly.

Use two delivery stages:

1. **Release 1: Curated tool mode (recommended production MVP).** ZenAI answers questions using approved, tenant-scoped SaaS reporting and inventory tools. This reuses existing backend business queries and minimizes cross-tenant risk.
2. **Release 2: Hardened text-to-SQL mode (optional).** ZenAI may query only an approved analytics schema through a read-only database role, PostgreSQL Row-Level Security (RLS), strict AST validation, statement limits, and a tenant context set by the server.

Release 1 must not be blocked on Release 2. Arbitrary SQL access must remain disabled until every text-to-SQL security acceptance test in this document passes.

---

## 2. Current-state findings

### 2.1 SaaS frontend

- React 18 + Vite 7 + React Router 7.
- Axios is already centralized through `src/hooks/useAxiosSecure.jsx`.
- Current authentication token is stored under `localStorage.token`.
- `AuthProvider` loads the current user from `/api/v1/auth/single-user`.
- The sidebar already declares:
  - Path: `/admin/insights`
  - Permission key: `insights`
  - Badge: currently `PRO`
- `/admin/insights` is not currently registered in `src/routes/Routes.jsx`.
- English localization already includes `menu.insights`; Bengali page-level content still needs to be added.
- Recharts and reusable chart primitives already exist.
- `SmartInventoryEngine.jsx` already implements stockout, auto-PO, and dead-stock workflows. AI Insights should link to it rather than duplicate it.

### 2.2 SaaS backend

- Node.js + TypeScript + Express 5 + PostgreSQL.
- JWT payload contains `id`, `role`, `org_id`, and `email`.
- The organization is the tenant boundary; most business tables use `org_id`.
- Users may also have `assigned_location_id` and location restrictions.
- Existing middleware includes:
  - `authChecker()` for JWT validation.
  - `checkPermission(...)` for menu permissions.
  - `requireFeature(...)` / plan access helpers.
- Existing report endpoints include:
  - `/api/v1/reports/sales`
  - `/api/v1/reports/orders`
  - `/api/v1/reports/product-performance`
  - `/api/v1/reports/inventory-valuation`
  - `/api/v1/reports/profit-loss`
  - `/api/v1/reports/customer-dues`
  - `/api/v1/reports/staff-performance`
  - `/api/v1/reports/sales-by-hour`
  - `/api/v1/reports/order-status-breakdown`
  - `/api/v1/reports/customer-retention`
- Existing Smart Inventory endpoints include stockout predictions, auto-PO drafts/approval, and dead-stock advice.
- The project currently has no real automated backend test command.
- `initDB()` runs during app startup and contains a large schema initializer. New AI migrations should not rely only on app startup for production changes.
- The backend creates a long-lived HTTP server and Socket.IO server but also contains Vercel deployment configuration. Streaming behavior and Socket.IO compatibility on the production runtime must be validated.

### 2.3 ZenAI

- FastAPI + Python + asyncpg + Redis + ChromaDB + Gemini.
- Existing capabilities:
  - Streaming NDJSON chat responses.
  - Schema introspection and embeddings.
  - SQL generation and validation.
  - Query cost estimation, timeout, row cap, retry, caching, feedback, and CSV export.
  - Separate users, workspaces, memberships, database connections, and JWT authentication.
- The standalone Next.js frontend is not required for the embedded SaaS experience.
- ZenAI currently expects its own JWT `sub`, while the SaaS JWT uses `id`.
- ZenAI currently scopes generated SQL by injecting `workspace_id` into the outer query.
- SaaS business tables use `org_id`, not `workspace_id`.
- The current outer-query filter is not a sufficient tenant boundary for joins, CTEs, nested queries, tables without the scope column, or ambiguous columns.
- ZenAI currently introspects all public tables and samples low-cardinality text values. That must not run against unrestricted production SaaS tables.
- The current Render blueprint is at the repository root while Python dependencies and app code are under `backend/`; deployment root/build paths must be corrected.

---

## 3. Goals

### 3.1 Product goals

- Add a native AI Insights experience under `/admin/insights`.
- Let authorized users ask business questions in English or Bengali.
- Return concise answers, insight bullets, charts, confidence, source/time-range context, and optional exports.
- Respect organization, branch/location, role, menu permission, subscription, and feature limits.
- Reuse existing business reports and Smart Inventory workflows.
- Support conversation history and feedback.
- Provide proactive insight cards in addition to chat.
- Keep all write actions explicit, confirmed, audited, and executed through existing SaaS APIs.

### 3.2 Engineering goals

- Preserve the current SaaS frontend and backend architecture.
- Keep AI model credentials and ZenAI endpoints out of the browser.
- Maintain hard multi-tenant isolation independently of model behavior.
- Permit ZenAI to scale and deploy separately from transaction-processing APIs.
- Add observable usage, latency, failure, and cost signals.
- Make rollout reversible through feature flags.

### 3.3 Success metrics

- Zero cross-organization or unauthorized-location data exposure in automated and manual tests.
- 95% of supported curated questions return a useful answer without errors.
- P95 first status event under 2 seconds when dependencies are healthy.
- P95 complete answer under 15 seconds for curated tools; define a separate target for text-to-SQL.
- 100% of AI requests have organization, user, correlation, and audit identifiers.
- 100% of write-like recommendations require a normal SaaS confirmation workflow.
- AI failures do not affect POS, orders, inventory, or authentication availability.

---

## 4. Non-goals for the first release

- Replacing Reports & Analytics.
- Replacing Smart Inventory.
- Giving the model direct write access to PostgreSQL.
- Allowing customer-supplied database connections from the embedded SaaS page.
- Exposing the standalone ZenAI registration/login/workspace UI inside NexDokandar.
- Supporting arbitrary SQL against all public SaaS tables.
- Automatically creating purchases, discounts, refunds, payments, or messages without confirmation.
- Training a custom model.
- Building a general-purpose workflow automation engine.

---

## 5. Target architecture

```text
NexDokandar React browser
  |
  | SaaS JWT; /api/v1/ai/* only
  v
NexDokandar Node/Express backend (public BFF/security boundary)
  |-- validates user, org, plan, permissions, location
  |-- creates short-lived signed delegation token
  |-- owns usage/quota and action authorization
  |-- proxies NDJSON stream
  |
  | private HTTPS + service authentication
  v
ZenAI FastAPI (private integrated mode)
  |-- verifies delegation token
  |-- conversation, model orchestration, reasoning, charts
  |-- Release 1: calls approved SaaS AI tools
  |-- Release 2: queries approved analytics views only
  |
  +--> ZenAI PostgreSQL (sessions/messages/logs/feedback)
  +--> Redis (rate limit/cache)
  +--> Chroma or later pgvector (approved schema metadata only)
  +--> Gemini API

Release 1 tool callback:
ZenAI --> private /api/v1/internal/ai/tools/:tool --> existing SaaS services --> SaaS PostgreSQL

Release 2 query path:
ZenAI --> read-only analytics connection --> ai_analytics views + FORCE RLS --> SaaS read replica preferred
```

### Trust boundaries

1. Browser input is always untrusted.
2. The SaaS JWT is validated only by the SaaS backend; it is not forwarded to Gemini.
3. `org_id`, user ID, allowed locations, role, and permissions are derived server-side, never accepted from browser claims or request bodies.
4. ZenAI receives a short-lived, signed delegation context from the SaaS backend.
5. ZenAI output is untrusted display content and is never treated as authorization.
6. Tool endpoints independently verify the signed delegation context.
7. Database RLS and permissions remain authoritative even if SQL validation or prompts fail.

---

## 6. Architecture Decision Records

### ADR-001: Private ZenAI service behind the SaaS backend

**Status:** Proposed

**Context:** ZenAI is Python/FastAPI while the SaaS backend is Node/Express. AI workloads have different dependencies, latency, scaling, and failure modes.

**Options considered:**

| Option | Advantages | Disadvantages | Decision |
|---|---|---|---|
| Native SaaS UI + Node gateway + private ZenAI | Best UX, one auth system, preserves Python code, isolates AI failures | Adds one internal service boundary | **Chosen** |
| Browser calls ZenAI directly | Less Node proxy code | Exposes service, duplicates auth/CORS, weakens policy enforcement | Rejected |
| Iframe standalone ZenAI | Fast demo | Poor theme/navigation, second login, awkward sizing and security | Rejected |
| Rewrite ZenAI in Node | One runtime | Large rewrite and regression risk | Rejected |
| Merge all repositories | One checkout | Couples deployments and dependency ecosystems | Rejected |

**Trade-off accepted:** One extra network hop is accepted to preserve a single public security boundary and independent AI scaling.

**Revisit trigger:** Reconsider only if operating the Python service becomes materially more expensive than maintaining an equivalent Node implementation.

### ADR-002: Curated tools before unrestricted text-to-SQL

**Status:** Proposed

**Decision:** Release the first production version using approved SaaS reporting tools. Keep direct SQL behind a disabled feature flag until the analytics schema and RLS are complete.

**Rationale:** Existing report services already apply tenant-aware business logic. This is safer and faster than immediately allowing generated SQL over the shared multi-tenant schema.

**Trade-off accepted:** Release 1 supports a bounded catalog of questions rather than every theoretically possible question.

**Revisit trigger:** Enable text-to-SQL only when demand for unsupported questions is measurable and the security gate in Section 18 passes.

### ADR-003: SaaS identity remains authoritative

**Status:** Proposed

**Decision:** Do not ask integrated users to register or log in to ZenAI. Automatically map SaaS organizations and users to ZenAI external identities.

**Consequences:** ZenAI standalone auth can remain for local development but must be disabled in integrated production mode.

### ADR-004: All model-recommended writes use existing SaaS commands

**Status:** Proposed

**Decision:** ZenAI is read-only. When it recommends an action, the UI opens a normal SaaS form or calls a specific, permission-checked SaaS command after human confirmation.

**Examples:** Create draft purchase order, open due-reminder composer, open discount editor, or navigate to filtered orders.

### ADR-005: NDJSON streaming for the initial integration

**Status:** Proposed

**Decision:** Retain ZenAI's current newline-delimited JSON stream for Release 1. The Node backend proxies it without buffering, and the browser parses partial lines.

**Trade-off:** SSE has broader event semantics, but changing the protocol is unnecessary for the MVP. Revisit if reconnect/event-ID support is required.

### ADR-006: AI Product Decisions (Slice 10)

**Status:** Accepted

**Decision:** The following product decisions define the access, retention, and operational limits for the AI Insights integration:
1. **Canonical feature key**: `ai_features`
2. **Eligible subscription plans**: PRO and ENTERPRISE plans
3. **Eligible roles**: `admin` and `manager` (branch-restricted staff can use AI Insights, but it will be hard-scoped to their assigned branch).
4. **Default monthly request limit**: 500 requests per month.
5. **Organization and user concurrency limits**: Max 5 concurrent requests per organization, and max 1 concurrent request per user.
6. **Conversation retention duration**: 30 days.
7. **Audit retention duration**: 90 days.
8. **Whether questions may be stored**: Yes, stored for the conversation retention duration (30 days) to allow users to resume chats.
9. **PII fields to exclude**: Passwords, auth tokens, API keys, payment methods, phone numbers, exact addresses, and full customer names (first names allowed).
10. **Production runtime for Node**: Standard long-lived Node.js instance (e.g., VPS or Render), as serverless/Vercel functions do not support long-lived NDJSON streaming well.
11. **Redis**: Yes, required for readiness (for ZenAI rate limiting and caching).
12. **Pilot rollout**: 2 internal test organizations for a 2-week pilot.

---

## 7. Product design for `/admin/insights`

### 7.1 Page layout

1. **Header**
   - Title: AI Insights / AI Business Copilot.
   - Current organization.
   - Branch selector constrained to authorized locations.
   - Date range selector.
   - Language selector or current app locale.
   - “Data updated” timestamp.

2. **Proactive insight strip**
   - Sales anomaly.
   - Profit/margin movement.
   - Stockout risk.
   - Dead-stock capital.
   - Customer dues.
   - Cash-flow warning when supported.
   - Each card links to the relevant report or Smart Inventory view.

3. **Copilot conversation panel**
   - Suggested prompts before the first message.
   - User and assistant message bubbles.
   - Streaming status indicator.
   - Stop/cancel button.
   - Retry button.
   - Feedback controls.
   - Clear/new conversation.

4. **Answer visualization**
   - KPI cards.
   - Recharts line, bar, area, and pie charts.
   - Accessible data table fallback.
   - Confidence label.
   - Effective organization/location/date scope.
   - Data freshness.
   - Optional “How this was calculated” section.
   - Generated SQL visible only to authorized administrators in Release 2.

5. **Action area**
   - Navigation links and draft-action buttons only.
   - Every action shows a preview/confirmation.

### 7.2 Initial suggested prompts

- “Summarize sales and profit for this month.”
- “Compare this month with last month.”
- “Which products generated the most revenue?”
- “Which products may run out soon?”
- “How much money is locked in dead stock?”
- “Show customer outstanding dues.”
- “When are our peak sales hours?”
- “How is customer retention changing?”
- “Compare branches for the selected period.”
- Bengali equivalents for every prompt.

### 7.3 UX rules

- Show that answers are generated and should be verified for critical decisions.
- Never render model HTML directly. Render plain text/controlled Markdown with HTML disabled.
- Never execute links or commands returned as arbitrary model content.
- Preserve filters across messages in a conversation.
- Clearly show when an answer is cached, incomplete, or based on fallback logic.
- Display user-friendly errors without database names, SQL errors, secrets, or stack traces.
- On rate limit, show retry timing and plan upgrade messaging when relevant.

---

## 8. External API contract: browser to SaaS backend

Base path: `/api/v1/ai`

All endpoints require `authChecker()`, `checkPermission("insights")`, and a backend feature gate accepting the final chosen feature key (recommended canonical key: `ai_features`, with `insights` supported temporarily during migration).

### 8.1 Start or continue chat

`POST /api/v1/ai/chat`

Request:

```json
{
  "question": "Why did profit fall this month?",
  "conversation_id": "optional-uuid",
  "location_id": "optional-authorized-location-uuid",
  "date_range": {
    "from": "2026-08-01",
    "to": "2026-08-19"
  },
  "locale": "en-BD",
  "timezone": "Asia/Dhaka"
}
```

Validation:

- `question`: trimmed, 1-2000 characters.
- `conversation_id`: valid UUID and owned by the current SaaS user/organization.
- `location_id`: UUID and authorized for the current user; admin “all branches” is represented internally, not by trusting an empty browser value.
- Date range: valid, `from <= to`, maximum range based on plan/system policy.
- Locale: allowlist `en`, `en-BD`, `bn`, `bn-BD` initially.
- Timezone: validated IANA timezone; default from organization/workspace.

Response headers:

```text
Content-Type: application/x-ndjson
Cache-Control: no-cache, no-transform
X-Accel-Buffering: no
X-Request-Id: <correlation-id>
X-Conversation-Id: <uuid>
```

Stream events, one JSON object per line:

```json
{"type":"meta","request_id":"...","conversation_id":"...","scope":{"location_id":null,"from":"2026-08-01","to":"2026-08-19"}}
{"type":"status","stage":"selecting_tools","message":"Checking the relevant reports..."}
{"type":"status","stage":"analyzing","message":"Analyzing results..."}
{"type":"answer","message_id":"...","answer":"...","insights":[],"chart_type":"bar","chart_data":[],"confidence":"high","sources":[],"cached":false}
{"type":"done","usage":{"input_tokens":0,"output_tokens":0},"execution_ms":1234}
```

Error event after streaming has begun:

```json
{"type":"error","code":"AI_UPSTREAM_UNAVAILABLE","message":"AI Insights is temporarily unavailable.","retryable":true}
```

Before streaming begins, use normal HTTP statuses: 400, 401, 403, 404, 409, 422, 429, 502, or 503.

### 8.2 Conversation endpoints

- `GET /api/v1/ai/conversations?cursor=&limit=20`
- `GET /api/v1/ai/conversations/:conversationId`
- `PATCH /api/v1/ai/conversations/:conversationId` for title/archive only.
- `DELETE /api/v1/ai/conversations/:conversationId` for user-requested deletion.

Every query must include the authenticated organization and user scope.

### 8.3 Feedback

`POST /api/v1/ai/messages/:messageId/feedback`

```json
{
  "rating": "up",
  "comment": "Optional comment up to 1000 characters"
}
```

### 8.4 Export

`GET /api/v1/ai/messages/:messageId/export?format=csv`

- Re-authorize the message against user and organization.
- Apply export row limits.
- Do not regenerate or execute stored SQL solely from a browser-provided ID.
- Prefer exporting the persisted, sanitized result snapshot or re-running the approved tool with the stored scope.

### 8.5 Proactive insights

`GET /api/v1/ai/insights?location_id=&from=&to=`

- Returns deterministic metric cards plus optional model-written summaries.
- Cache metrics and narrative separately.
- Never hide deterministic metrics if narrative generation fails.

### 8.6 Usage

`GET /api/v1/ai/usage`

Returns current billing month limits, requests used, tokens/cost if exposed, reset time, and whether the feature is throttled.

---

## 9. Internal service contract: SaaS backend to ZenAI

Base path: `/internal/v1`

ZenAI integrated production mode must reject public calls to this path unless all service-authentication checks pass.

### 9.1 Delegation token

The SaaS backend creates a short-lived RS256 JWT (recommended lifetime: 5 minutes, never persisted in the browser) containing:

```json
{
  "iss": "nexdokandar-backend",
  "aud": "nexdokandar-ai",
  "sub": "saas-user-uuid",
  "org_id": "organization-uuid",
  "role": "admin",
  "allowed_location_ids": ["location-uuid"],
  "selected_location_id": "location-uuid-or-null",
  "permissions": ["insights", "reports"],
  "features": ["ai_features"],
  "locale": "bn-BD",
  "timezone": "Asia/Dhaka",
  "request_id": "correlation-id",
  "jti": "unique-token-id",
  "iat": 0,
  "exp": 0
}
```

Rules:

- Node signs with a dedicated AI delegation private key, not the normal SaaS HS256 login secret.
- ZenAI receives only the public verification key.
- Validate algorithm, issuer, audience, expiry, required claims, and maximum token age.
- Do not accept algorithm negotiation or `none`.
- Do not log the raw token.
- Optionally reject replayed `jti` values for high-risk internal endpoints.
- The original SaaS bearer token must never be forwarded to ZenAI or Gemini.

### 9.2 Internal chat request

`POST /internal/v1/chat`

```json
{
  "question": "...",
  "conversation_id": "optional-uuid",
  "date_range": {"from":"2026-08-01","to":"2026-08-19"},
  "capabilities": ["sales_summary","profit_loss","inventory_health"]
}
```

Identity and tenant values come exclusively from the delegation token.

### 9.3 Tool callback authentication

ZenAI forwards the still-valid delegation token to `/api/v1/internal/ai/tools/:toolName` over private HTTPS. The SaaS backend verifies its own signature and the caller's private-service credential/network identity.

The tool request body contains only validated tool parameters such as date range, grouping, limit, and requested measure. `org_id` is never accepted from the body.

### 9.4 Internal health/readiness

- `GET /health/live`: process alive; no secret data.
- `GET /health/ready`: checks required service state with short timeouts.
- Metrics must be protected by private network or service authentication.

---

## 10. Release 1 curated tool catalog

Create a strict registry; the model may select only registered tools and schema-validated arguments.

| Tool | Backing SaaS capability | Required permission | Parameters |
|---|---|---|---|
| `sales_summary` | Reports sales service | insights + reports/dashboard policy | from, to, location, interval |
| `order_summary` | Orders report | insights | from, to, location, channel, status |
| `product_performance` | Product performance report | insights | from, to, location, limit, sort |
| `inventory_valuation` | Inventory valuation | insights + inventory policy | location, category |
| `profit_loss` | Profit/loss report | insights + finance policy | from, to, location |
| `customer_dues` | Customer dues report | insights + customer/finance policy | location, limit, risk band |
| `staff_performance` | Staff performance report | insights + staff-report policy | from, to, location, user filter |
| `sales_by_hour` | Sales-by-hour report | insights | from, to, location |
| `order_status_breakdown` | Status breakdown report | insights | from, to, location |
| `customer_retention` | Retention report | insights | comparison periods, location |
| `stockout_risk` | Smart Inventory stockout service | insights + inventory | location, horizon days |
| `deadstock_advisor` | Smart Inventory dead-stock service | insights + inventory | location, idle days |
| `business_health` | Existing health/report composition | insights | from, to, location |

### Tool implementation rules

- Reuse service-layer functions, not controllers, so internal calls do not fake Express requests.
- Every service call takes an explicit trusted `orgId` and optional validated `locationId`.
- Review every reused report query for organization and location predicates before registration.
- Normalize numeric/date values into a stable JSON contract.
- Limit arrays before sending them to the model; aggregate whenever possible.
- Remove passwords, tokens, platform credentials, addresses, phone numbers, emails, salary details, and other PII unless a documented use case explicitly requires them.
- Return metadata: source tool, parameters, row count, generated-at time, and data freshness.
- Set per-tool timeouts and maximum result sizes.
- The model cannot construct arbitrary URLs or tool names.
- Tool errors return stable error codes and no raw SQL/stack traces.

### Model orchestration

- Add a ZenAI `tool` execution mode separate from existing `sql` mode.
- Provide only tools allowed by the delegation claims.
- Maximum tool calls per question: start with 4.
- Execute independent read-only tools in parallel only when their parameter scopes match.
- Prevent recursive tool calls.
- Summarize/trim tool results before the final reasoning call when token thresholds are exceeded.
- Record tool name, sanitized parameters, latency, and status in the audit log.

---

## 11. SaaS frontend implementation

### 11.1 Files to add

Recommended structure:

```text
src/admin/pages/AIInsights/
  index.jsx
  AIInsightsHeader.jsx
  InsightCards.jsx
  ConversationSidebar.jsx
  ChatPanel.jsx
  MessageBubble.jsx
  SuggestedPrompts.jsx
  AnswerChart.jsx
  AnswerTable.jsx
  ConfidenceBadge.jsx
  SourceDetails.jsx
  ActionPanel.jsx
  AIEmptyState.jsx
  AIErrorState.jsx

src/services/aiInsightsService.js
src/hooks/useAIChatStream.js
src/utils/aiStreamParser.js
```

Split components only when useful; do not reproduce ZenAI's entire standalone frontend structure blindly.

### 11.2 Files to modify

- `src/routes/Routes.jsx`
  - Import the AI Insights page.
  - Register child route `path: "insights"` inside the protected admin layout.
  - Use `<ProtectedRoute><AIInsightsPage /></ProtectedRoute>`.
- `src/config/menuConfig.js`
  - Keep `/admin/insights` and key `insights`.
  - Confirm final badge (`PRO`, `ENT`, or `AI`) against product policy.
  - Do not reuse the `inventory` permission key for AI Insights.
- `src/i18n/locales/en/common.json`
- `src/i18n/locales/bn/common.json`
  - Add page labels, prompts, statuses, errors, confidence labels, and disclaimers.
- Optional dashboard/health pages
  - Add links to AI Insights, but do not duplicate chat state.

### 11.3 `aiInsightsService.js`

Use `useAxiosSecure` or the same base URL/auth convention. Do not add `VITE_ZENAI_URL`.

Methods:

- `streamChat(payload, signal)` using `fetch` if Axios response streaming is unreliable in the browser.
- `getConversations(cursor)`.
- `getConversation(id)`.
- `archiveConversation(id)`.
- `deleteConversation(id)`.
- `submitFeedback(messageId, payload)`.
- `getProactiveInsights(filters)`.
- `getUsage()`.
- `getExportUrl(messageId, format)` or authenticated blob download.

If `fetch` is used, read `localStorage.token` consistently with the existing app and attach only the SaaS backend base URL.

### 11.4 Stream handling

- Use `AbortController` for stop, navigation, and component unmount.
- Buffer partial bytes and split on newline.
- Parse only complete JSON lines.
- Cap client-side buffered content.
- Ignore unknown event types safely while logging them in development.
- Ensure the final buffered line is parsed after stream completion.
- Prevent duplicate sends while a request is active unless multi-conversation concurrency is intentionally supported.
- Do not retry a non-idempotent chat request automatically after receiving partial output. Offer a visible retry action.

### 11.5 State model

Minimum state:

```text
conversationId
messages[]
activeRequestId
statusStage
isStreaming
selectedLocationId
dateRange
usage
conversationCursor
error
```

Use local component state initially. Add Redux only if AI state must be shared outside the page.

### 11.6 Accessibility and responsive behavior

- Keyboard-accessible prompt input and buttons.
- `aria-live="polite"` for streaming statuses; do not announce every token.
- Table fallback for every chart.
- Non-color confidence labels.
- Logical focus after send, error, new conversation, and modal confirmation.
- Mobile layout: conversation drawer, stacked cards, horizontally scrollable data tables.
- Respect reduced-motion preferences.

---

## 12. SaaS backend implementation

### 12.1 New module

```text
src/modules/aiInsights/
  aiInsights.routes.ts
  aiInsights.controller.ts
  aiInsights.service.ts
  aiInsights.validation.ts
  aiInsights.types.ts
  aiInsights.errors.ts
  aiToolRegistry.ts
  aiTool.controller.ts
  aiTool.routes.ts
  aiUsage.service.ts
```

Supporting files:

```text
src/middleware/internalAiAuth.ts
src/utils/aiDelegationToken.ts
src/utils/streamProxy.ts
```

### 12.2 Route registration

Modify `src/app.ts`:

```text
app.use("/api/v1/ai", aiInsightsRoutes)
app.use("/api/v1/internal/ai", internalAiToolRoutes)
```

Register the public AI route before the final 404 handler. The internal route must require service authentication and must not rely on CORS as protection.

### 12.3 Middleware order

Public route order:

```text
request ID
authChecker()
checkPermission("insights")
requireFeature(["ai_features", "insights"])
AI quota/rate limit
request validation
controller
```

Internal tool route order:

```text
private-service authentication
delegation-token verification
tool-name allowlist
argument validation
per-tool authorization
controller
```

### 12.4 User/location authorization

- Derive `orgId` from `req.user.org_id`.
- Derive `userId` from `req.user.id`.
- Look up the user's current assigned location and authorized locations server-side.
- Admin “all branches” can set `selected_location_id = null`; staff with one assigned location cannot.
- Reject a requested location outside the authorized set with 403.
- Do not fall back from a missing location to `org_id`; they are different entity types.
- Include effective scope in the response metadata.

### 12.5 ZenAI client behavior

- Use Node's built-in `fetch`/Undici on the supported Node runtime.
- Connect to `ZENAI_INTERNAL_URL` with strict timeouts.
- Attach delegation token and service credential.
- Pipe response chunks without loading the entire answer into memory.
- Abort upstream ZenAI request when the client disconnects.
- Propagate `X-Request-Id`.
- Do not retry after stream bytes have been sent.
- Convert upstream connection failures into stable public error events.
- Use a circuit breaker only after observing repeated upstream failures; start with bounded timeouts and health checks.

### 12.6 Feature and plan configuration

- Select one canonical backend feature key: recommended `ai_features`.
- Continue accepting existing `insights` entries during a migration window.
- Add feature availability to the desired Pro/Enterprise plan seeds/configuration.
- Add `insights` to default admin menu permissions only when the plan allows it.
- Confirm behavior for super-admin, admin, manager, and staff.
- Backend enforcement is mandatory even if the sidebar hides the item.

### 12.7 Usage and audit tables

Add production migrations (names may follow existing conventions):

```sql
CREATE TABLE ai_usage_monthly (
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  year SMALLINT NOT NULL,
  month SMALLINT NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0,
  input_tokens BIGINT NOT NULL DEFAULT 0,
  output_tokens BIGINT NOT NULL DEFAULT 0,
  estimated_cost NUMERIC(14,6) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (org_id, year, month)
);

CREATE TABLE ai_action_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  location_id UUID REFERENCES locations(id),
  conversation_id UUID,
  message_id UUID,
  action_type TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  request_payload JSONB,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Do not store secrets or raw unredacted model prompts in `request_payload`. Decide whether conversation IDs remain external ZenAI UUIDs or are mirrored locally without foreign keys.

### 12.8 Migration discipline

- Create timestamped/idempotent migration files under a new or existing migration directory.
- Record applied migrations in a schema-migrations table.
- Do not depend solely on the large startup `initDB()` for production AI changes.
- Run migrations as a release step with backups and rollback notes.

---

## 13. ZenAI integrated-mode implementation

### 13.1 Configuration additions

Add settings:

```text
ZENAI_MODE=integrated
SAAS_DELEGATION_PUBLIC_KEY=<multiline/public-key reference>
SAAS_DELEGATION_ISSUER=nexdokandar-backend
SAAS_DELEGATION_AUDIENCE=nexdokandar-ai
SAAS_INTERNAL_TOOLS_URL=https://<private-saas-host>/api/v1/internal/ai
SAAS_INTERNAL_SERVICE_KEY=<secret-manager value>
SAAS_ANALYTICS_DATABASE_URL=<Release-2-only read-only DSN>
ENABLE_CURATED_TOOLS=true
ENABLE_TEXT_TO_SQL=false
MAX_TOOL_CALLS_PER_REQUEST=4
MAX_QUESTION_LENGTH=2000
AI_RESULT_ROW_LIMIT=500
AI_QUERY_TIMEOUT_MS=5000
CONVERSATION_RETENTION_DAYS=<approved value>
```

Keep secrets out of source and frontend environment variables.

### 13.2 New files

Recommended structure:

```text
backend/app/routers/internal_chat.py
backend/app/security/delegation.py
backend/app/models/request_context.py
backend/app/services/tool_registry.py
backend/app/services/tool_client.py
backend/app/services/tool_chat_pipeline.py
backend/app/services/pii_redaction.py
backend/app/services/policy.py
backend/app/db/migrations/002_saas_integration.sql
```

### 13.3 Files to modify

- `backend/app/main.py`
  - Register internal router.
  - Disable standalone auth/workspace/connection routes when `ZENAI_MODE=integrated`, or mount them only in standalone mode.
  - Remove browser CORS need in integrated mode; only Node calls ZenAI.
  - Protect `/metrics`.
  - Use a lifespan handler for shared clients/pools instead of deprecated startup events where practical.
- `backend/app/core/config.py`
  - Add validated integrated settings.
  - Fail startup in production if default JWT/encryption secrets or missing service keys are detected.
- `backend/app/services/chat_pipeline.py`
  - Preserve existing SQL pipeline as a separate mode.
  - Route integrated MVP requests to `tool_chat_pipeline`.
  - Include location/date/locale in cache and logs.
- `backend/app/db/data_access.py`
  - Scope conversation/message/history/feedback operations to external organization and user identities.
- `backend/app/db/migrate.py`
  - Move toward ordered migrations; do not destructively replace existing standalone data.
- `backend/app/services/cache.py`
  - Expand cache keys to include every authorization/data-scope input.
- `backend/app/core/logger.py`
  - Add request, user, org, location, execution mode, tools, and token usage without logging secrets/PII.

### 13.4 External identity mapping

Recommended migration approach that preserves standalone compatibility:

- `users`
  - Add `external_user_id UUID` nullable.
  - Add `auth_source TEXT NOT NULL DEFAULT 'local'` with allowed values `local`, `nexdokandar`.
  - Make `password_hash` nullable only if code paths correctly require it for local auth.
  - Unique partial index on `(auth_source, external_user_id)` where external ID is not null.
- `workspaces`
  - Add `external_org_id UUID` nullable.
  - Add `integration_source TEXT`.
  - Unique partial index on `(integration_source, external_org_id)`.
- On first integrated request:
  - Upsert external user by SaaS user ID.
  - Upsert workspace by SaaS org ID.
  - Add/update membership only if existing ZenAI data-access functions still require it.

Alternative: create dedicated `external_principals` and `tenant_bindings` tables. Use this only if standalone ZenAI must remain a first-class separately marketed product; it is cleaner but adds more code.

### 13.5 Connection model

In integrated mode:

- Do not ask each SaaS organization for database credentials.
- Do not create duplicate `connections` rows containing the same SaaS database credentials.
- Release 1 uses SaaS internal tools and no target database connection.
- Release 2 uses one centrally configured read-only analytics DSN, with database RLS establishing per-request tenant context.
- Keep existing per-workspace connection routes available only in standalone development/product mode.

### 13.6 Conversation authorization

- Conversation ID alone never authorizes access.
- Persist external org and external user linkage for each session.
- History, feedback, export, archive, and deletion must filter by both organization and user, unless an explicit admin policy allows organization-wide review.
- A new user must not be able to guess another user's session UUID.
- Decide and document whether admins can inspect employee conversations; default recommendation is no, except audited support/safety workflows.

---

## 14. Release 2 text-to-SQL security design

### 14.1 Mandatory database architecture

Preferred:

```text
Primary SaaS PostgreSQL
  --> read replica / analytics database
       --> ai_analytics schema
            --> approved views/materialized views
                 --> FORCE ROW LEVEL SECURITY
```

If a replica is not initially available, use the primary only with strict timeouts, cost limits, connection pool limits, and a kill switch. Do not let AI traffic exhaust the transaction-processing pool.

### 14.2 Dedicated role

Create a role similar to `zenai_reader`:

- `NOLOGIN` base role plus a managed login role, or a dedicated managed credential.
- `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`.
- No ownership of source tables or views.
- No access to `public` tables by default.
- `USAGE` only on `ai_analytics`.
- `SELECT` only on approved views.
- Revoke create privileges on schemas.
- Restrict function execution and search path.
- Rotate credential through the deployment secret manager.

### 14.3 Tenant context and RLS

Example policy concept:

```sql
ALTER TABLE <approved_base_or_partition> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <approved_base_or_partition> FORCE ROW LEVEL SECURITY;

CREATE POLICY zenai_org_isolation ON <table>
USING (org_id = current_setting('app.current_org_id', true)::uuid);
```

Location-sensitive views/policies must also apply the effective allowed location set. Avoid using a user-controllable SQL literal as the policy source.

### 14.4 One connection and transaction per query

The current ZenAI code acquires connections separately for cost estimation and execution. Release 2 must change this flow:

1. Acquire one connection.
2. Begin a read-only transaction.
3. `SET LOCAL app.current_org_id = ...` using safe parameter handling/config calls.
4. Set allowed/selected location context.
5. Set `statement_timeout`, `lock_timeout`, read-only transaction, and safe `search_path`.
6. Run `EXPLAIN (FORMAT JSON)` on the validated query.
7. Reject excessive estimated cost/rows.
8. Execute on the same connection and transaction.
9. Roll back/end transaction, ensuring context cannot leak through the pool.

Never set tenant context globally on a pooled connection without transaction-local cleanup.

### 14.5 Analytics views

Create only the views needed for approved business questions. Candidate names:

```text
ai_analytics.sales_daily
ai_analytics.sales_by_channel
ai_analytics.order_status_daily
ai_analytics.product_performance
ai_analytics.inventory_health
ai_analytics.inventory_valuation
ai_analytics.customer_due_summary
ai_analytics.customer_retention
ai_analytics.profit_loss_monthly
ai_analytics.staff_performance
ai_analytics.branch_performance
```

Each view should:

- Include `org_id` and `location_id` where relevant for policy enforcement.
- Use documented business definitions matching existing reports.
- Exclude raw passwords, secrets, API keys, payment tokens, biometric data, 2FA secrets, and platform credentials.
- Exclude or mask customer/staff PII unless specifically approved.
- Use stable, human-readable column comments for schema retrieval.
- Have indexes/materialization strategy validated with `EXPLAIN`.
- Include freshness metadata where materialized.

### 14.6 SQL validator changes

Replace the current generic scope injection as the security mechanism. RLS is authoritative. The validator remains defense in depth and must:

- Accept exactly one query.
- Allow SELECT only.
- Permit only approved `ai_analytics` relations.
- Reject unqualified or non-approved relations.
- Reject DML, DDL, COPY, CALL, DO, transaction commands, EXPLAIN from model output, and locking clauses.
- Reject system catalogs and information schema in generated queries.
- Restrict functions to an allowlist where practical.
- Reject dangerous, volatile, file, network, sleep, settings, advisory-lock, and extension functions.
- Reject recursive CTEs initially.
- Validate every table reference in all CTEs, subqueries, set operations, and joins.
- Enforce a result limit after parsing.
- Enforce maximum joins, CTEs, nesting depth, and query text length.
- Normalize SQL only after validation.
- Never return unvalidated SQL on parser failure.

Do not merely replace `workspace_id` with `org_id` in `tenant_scoping.py`.

### 14.7 Schema introspection changes

- Introspect `ai_analytics` only.
- Use a static allowlist or metadata registry.
- Do not sample arbitrary text values from production columns.
- If samples are required, use manually supplied safe examples or pre-approved low-cardinality columns.
- Schema embeddings can be shared by schema version because all tenants use the same SaaS schema; they need not be duplicated per organization.
- Rebuild embeddings during deployments/migrations, not through unrestricted customer-triggered introspection.

### 14.8 Query result handling

- Maximum returned rows: start at 500 for chat and 2,000 only for controlled export.
- Maximum cells and serialized response bytes.
- Redact denied fields after query as a final defense.
- Round/format monetary and percentage values consistently.
- Use organization currency and timezone.
- Do not send full raw result sets to Gemini when deterministic aggregation is sufficient.

---

## 15. Security and privacy requirements

### 15.1 Threats to test

- Cross-tenant data request: “Show organization X's sales.”
- Prompt injection requesting system prompts, credentials, or unauthorized tables.
- SQL injection through question text, filters, date fields, or identifiers.
- CTE/subquery bypass of table allowlists.
- Location bypass by staff users.
- Conversation/history IDOR.
- Export IDOR.
- Feature/plan bypass through direct API calls.
- Tool-name or argument injection.
- Service token replay/forgery.
- Cached response leakage across org/location/role/locale.
- PII leakage in model prompts, logs, errors, charts, or exports.
- Denial of service through long questions, expensive queries, repeated streams, or abandoned connections.
- Markdown/script injection in model output.
- Model recommendation attempting an unauthorized write.

### 15.2 Data classification

Create and approve a field-level classification before enabling tools/views:

- **Allowed aggregate:** totals, counts, trends, category/product aggregates.
- **Restricted:** customer/staff names, invoice numbers, supplier details.
- **Highly restricted:** phone, email, address, salary, payment details.
- **Never exposed:** password hashes, 2FA/biometric secrets, API keys, payment tokens, platform credentials, reset tokens.

### 15.3 Prompt and log policy

- State whether questions and answers may be sent to Gemini under the chosen provider terms.
- Avoid sending raw PII where aggregation answers the question.
- Redact secrets from logs.
- Store prompt/answer content only for the approved retention period.
- Support organization/user deletion requests.
- Document whether data may leave the deployment region.
- Add an admin-facing privacy notice before broad rollout.

### 15.4 Output safety

- Render controlled Markdown with raw HTML disabled.
- Validate chart structures before passing to Recharts.
- Cap labels, series, points, and string lengths.
- Treat “actions” as typed server-generated objects from an allowlist, not URLs or code from model prose.
- Never evaluate code supplied by the model.

---

## 16. Caching, quotas, and billing

### 16.1 Cache key

At minimum include:

```text
org_id
selected/allowed location scope
user permission class
question normalized form
explicit date range and resolved relative dates
locale
timezone
tool/sql mode
tool/schema version
data freshness version or TTL bucket
```

Never use only workspace + question when location or permissions can alter results.

### 16.2 Suggested initial limits

Values require product approval; safe starting examples:

- Question length: 2,000 characters.
- Concurrent streams per user: 1-2.
- Concurrent streams per organization: 5.
- Tool calls per request: 4.
- Result rows per tool: 100-500 depending on tool.
- Chat requests per minute per user: 10.
- Monthly quota by plan: define after measuring model cost.
- Request hard timeout: 30-60 seconds end-to-end; lower per tool/query.

### 16.3 Metering

- Count accepted requests, completed requests, model calls, input/output tokens, cache hits, tool calls, and failures.
- Increment usage atomically.
- Decide whether failed provider calls consume quota.
- Keep provider/model pricing configuration server-side and versioned.
- Add alert thresholds for abnormal organization usage and global spend.

---

## 17. Reliability and failure behavior

| Failure | Required behavior |
|---|---|
| ZenAI unavailable | AI endpoint returns 503; SaaS core remains healthy |
| Gemini unavailable/quota exceeded | Friendly retryable error; deterministic report cards remain available |
| Redis unavailable | Define fail-open cache/rate-limit behavior with local protection; no tenant leakage |
| Chroma unavailable | Curated tool mode continues if embeddings are not required |
| SaaS tool timeout | ZenAI reports partial/unavailable source; does not fabricate metrics |
| Browser disconnects | Node aborts ZenAI; ZenAI cancels downstream work |
| Query cost too high | Reject before execution and ask for narrower scope |
| Stream interrupted | Preserve completed message only according to explicit policy; UI offers retry |
| Invalid model JSON | One bounded repair attempt, then stable error/fallback |

Add startup/readiness checks but do not make liveness depend on every external provider.

---

## 18. Testing strategy and release gates

### 18.1 SaaS backend tests

Introduce a real test stack, recommended Vitest or Jest + Supertest.

Unit tests:

- Delegation token creation and claim validation.
- Feature/permission/plan decisions.
- Location authorization.
- Request validation.
- Tool registry argument schemas.
- Usage/quota accounting.
- Stream proxy partial chunks, cancellation, and upstream errors.

Integration tests:

- User from org A cannot request org B data.
- Staff cannot select an unauthorized branch.
- Direct calls without `insights` permission fail.
- Expired/inactive plan fails.
- Internal tool route rejects browser JWT, missing service key, forged token, wrong audience, and expired token.
- Each registered tool applies `org_id` and location filters.
- AI outage does not break non-AI endpoints.

### 18.2 ZenAI tests

Add pytest/pytest-asyncio and mocked Gemini/tool clients.

- Delegation JWT verification.
- External identity/workspace upsert.
- Conversation ownership.
- Tool selection allowlist and maximum call count.
- Tool callback context propagation.
- Cache isolation across org/location/permissions.
- PII redaction.
- NDJSON event format.
- Cancellation and timeout handling.
- Standalone routes disabled in integrated mode.

Release 2 tests:

- Validator rejects every non-approved relation at every nesting level.
- DML/DDL/unsafe functions rejected.
- RLS returns only the current org even for malicious SQL.
- FORCE RLS and non-bypass role verified from database metadata.
- Tenant context does not remain on reused pool connections.
- EXPLAIN and execution use the same transaction/context.
- Query timeout, row cap, byte cap, join cap, and cost cap work.

### 18.3 Frontend tests

Introduce Vitest + React Testing Library if not already present.

- Route and permission behavior.
- Suggested prompt and filter behavior.
- NDJSON parsing across arbitrary chunk boundaries.
- Stop/cancel behavior.
- Status, answer, error, cached, and incomplete states.
- Chart validation and table fallback.
- Feedback and export authorization errors.
- Bengali/English labels.
- Responsive and keyboard navigation.

### 18.4 End-to-end tests

Use Playwright or the team's selected browser tool:

1. Admin with AI plan opens `/admin/insights` and receives an answer.
2. Non-entitled user sees upgrade/access UI and API returns 403.
3. Staff sees only assigned branch results.
4. Switching branch changes scope and does not reuse the wrong cache.
5. Conversation reload preserves correct history.
6. Feedback is stored.
7. Export contains only authorized data.
8. ZenAI outage shows a recoverable page state.
9. Prompt injection does not expose system prompts, SQL credentials, or other tenants.
10. Smart Inventory recommendation links to the existing Smart Inventory page.

### 18.5 Mandatory go-live security gate

- [ ] No public route reaches ZenAI without Node authorization.
- [ ] No browser configuration contains ZenAI URL or model/service secrets.
- [ ] Organization and location scope are derived server-side.
- [ ] All Release 1 tools pass query-level tenant review.
- [ ] Conversation/history/export IDOR tests pass.
- [ ] Cache isolation tests pass.
- [ ] Rate limits and monthly quotas are active.
- [ ] Logs have no secrets or prohibited PII.
- [ ] Feature flag can disable AI globally and per organization.
- [ ] Release 2 remains off unless RLS/role/validator tests pass.

---

## 19. Deployment plan

### 19.1 Runtime decision gate

Before implementation sign-off, test whether the current SaaS backend deployment supports:

- Incremental NDJSON streaming without buffering.
- Request durations required by AI calls.
- Client disconnect propagation.
- Existing Socket.IO behavior.
- Concurrent ZenAI callbacks to internal tool endpoints.

The current code creates a persistent HTTP/Socket.IO server while `vercel.json` targets a serverless deployment. Recommended production arrangement is a persistent Node service (Render, Railway, Fly.io, ECS, VM, or equivalent) plus the private ZenAI service. If Vercel remains, run a proof test under production limits and document the maximum duration and streaming behavior.

### 19.2 ZenAI Render blueprint corrections

- Set `rootDir: backend`, or update build/start commands to reference `backend/requirements.txt` and `backend/app.main` correctly.
- Set a health check path.
- Use managed Redis.
- Use managed PostgreSQL for ZenAI metadata.
- Chroma local persistence requires a persistent disk and a single-writer deployment. For multi-instance scaling, migrate embeddings to a shared vector store such as pgvector.
- Do not expose internal ZenAI publicly when private networking is available.

### 19.3 Environment matrix

SaaS backend:

```text
ZENAI_ENABLED=false|true
ZENAI_INTERNAL_URL=
ZENAI_INTERNAL_SERVICE_KEY=
AI_DELEGATION_PRIVATE_KEY=
AI_DELEGATION_KEY_ID=
AI_DELEGATION_ISSUER=nexdokandar-backend
AI_DELEGATION_AUDIENCE=nexdokandar-ai
AI_DEFAULT_MONTHLY_QUOTA=
AI_REQUEST_TIMEOUT_MS=
AI_GLOBAL_KILL_SWITCH=false
```

ZenAI:

```text
ZENAI_MODE=integrated
ZENAI_DATABASE_URL=
REDIS_URL=
GEMINI_API_KEY=
SAAS_DELEGATION_PUBLIC_KEY=
SAAS_DELEGATION_ISSUER=nexdokandar-backend
SAAS_DELEGATION_AUDIENCE=nexdokandar-ai
SAAS_INTERNAL_TOOLS_URL=
SAAS_INTERNAL_SERVICE_KEY=
ENABLE_CURATED_TOOLS=true
ENABLE_TEXT_TO_SQL=false
SAAS_ANALYTICS_DATABASE_URL=
ZENAI_ENCRYPTION_KEY=
DEBUG=false
```

SaaS frontend:

- No ZenAI-specific URL or secret.
- Continue using `VITE_BASE_URL` for the SaaS backend.

### 19.4 Network policy

- Browser can reach SaaS frontend/backend only.
- SaaS backend can reach ZenAI internal API.
- ZenAI can reach Gemini, ZenAI PostgreSQL, Redis, and the SaaS internal tool endpoint.
- Release 2 ZenAI can reach the analytics database/replica only.
- Analytics database credentials cannot access transaction writes.

---

## 20. Observability

### 20.1 Correlation

Generate or accept a safe `X-Request-Id` at the SaaS backend and propagate it to ZenAI, tool callbacks, logs, and response headers.

### 20.2 Metrics

- Request count by status/plan/mode.
- Active streams.
- End-to-end and stage latency.
- Gemini latency/error/rate-limit counts.
- Tool latency/error counts.
- Query cost, duration, rows, and rejection reason for Release 2.
- Cache hit rate.
- Token usage and estimated cost.
- User/org quota rejections.
- Cancellation/disconnection count.
- Feedback up/down rate.

Do not put raw organization/user IDs in high-cardinality metric labels; keep them in structured audit logs where appropriate.

### 20.3 Alerts

- AI error rate above threshold.
- P95 latency regression.
- Provider quota/spend threshold.
- Repeated security-policy rejection.
- Database query timeout/cost rejection spike.
- Redis/ZenAI DB unavailable.
- Unexpected cross-scope/cache test failure in synthetic monitoring.

---

## 21. Data retention and lifecycle

Decisions required before launch:

- Conversation retention duration.
- Query/tool log retention.
- Feedback retention.
- Whether administrators can export conversation data.
- User/org deletion behavior.
- Backup retention for ZenAI metadata.

Implementation requirements:

- Scheduled deletion/anonymization job.
- Cascade or explicit cleanup when a SaaS organization is deleted.
- Archived conversations remain subject to retention.
- Cached data expires independently and promptly.
- Do not retain raw tool results longer than needed; prefer summaries and sanitized snapshots.

---

## 22. Rollout plan

### Phase 0: Decisions and baseline

- [ ] Approve this architecture and canonical feature key.
- [ ] Choose production runtime/provider topology.
- [ ] Define initial plans, quotas, data retention, and PII policy.
- [ ] Record baseline report outputs for test organizations.
- [ ] Add `ZENAI_ENABLED` and global kill switch, default off.
- [ ] Create staging organizations with intentionally distinct data for isolation testing.

### Phase 1: ZenAI integrated identity and internal API

- [ ] Add integrated configuration and delegation verification.
- [ ] Add external organization/user mapping.
- [ ] Add internal chat endpoint.
- [ ] Add curated tool client and tool-mode orchestration.
- [ ] Scope cache, sessions, history, feedback, and logs correctly.
- [ ] Disable standalone auth/connect routes in integrated production mode.
- [ ] Add tests and protected health/metrics.

### Phase 2: SaaS internal tool layer

- [ ] Create AI module and internal tool registry.
- [ ] Review/refactor report service functions for explicit `orgId`/`locationId` arguments.
- [ ] Add service authentication and delegation validation.
- [ ] Register initial read-only tools.
- [ ] Add result schemas, limits, and PII redaction.
- [ ] Add usage/audit migrations.
- [ ] Add tool-level tenant tests.

### Phase 3: SaaS public BFF endpoints

- [ ] Add public chat/history/feedback/export/insight/usage routes.
- [ ] Add plan, permission, location, and quota enforcement.
- [ ] Implement streaming proxy and cancellation.
- [ ] Normalize errors and propagate request IDs.
- [ ] Add integration tests with mocked ZenAI.

### Phase 4: Native frontend

- [ ] Add route and page.
- [ ] Add chat streaming hook/parser.
- [ ] Add cards, charts, tables, sources, feedback, filters, and history.
- [ ] Add English/Bengali content.
- [ ] Add upgrade/permission/error/empty states.
- [ ] Link inventory insights to Smart Inventory.
- [ ] Add frontend and E2E tests.

### Phase 5: Staging hardening

- [ ] Deploy private ZenAI and staging Node backend.
- [ ] Run tenant/location isolation suite.
- [ ] Run prompt-injection and IDOR suite.
- [ ] Validate production-like streaming runtime.
- [ ] Load test expected concurrency and cancellation.
- [ ] Review logs for secrets/PII.
- [ ] Tune quotas, timeouts, tool result sizes, prompts, and caching.

### Phase 6: Limited production rollout

- [ ] Enable for internal organization only.
- [ ] Enable for a small Enterprise/Pro pilot cohort.
- [ ] Monitor accuracy, latency, cost, failures, and feedback.
- [ ] Keep global/per-org kill switch tested.
- [ ] Expand gradually after review.

### Phase 7: Optional hardened text-to-SQL

- [ ] Create analytics schema/views.
- [ ] Create non-bypass read-only role and FORCE RLS.
- [ ] Replace scope injection security assumptions.
- [ ] Refactor query executor to one scoped transaction.
- [ ] Restrict introspection/embeddings.
- [ ] Complete SQL security test corpus and database review.
- [ ] Enable behind a second flag for internal users first.

---

## 23. Rollback plan

- Set global AI kill switch to disable `/api/v1/ai/*` while leaving the SaaS operational.
- Hide the menu/page through feature configuration without deleting code.
- Stop ZenAI deployment independently.
- Revoke/rotate internal service keys and delegation keys.
- Revoke `zenai_reader` database login immediately if Release 2 is implicated.
- Disable `ENABLE_TEXT_TO_SQL` independently of curated tool mode.
- Preserve audit evidence before purging compromised caches/sessions.
- Database migrations should have documented down steps where safe; avoid destructive rollback of usage/audit history.

---

## 24. Manual review checklist

### Architecture/product

- [ ] Native page + private service architecture accepted.
- [ ] Curated-tools-first approach accepted.
- [ ] Standalone ZenAI product mode still needed or not decided.
- [ ] AI plan availability decided.
- [ ] User roles allowed to use AI decided.
- [ ] Admin visibility into employee conversations decided.
- [ ] Supported English/Bengali behavior decided.

### Data/security

- [ ] Initial tool list approved.
- [ ] PII classification approved.
- [ ] Gemini/provider data terms reviewed.
- [ ] Retention periods approved.
- [ ] Organization/location rules confirmed.
- [ ] Write-action confirmation policy approved.
- [ ] Text-to-SQL explicitly off for Release 1.

### Operations

- [ ] Node streaming deployment validated.
- [ ] Private networking approach selected.
- [ ] Redis/ZenAI PostgreSQL provisioned.
- [ ] Chroma persistence/scaling approach selected.
- [ ] Secret rotation owner identified.
- [ ] Monitoring and budget alerts configured.
- [ ] Rollback/kill switch tested.

---

## 25. Definition of done for Release 1

Release 1 is complete only when:

1. `/admin/insights` is a native protected SaaS route.
2. No second login, workspace creation, or database connection setup is visible to SaaS users.
3. Browser traffic goes only to the SaaS backend.
4. Backend enforces JWT, plan feature, menu permission, organization, location, and quota.
5. ZenAI verifies short-lived delegation context.
6. At least the approved sales, product, inventory, profit/loss, dues, and retention tools work.
7. Answers stream with status, final answer, chart/table, confidence, source scope, and stable errors.
8. Conversation history, feedback, cancellation, and controlled export work.
9. English and Bengali UI strings are present.
10. Cross-tenant, cross-location, IDOR, cache, and prompt-injection tests pass.
11. Core SaaS functionality remains available during ZenAI/provider outages.
12. Usage, audit, latency, errors, and estimated model cost are observable.
13. Feature flags and rollback are tested.
14. Direct text-to-SQL is still disabled unless the separate Release 2 gate passes.

---

## 26. Estimated implementation order and effort

These are rough engineering estimates for one developer familiar with the repositories; they are planning aids, not commitments.

| Workstream | Estimate | Depends on |
|---|---:|---|
| Decisions, feature flags, staging fixtures | 1-2 days | Product/security decisions |
| ZenAI integrated auth, identity mapping, tool mode | 4-7 days | Delegation contract |
| SaaS internal tools and security review | 4-7 days | Approved tool catalog |
| SaaS public AI gateway and streaming | 3-5 days | ZenAI internal endpoint |
| Native frontend experience | 5-8 days | Public API contract |
| Automated tests and staging hardening | 5-10 days | All MVP components |
| Deployment/observability/pilot | 2-5 days | Runtime/provider access |
| Optional analytics views + hardened SQL | 10-20+ days | DBA/security review |

Expected Release 1: approximately **24-44 developer-days**, depending on test infrastructure, deployment changes, UI polish, and how many existing reports require tenant/location refactoring.

---

## 27. Open decisions requiring manual confirmation

1. Which plans receive AI Insights: Pro only, Enterprise only, both, or usage-based add-on?
2. Canonical feature key: adopt `ai_features` and migrate `insights`, or use `insights` everywhere?
3. Can managers/staff use AI, and which tool categories are role-restricted?
4. May admins select all branches? May managers compare only assigned branches?
5. Conversation retention and admin visibility policy.
6. Whether customer/staff names or only aggregates may be sent to Gemini.
7. Production deployment provider and whether the Node backend will move off serverless hosting.
8. Initial monthly quotas and overage behavior.
9. Whether standalone ZenAI must remain deployable as a separate product.
10. Whether Release 2 text-to-SQL is a roadmap requirement or can remain optional indefinitely.

---

## 28. Final recommendation

Implement the integration without rewriting either SaaS application. Add a focused AI module to the Node backend and a native AI Insights page to React, then adapt ZenAI into an integrated private-service mode. Ship curated, tenant-safe business tools first. Treat direct SQL as a separate security project backed by analytics views, a non-bypass read-only role, RLS, and exhaustive adversarial testing.

The one change that must not be shortcut is tenant isolation: ZenAI's current `workspace_id` outer-query injection is not compatible with the SaaS `org_id` model and must not be used as the production security boundary.
