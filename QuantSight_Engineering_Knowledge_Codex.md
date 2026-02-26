# QuantSight Engineering Knowledge Codex

## 1. Architectural Doctrine

### Core System Invariants

| Invariant | Classification | Description | Protocol |
|-----------|----------------|-------------|----------|
| **Transport Agnosticism** | MANDATORY | The frontend must never assume execution context (Web vs. Desktop). | All data requests MUST route through an abstraction layer (`ApiContract`). Synchronous IPC is strictly prohibited. |
| **Infrastructure as Code** | MANDATORY | Server configurations must be reproducible without human intervention. | Cloud Run deploys MUST use explicit revision flags and environment injection via GCP Secret Manager. |
| **Graceful Degradation** | MANDATORY | Subsystem failure must not result in total system collapse. | Any downstream dependency failure (e.g., AI inference timeout) MUST resolve to a `degraded` state flag, not an unhandled exception. |
| **Single Source of Truth** | RECOMMENDED | Business rules must exist once, centrally located on the backend. | The frontend MUST act strictly as a presentation and telemetry routing layer. Calculation of analytical derivatives belongs on the backend. |

### Transport Guarantees

- The `ApiContract` transport layer MUST implement fallback logic: `IF` IPC (`window.electronAPI`) encounters a pipeline failure or timeout `-> THEN` gracefully fallback to Web `fetch()`.
- The Shadow-Race implementation (simultaneous evaluation of local cache vs network) MUST NOT block the main render loop. Stale data MUST render immediately until the network delta is resolved.

### Contract Immutability Rules

- Backend API signatures are immutable. An endpoint MUST NOT change its signature (adding required fields, renaming fields) without establishing a formalized `/v2/` namespace.
- Pydantic models MUST NOT drop properties; deprecation requires a 30-day sunset utilizing explicit HTTP Warning headers.

### Context Discipline

- "God Contexts" (monolithic React Context providers) are prohibited.
- Global Context (`useContext`) is reserved strictly for theme, auth, and environment configuration.
- High-frequency telemetry or deeply nested state MUST utilize atomic slicing (e.g., Zustand) to prevent prop-drilling and unwanted render cascades.

### Route Registration Laws

- Backend routes MUST be registered via modular `APIRouter` segments based on domain boundaries (e.g., `/vanguard/`, `/pulse/`).
- Frontend routing (via `HashRouter` or `BrowserRouter`) MUST lazy-load heavy sub-applications using `React.lazy` and `Suspense` boundaries to protect initial paint metrics.

---

## 2. Frontend Production Protocols

### Rendering Rules

- **No Inline Functional Instantiation:** Functions passed as props to memoized child components MUST be wrapped in `useCallback`.
- **Derivation Over Synchronization:** Values computable from existing state MUST be calculated dynamically during the render cycle, NEVER synchronized into state via `useEffect`.

### State Mutation Rules

- Local state MUST be treated as deeply immutable. Array/Object manipulations must map entirely new references to trigger reconciliation efficiently.

### API Consumption Discipline

- UI components MUST NOT call `fetch` or IPC bridges directly.
- Components MUST consume data via explicit hooks (`usePulseTelemetry`, `useVanguardStatus`) which wrap the unified `ApiContract`.

### SSE Lifecycle Contract

- Every `EventSource` instantiation MUST have an exact `cleanup` routine returned by the `useEffect` that triggers `.close()`.
- Orphaned SSE connections constitute a memory leak and violate production metrics.

### Re-render Prevention Standards

- Contexts that mix rapidly changing data (e.g., live match telemetry) with static data (e.g., user profiles) violate performance laws.
- `React.memo` is REQUIRED on any list-item component that renders > 50 instances simultaneously.

### Type Safety Mandates

- Typescript `strict: true` is MANDATORY.
- The use of `any` is PROHIBITED. Use `unknown` and Type Guards if the payload is genuinely unstructured.
- Implicit `any` will break the CI build.

### Error Boundary Policies

| Boundary Scope | Requirement | Impact on Failure |
|----------------|-------------|-------------------|
| **Root Application** | MANDATORY | Displays formal "System Offline" UI and attempts reconnection. |
| **Page Level** | MANDATORY | Quarantines page crash; allows navigation to other workspaces. |
| **Widget/Component** | RECOMMENDED | Disables specific widget (e.g., Live Pulse panel) while preserving the host page. |

### Anti-Pattern Registry

- **State Duplication:** Copying prop data into local state without an explicit `initialValue` naming convention.
- **Micro-Effects:** Chaining `useEffect` hooks where one effect updates state, triggering the next effect, resulting in 4-5 render cycles before user visibility.
- **Swallowing Errors:** Catch blocks that log to `console.error` but fail to report to Vanguard or the central metrics engine.

