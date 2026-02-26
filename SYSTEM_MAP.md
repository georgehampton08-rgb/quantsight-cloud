# QuantSight Cloud — System Map

*Last updated: 2026-02-26 | Auto-generated during Vanguard wiring session*

---

## 🗺 QUICK REFERENCE

| Layer | Technology | URL / Path |
|-------|-----------|------------|
| **Frontend** | React + Vite + HashRouter | `https://quantsight-prod.web.app` |
| **Backend API** | FastAPI + Uvicorn on Cloud Run | `https://quantsight-cloud-458498663186.us-central1.run.app` |
| **Database** | Firestore (Cloud) | Project: `quantsight-prod` |
| **Hosting** | Firebase Hosting | Auto-deploys from `dist/` |
| **Container** | Google Cloud Run | Region: `us-central1` |
| **Source** | GitHub | `georgehampton08-rgb/quantsight-cloud` |

---

## 🖥 FRONTEND — Page → API Mapping

### Route Tree (`src/components/MainCanvas.tsx`)

```
/#/                → CommandCenterPage
/#/player          → PlayerProfilePage
/#/player/:id      → PlayerProfilePage
/#/matchup         → MatchupEnginePage
/#/matchup-lab     → MatchupLabPage
/#/team            → TeamCentralPage
/#/settings        → SettingsPage          ← includes VanguardHealthWidget
/#/injury-admin    → InjuryAdmin
/#/pulse           → PulsePage
/#/vanguard        → VanguardControlRoom
```

### Page → Endpoint Mapping

| Page | Backend Endpoints Called | Status |
|------|--------------------------|--------|
| **CommandCenterPage** | `/teams`, `/schedule`, `/live/leaders`, `/live/games` | ✅ Live |
| **PlayerProfilePage** | `/players/search`, `/player/{id}`, `/roster/{team_id}`, `/nexus/*` | ⚠️ Nexus 404 |
| **MatchupEnginePage** | `/matchup/analyze`, `/matchup/{id}/{opp}`, `/radar/{id}` | ✅ Live |
| **MatchupLabPage** | `/matchup-lab/games`, `/matchup-lab/crucible-sim` | ✅ Live |
| **TeamCentralPage** | `/teams`, `/teams/{abbrev}` | ✅ Live |
| **SettingsPage** | `/vanguard/admin/stats` (via widget), `/admin/collections/status` | ✅ Fixed |
| **InjuryAdmin** | `/admin/injuries/*`, `/players/search` | ✅ Live |
| **PulsePage** | `/live/stream` (SSE), `/live/leaders`, `/live/games`, `/live/status` | ⚠️ SSE intermittent |
| **VanguardControlRoom** | `/vanguard/admin/stats`, `/vanguard/admin/incidents`, `/vanguard/admin/learning/status`, `/vanguard/admin/incidents/{fp}/resolve`, `/vanguard/admin/incidents/{fp}/analyze` | ✅ Fixed |

### Frontend Context Providers (`src/context/`)

```
OrbitalContext   — Global state (player/team selection, nav)
HealthContext    — Backend connectivity status
ProgressContext  — Global loading progress bar
ToastContext     — Toast notification system
LiveGameContext  — Live game feed state (SSE-connected)
```

---

## ⚙️ BACKEND — Route Registry

All routes registered in `backend/main.py`. Grouped by module below.

### Core / Admin (`api/admin_routes.py`)

```
GET  /admin/init-collections
GET  /admin/collections/status
POST /admin/seed/sample-data
POST /admin/collections/{name}/clear
```

### Public Data (`api/public_routes.py`)

```
GET  /teams
GET  /teams/{team_abbrev}
GET  /players
GET  /players/{player_id}
GET  /players/search
GET  /schedule
GET  /injuries
GET  /roster/{team_id}
GET  /player/{player_id}
```

### Game Data (`api/game_logs_routes.py`)

```
GET  /api/game-logs
GET  /game-logs
GET  /game-dates
GET  /boxscore/{game_id}
```

### H2H System (`api/h2h_population_routes.py`)

