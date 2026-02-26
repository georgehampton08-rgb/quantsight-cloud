# QuantSight Strategic Intelligence & Architecture Dossier

**Role**: Senior Systems Architect + Research Agent
**Task**: Absorb, analyze, and expand deep technical knowledge necessary to build, harden, and scale the QuantSight Cloud system (frontend + backend).

## Core Mechanisms for Research

1. The provided local codebase context.
2. Internet research (official documentation, production architecture case studies, GitHub issues, Cloud Run docs, Firestore scaling docs, FastAPI best practices, React performance guides, SSE reliability patterns, Electron IPC design references, etc.)

*NOTE: Treat this as a structured intelligence-gathering operation — not surface-level browsing.*

---

## 🏗️ SYSTEM CONTEXT

**Frontend:**

- React 18 + Vite + TypeScript
- HashRouter
- Context-based global state (OrbitalContext, HealthContext, etc.)
- Custom SSE implementation (EventSource)
- Centralized ApiContract transport layer (IPC ↔ Web fallback)
- Electron desktop + Web deployment
- Firebase Hosting

**Backend:**

- FastAPI + Uvicorn
- Deployed on Google Cloud Run
- Firestore database
- SSE live stream endpoints
- Modular route registry
- Vanguard autonomous middleware (incident detection + profiling)
- Gemini AI integration for triage

**Transport:**

- `ApiContract.execute()`
- IPC (`window.electronAPI`)
- Web fallback via `fetch()`
- Shadow-race simulation caching pattern

---

## 🎯 OBJECTIVES & DOMAINS TO RESEARCH

You must build a comprehensive knowledge dossier structured in the following domains:

**A) React Architecture Mastery**

- Advanced Context patterns vs Zustand/Redux tradeoffs
- Large SPA route organization
- HashRouter production implications
- ErrorBoundary production patterns
- Re-render control + memoization patterns
- Handling async orchestration in heavy pages (like PlayerProfilePage)
- Best practices for separating UI from service logic
- Type-safe API contract enforcement in TS
- Build optimization with Vite

**B) FastAPI Production Design**

- Route modularization patterns
- Avoiding wildcard shadowing
- Dependency injection best practices
- Structured error handling
- Background task orchestration
- SSE in FastAPI (production-grade)
- Handling Cloud Run concurrency
- Preventing import-failure silent crashes

**C) Google Cloud Run Production Patterns**

- Cold start mitigation
- Concurrency configuration
- Health checks and startup probes
- Container fail-fast patterns
- Logging best practices
- Deployment rollbacks
- Canary releases

**D) Firestore Scaling & Integrity**

- Indexing best practices
- Hot document protection
- Quota management
- Collection TTL strategies
- High-frequency write patterns
- Real-time listener scaling
- Firestore cost controls

**E) SSE & Real-Time Systems**

- EventSource production hardening
- Circuit breaker patterns
- Visibility-aware streaming
- Backpressure handling
- Stream resumption strategies
- Comparing SSE vs WebSockets
- Production retry budgets

**F) Electron IPC + Hybrid Apps**

- Secure preload design
- Context isolation best practices
- IPC performance constraints
- Offline-first architecture
- Preventing dual-transport drift

**G) API Contract Governance**

- Contract validation patterns
- Schema versioning
- Runtime validation (zod/io-ts)
- Preventing drift between frontend & backend
- OpenAPI enforcement strategies
- Type generation from FastAPI schemas

**H) Observability & Reliability**

- Structured logging
- Distributed tracing
- Error fingerprinting
- Production metrics dashboards
- SLO/SLA design
- Incident lifecycle automation
- Smoke harness design patterns

---

## 📋 RESEARCH RULES & DELIVERABLE FORMAT

1. **Search extensively**: Official documentation, production case studies, GitHub discussions, architecture blog posts, real-world scaling failures.
2. **Cite source types**: (docs/blog/github/rfc) but do not just dump raw links.
3. **Extract the hard truths**: Patterns, anti-patterns, failure stories, and recommended production-grade designs.
4. **No vague summaries**. For each domain:
   - Identify risks specific to QuantSight.
   - Recommend architecture adjustments.
   - Highlight scaling inflection points.
   - Propose guardrails.
5. **Structure the output exactly like this:**

   ```
   DOMAIN NAME
   ─ Current State Risk
   ─ Production Patterns (researched)
   ─ Anti-Patterns Found in Industry
   ─ Direct Recommendations for QuantSight
   ─ Optional Future Upgrade Paths
   ```

6. **Tone**: This must read like a technical intelligence brief, not a blog post. Avoid fluff, no motivational tone, no emojis, zero repetition.

***Deliverable***: Produce a comprehensive engineering intelligence dossier that empowers a senior architect to harden QuantSight to enterprise-grade reliability, prevent architectural drift, avoid known scaling traps, enforce long-term contract discipline, and prepare for 10x scale without a rewrite.