---

## 3. Backend Reliability Protocols

### Route Isolation Laws

- Each functional domain must reside in its own `APIRouter`. Domains must not query each other's databases without going through an internal service abstraction.

### Wildcard Protection Standards

- Static route declarations MUST precede variable routes.
- Example: `@app.get("/users/me")` MUST be declared before `@app.get("/users/{user_id}")`. Violations will cause endpoint shadowing.

### Import-Failure Fail-Fast Rules

- "Deep Import Crashes" (where an endpoint fails at runtime due to a deferred missing import) MUST be mitigated by strict container startup testing. `pytest` builds MUST perform a full AST load simulation.

### Dependency Injection Best Practices

- FastAPIs `Depends()` MUST be leveraged for database clients, cache connections, and Vanguard execution to guarantee clean Testability/Mocking interfaces.
- Global singletons (unless heavily guarded like `SubsystemOracle`) are strictly prohibited within route logic.

### Structured Exception Taxonomy

- Throwing raw Python exceptions directly answers to the client is barred.
- All errors MUST be wrapped in a `QuantSightBaseException` hierarchy, which is mapped via global exception handlers to precise HTTP codes and standardized JSON error fingerprints.

### Background Task Governance

- CPU-heavy operations (e.g., Vertex Monte Carlo simulations, AI prompt execution) MUST NOT block the primary `asyncio` event loop.
- Blocking execution must be dispatched to `asyncio.to_thread` or an external Cloud Task queue.

---

## 4. Cloud Run Production Hardening

### Cold Start Mitigation Doctrine

- **CPU Allocation:** "Always-on" CPU allocation MUST be enabled for the Vanguard routing layer to prevent the ASGI worker from freezing between invocations.
- **Lean Init:** Global execution logic at module initialisation time MUST be eradicated. Connection pools should initialize lazily or via the ASGI Lifespan event.

### Concurrency Configuration Standards

- Max concurrent requests per instance MUST be explicitly tuned via memory profiling. If QuantSight's footprint is ~300MB under load, and the limit is 512MB, concurrency should be constrained (e.g., 80) to force horizontal scaling over OOM crashing.

### Health Check Protocol

- Every deployed container MUST expose a synchronous `/healthz` liveness probe and an asynchronous `/readyz` probe.
- Until `/readyz` confirms a successful Firestore handshake, the container MUST NOT accept traffic.

### Logging Requirements

- `print()` is PROHIBITED.
- Standardized `structlog` configurations MUST output JSON natively. GCP Operations expects formal JSON boundaries to index attributes like `severity` and `correlation_id` correctly.

### Deployment Rollback Protocol

- Every Cloud Run deployment MUST be tagged with the exact Git SHA and Semantic Version.
- IF synthetic smoke tests fail post-deploy -> THEN Cloud Build MUST execute an immediate 100% traffic redirection to the previous stable revision.

### Canary Release Strategy

- Changes involving Vanguard Middleware or AI prompt schemas MUST be released via target tags enabling traffic splits (e.g., 10% Canary / 90% Stable) to monitor for error spike anomalies.

### Container Boot Validation Checklist

1. Environment variables injected securely (Secret Manager).
2. Lifespan startup triggers database pool creation.
3. Dummy query dispatched to Firestore.
4. Liveness probe responds `200 OK`.

---

## 5. Firestore Scaling & Integrity Law

### Index Governance

- Client-side sorting on large queries is barred. All compound queries MUST have matching definitions in `firestore.indexes.json`.
- Missing indexes must result in developer environment errors, not production latency.

### Hot Document Protection

- **LAW:** Firestore physically limits sustained writes to a single document to **1 write per second**.
- High-velocity updates (like telemetry) MUST be buffered in memory via FastAPI and flushed in batches, or distributed across Sharded Counter documents.

### TTL Enforcement Standards

- Ephemeral records (AI inference logic loops, transient incident definitions) MUST define an `expires_at` timestamp attribute.
- Firestore TTL policies MUST be active to automatically purge these records, preventing unbound storage bloat and billing shocks.

### Cost Containment Rules

- Polling a Firestore collection with a massive snapshot listener where `limit()` is undefined is strictly PROHIBITED.
- Reads MUST be heavily cached where possible. Live listeners are reserved exclusively for Real-Time required data.

### Write Burst Handling Strategy

- Bulk data ingestion MUST utilize Firestore `BulkWriter` algorithms with geometric backoff to gracefully handle quota pressure logic.

### Schema Drift Prevention