```
POST /api/h2h/populate
GET  /api/h2h/status/{player_id}/{opponent}
GET  /api/h2h/fetch/{player_id}/{opponent}
```

### Injury Admin (`api/injury_admin.py`)

```
POST /admin/injuries/add
POST /admin/injuries/bulk
DEL  /admin/injuries/remove/{player_id}
GET  /admin/injuries/all
GET  /admin/injuries/team/{team_abbr}
```

### Matchup Engine (`api/matchup_endpoint.py`)

```
GET  /matchup/analyze
GET  /matchup/{player_id}/{opponent}
GET  /matchup-lab/games
GET  /matchup-lab/crucible-sim
GET  /analyze/crucible
GET  /analyze/usage-vacuum
GET  /usage-vacuum/analyze
```

### Aegis Sovereign (`aegis/`)

```
GET  /radar/{player_id}
GET  /aegis/matchup
GET  /debug/teams-schema
GET  /settings/gemini-key
GET  /player/{player_id}
```

### Nexus Hub (`api/nexus_routes.py`) — ⚠️ 404 IN PRODUCTION

```
GET  /nexus/health          ← 404 — module import fails in container
GET  /nexus/cooldowns        ← 404
GET  /nexus/cooldowns/{key}  ← 404
DEL  /nexus/cooldowns/{key}  ← 404
```

### Live Stream (`api/live_stream_routes.py`) — ⚠️ IMPORT FAILS

```
GET  /live/stream    ← SSE endpoint — intermittent
GET  /live/leaders   ← Falls back to mock if SSE down
GET  /live/games
GET  /live/status
```

### Vanguard Health (`vanguard/api/health.py`)

```
GET  /vanguard/health          ← ✅ Primary health check
GET  /vanguard/incidents        ← Legacy list (use admin/incidents)
GET  /vanguard/admin/stats      ← ✅ Fixed (alias in health.py, above wildcard)
GET  /vanguard/incidents/{fp}   ← ⚠️ Wildcard — was shadowing admin routes
```

### Vanguard Admin (`vanguard/api/admin_routes.py`)

```
POST /vanguard/admin/mode
GET  /vanguard/admin/incidents
GET  /vanguard/admin/stats         ← Defined here, but shadowed by {fp} wildcard
POST /vanguard/admin/incidents/{fp}/resolve
POST /vanguard/admin/incidents/{fp}/analyze
GET  /vanguard/admin/incidents/{fp}/analysis
POST /vanguard/admin/incidents/analyze-all
POST /vanguard/admin/incidents/resolve-all
POST /vanguard/admin/incidents/bulk-resolve
GET  /vanguard/admin/learning/status
GET  /vanguard/admin/learning/export
GET  /vanguard/admin/archives
POST /vanguard/admin/cron/archive
```

### Vanguard Vaccine (`vanguard/api/vaccine_routes.py`)

```
POST /vanguard/vaccine/inject
GET  /vanguard/vaccine/status
```

### Vanguard Cron (`vanguard/api/cron_routes.py`)

```
POST /cron/vanguard/purge
POST /cron/vanguard/archive
```

---

## 🧠 VANGUARD SUBSYSTEMS

```
Vanguard Autonomous Operator
├── Inquisitor (ENABLED)     — Middleware sampling (5% of requests)
│   └── Catches unhandled errors, creates incident fingerprints
├── Archivist (ENABLED)      — Firestore incident persistence
│   └── Storage cap: 500MB | Retention: 7 days
├── Profiler (ENABLED)       — AI triage via gemini-2.0-flash
│   └── Fires on new incidents when LLM enabled
├── Surgeon (DISABLED)       — Circuit breaker / auto-remediation
│   └── Requires CIRCUIT_BREAKER or FULL_SOVEREIGN mode
└── Vaccine (ENABLED)        — Health gate / proactive blocks
    └── Blocks known-bad patterns from reaching handlers

Operating Modes (in order of autonomy):
  SILENT_OBSERVER  → Records only, no intervention [CURRENT]
  CIRCUIT_BREAKER  → Blocks repeat-offender endpoints
  FULL_SOVEREIGN   → Full auto-remediation + Surgeon active
```

---

## 📡 DATA FLOW DIAGRAMS

### Live Pulse Flow

```
NBA CDN API
    │
    ▼
CloudAsyncPulseProducer (backend)
    │  ← writes every 30s
    ▼
Firestore /pulse/leaders
    │
    ├── SSE /live/stream ──────────► PulsePage (web)
    └── Firestore listener ─────────► Mobile clients
```

### Matchup Analysis Flow

```
User selects Player + Opponent
    │
    ▼
MatchupEnginePage  →  POST /matchup/analyze
    │
    ▼
AegisOrchestrator
    ├── PlayerApi  →  /players/{id}  (vital stats)
    ├── H2H Store  →  /api/h2h/fetch/{id}/{opp}  (historical data)
    └── GeminiAI   →  Narrative summary
    │
    ▼
Response: { score, narrative, recommendation, context }
```

### Vanguard Incident Flow

```
Any API request
    │
    ▼
InquisitorMiddleware (5% sample + all errors)
    │
    ▼
VanguardArchivist  →  Firestore /vanguard/incidents/{fingerprint}
    │
    ├── Profiler  →  Gemini AI analysis (async)
    └── Vaccine   →  Block if recurring pattern
    │
    ▼
VanguardControlRoom UI  →  GET /vanguard/admin/incidents
                         →  GET /vanguard/admin/stats
```

---

## 🔌 API CONTRACT (Frontend Transport)

Transport layer: `src/api/client.ts → ApiContract`

```
ApiContract.execute(ipcMethod, { path, options })
    │
    ├─ If Electron + IPC available → window.electronAPI[ipcMethod]()
    │
    ├─ If Electron + no IPC → Web fallback (with warning logged to Vanguard)
    │
    └─ If Web → fetch(VITE_API_URL + path)
                FALLBACK_BASE = quantsight-cloud-*.run.app
```

All HTTP errors (non-2xx) throw. UI catches errors and shows toasts. No silent null fallbacks.

---

## ⚠️ KNOWN PRODUCTION ISSUES (see DEAD_CODE_AUDIT.md for full list)

| Issue | Impact | Root Cause | Fix Status |
|-------|--------|------------|------------|
| `/vanguard/admin/stats` was 404 | Control Room showed no data | `{fingerprint}` wildcard in `health.py` captured `/admin/stats` | ✅ Fixed in `health.py` |
| `/nexus/*` all 404 | PlayerProfile missing cooldowns | `api/nexus_routes.py` import fails in container | 🔴 Nexus module dead |
| `/live/stream` SSE intermittent | Pulse page silent | `live_stream_routes` import Exception swallowed | 🟡 Graceful fallback |
| NexusApi in frontend | Widget crashed | Called dead nexus endpoints | ✅ Fixed — removed |

---

## 🚀 DEPLOYMENT CHECKLIST

```powershell
# 1. Build + verify TypeScript compiles
npm run build

# 2. Run Vanguard smoke test (exit 0 = all critical endpoints up)
npx tsx scripts/smoke_vanguard.ts

# 3. Deploy backend
gcloud run deploy quantsight-cloud --source . --region us-central1 --allow-unauthenticated --quiet

# 4. Deploy frontend
firebase deploy --only hosting

# 5. Verify production
python scripts/verify_prod.py   # or re-run smoke_vanguard.ts
```

### Key Files

```
backend/main.py            — FastAPI entry point, route registration
backend/Dockerfile          — Copies backend/, runs uvicorn main:app
vanguard/api/health.py     — Vanguard health + admin/stats alias
vanguard/api/admin_routes.py — Full admin CRUD (incidents, resolve, analyze)
src/api/client.ts           — Transport layer (IPC ↔ Web)
src/pages/VanguardControlRoom.tsx — Control Room UI
src/components/vanguard/VanguardHealthWidget.tsx — Settings page widget
DEAD_CODE_AUDIT.md          — Zombie/orphan file tracking
scripts/smoke_vanguard.ts   — Production API health test
```

---

*This document reflects the system state as of 2026-02-26. Update after any major route or page additions.*