- Documents in Firestore are schemaless. QuantSight enforces schemas at the application edge. All reads from Firestore MUST strictly validate through a Pydantic structure immediately upon retrieval before propagating into the business logic.

---

## 6. Real-Time Streaming Doctrine

### SSE Retry Budgets

- `EventSource` reconnections MUST NOT hammer the API Gateway.
- Implement strictly Truncated Exponential Backoff. (e.g., Retry 1: 2s, Retry 2: 4s, Retry 3: 8s, up to max 60s).
- After 5 consecutive failures, the UI must display a `DEGRADED: LIVE TELEMETRY OFFLINE` flag to the user and halt automated connection spams.

### Circuit Breaker Formal Spec

- The Vanguard Surgeon tier MUST track endpoint failure rates over a sliding 60-second window.
- IF failure threshold > 50% -> Transition state to `OPEN` (Fail immediately without network).
- Probe via `HALF-OPEN` states incrementally.

### Visibility-State Governance

- When the browser/desktop Page Visibility API detects the QuantSight window is minimized or hidden, telemetry streams MUST be paused or reduced to long-polling to conserve frontend CPU constraints and backend throughput.

### Backpressure Rules

- If the frontend React thread cannot paint incoming SSE chunks fast enough, the internal buffered receiver must deterministically drop contiguous middle-state events and only enforce the most recent complete state vector.

### Event Replay Strategy

- FastAPI SSE streams MUST inject an `id` field dynamically.
- The frontend MUST submit the `Last-Event-ID` header on reconnection so the backend can replay any delta chunks missed during the drop window.

### When to Migrate to WebSockets

- If the system architecture expands to require bidirectional sub-50ms latency (e.g., realtime collaborative UI or highly interactive local simulations pushed back to the cloud synchronously), SSE is deprecated for pure WebSockets.

---

## 7. API Contract Constitution

### Schema Versioning Protocol

- Changes to API logic that alter standard return shapes constitute a Breaking Change.
- Breaking changes require a new URL path (e.g., `/api/v2/pulse/`) to run concurrently with `v1` until all Electron clients establish parity.

### Breaking-Change Procedure

1. Create isolated endpoint.
2. Deploy concurrent architecture.
3. Publish forced update prompt on Electron client.
4. Wait 30 days. Observe telemetry.
5. Decommission `v1`.

### Runtime Validation Strategy

- **Frontend Validation:** The web fallback `fetch()` must validate the payload via Zod before inserting data into atomic stores. Data violating the schema is dropped and flagged to Vanguard.
- **Backend Validation:** Incoming requests rigidly processed by Pydantic. Malformed bodies result in `422 Unprocessable Entity` naturally.

### Type Generation Discipline

- Manual TypeScript interfaces mirroring Python Pydantic models are BANNED.
- An `openapi-typescript-codegen` script MUST run during the build process to guarantee 1:1 typing parity directly from the FastAPI OpenAPI spec.

### Shadow-Race Preservation Spec

- For critical data paths, the frontend dispatches an IPC request and a Web request simultaneously. The primary renderer accepts the first successful resolution; the slower resolution is validated against the former silently to detect environment drift.

### Electron Fallback Governance

- Desktop implementations MUST operate successfully even if IPC bridges collapse, deferring entirely to standard web authentication pathways over HTTPS.

---

## 8. Observability & Incident Governance

### Structured Logging Schema

- Logs MUST consist of: `timestamp_utc`, `severity`, `correlation_id`, `subsystem`, `event_type`, and `message`.
- No parsing of string blobs. All tools query via schema keys.

### Correlation ID Requirements

- A UUID generated exactly once at the frontend click/interaction event MUST be propagated through IPC, to the fetch headers (`X-Correlation-ID`), into the FastAPI middleware, through Vanguard, and strictly attached to downstream logs.

### Distributed Trace Standard

- Adhere to OpenTelemetry context propagation standard (`traceparent`). Ensures unified visibility when external modules (e.g., Gemini invocations) span multi-second epochs.

### Vanguard Subsystem Integration Rules

- `SubsystemOracle` MUST NOT impact critical request latency. Vanguard profiling is completely asynchronous and only evaluates the aggregated request traces post-response.

### Incident Fingerprint Lifecycle

- Errors are tokenized into strict fingerprints (`ModuleName:LineNumber:ExceptionType`).
- Identical fingerprints occurring within a 30-minute window are incremented rather than heavily replicated in the Archivist database to prevent spam.

### AI Triage Guardrails

- LLM summarizations of incidents MUST NOT execute autonomous rollback commands unsupervised. They operate as read-only advisory summaries.
- Inference context is strictly sanitized of all authentication secrets before reaching the LLM prompt.

---

## 9. Security Hardening Charter

### IPC Surface Restriction Rules

- `contextIsolation: true` in Electron is MANDATORY.
- The preload script MUST expose exclusively narrowed, strongly typed channel names (e.g., `get-pulse-data`) mapped explicitly to `ipcRenderer.invoke` or `.on`.
- Synchronous `ipcRenderer.sendSync` is BANNED as it introduces main-thread locking and security exploitation angles.

### Rate Limiting Governance

- All exposed APIs enforce Token Bucket rate limiting via Redis or memory caches matching the client IP or designated User ID.

### Abuse Mitigation

- Rapid anomalous mutations simulating bot-level interactivity trigger an immediate backend quarantine flag, restricting the correlation ID or IP space to heavily degraded, long-cached read access.

### Firestore Security Rule Alignment

- Accessing the database directly via Web config requires robust Firestore Security Rules evaluating Bearer/JWT tokens. The default rule is ALWAYS `allow read, write: if false;`.

### LLM Key Protection Rules

- Never embed Gemini keys in `.env` files within Docker images. Keys MUST be requested at runtime exclusively via GCP Secret Manager and held strictly within volatile memory.

---

## 10. Deployment & CI Enforcement Protocol

### Required CI Checks

| Check | Requirement | Purpose |
|-------|-------------|---------|
| `tsc --noEmit` | MANDATORY | Validates absolute frontend type parity. |
| `pytest` | MANDATORY | Confirms core logic and import hierarchies remain intact. |
| `pylint / ruff` | MANDATORY | Enforces python structural and syntax discipline. |
| Bandit / Snyk | RECOMMENDED| Prevents unintentional dependency vulnerabilities. |

### Pre-Deploy Validation Checklist

- [ ] Database index parameters verified against `firestore.indexes.json`.
- [ ] Endpoints validate 100% on synthetic test harnessing.
- [ ] API Contract TS compilation step passed cleanly.

### Post-Deploy Verification Steps

- Smoke harness execution directly against the production Cloud Run URL (simulated authentication) prior to enabling full DNS resolution updates.

### Schema Migration Approval Process

- Altering the fundamental arrangement of Firestore documents or SQL schemas requires a formal migration script utilizing defensive `try-except` data healing routines that are heavily audited prior to execution.

---

## 11. Failure Case Compendium

### Real-World Industry Failures

| Incident Pattern | Industry Example | How It Occurs | CloudSight Prevention Mechanism |
|------------------|------------------|---------------|---------------------------------|
| **Connection Storm/Thundering Herd** | Discord Server Collapse | Clients disconnecting simultaneously hammer the API all at once. | Truncated Exponential Backoff on SSE & Reconnections smooths the curve. |
| **Hot Document Write Crash** | Firebase Mobile App Shutdown | Updating a central "global stats" document on every user action instantly exceeds 1/sec limits. | Batched writes and Distributed Sharded Counters. |
| **Deep Import Failure** | AWS Lambda silent drop | A conditional deep import fails at runtime over networking, but startup tests passed. | Strict Python AST load simulation required in CI PyTest boundaries. |
| **Memory Leak via Retained References** | Netflix Zuul Edge Gateway | Storing connections or unhandled promises in global arrays that never garbage collect. | Strict `useEffect` cleanup procedures over SSE streams; Python async generators wrapped in `finally` close blocks. |

---

## 12. Scaling Roadmap Triggers

**Threshold Indicator: 10x User Volume Acceleration**

- **When to shard Firestore:**
  - *Trigger:* Write thresholds on player analytics approach 500 writes/second in specific regions.
  - *Action:* Move rapidly mutating historical state metrics to Bigtable; utilize Firestore explicitly for user configuration only.
  
- **When to introduce Redis:**
  - *Trigger:* "Pulse" telemetry computation begins exceeding 512MB RAM across standard Cloud Run containers due to in-memory buffering.
  - *Action:* Migrate active session state and rate limiting out of container memory into Cloud Memorystore (Redis).

- **When to add message queues:**
  - *Trigger:* Vanguard LLM invocations and Monte Carlo inference operations experience degraded latency due to HTTP/ASGI connection timeouts.
  - *Action:* Isolate AI and Simulation logic into background worker pools orchestrated completely by Google Cloud Tasks/PubSub.

- **When to separate services:**
  - *Trigger:* A single deploy of the monolithic FastAPI application fails to build within 3 minutes or exceeds deployment layer size constraints.
  - *Action:* Execute the "Strangler Fig" pattern. Extract the Vanguard autonomous layer into a dedicated gRPC microservice separate from the data telemetry pipelines.
