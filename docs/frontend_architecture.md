# QuantSight Frontend Architecture
>
> Reverse-engineered from deployed bundle: `index-BKviPUhI.js` (878 KB)
> Audited: 2026-02-24 | Firebase Hosting: `quantsight-prod.web.app`
> Backend: `https://quantsight-cloud-458498663186.us-central1.run.app`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React (hooks, functional components) |
| Router | React Router v6 (`HashRouter`) |
| Charts | Recharts |
| Search | Fuse.js (local fuzzy search) |
| Animation | Framer Motion |
| Styling | Tailwind CSS |
| Runtime | Web + Electron (dual-mode via `window.electronAPI` IPC checks) |
| State | React Context (`OrbitalContext` for selected player/team) + `localStorage` |

---

## Routes

| Path | Page | Notes |
|---|---|---|
| `/` | Home / Command Center | Pulse stats, schedule widget |
| `/player` | Player Lab | Search + profile |
| `/player/:id` | Player Profile | Deep stats, play types, hustle |
| `/matchup` | Matchup Engine | Aegis simulation |
| `/pulse` | The Pulse | Live telemetry leaderboard |
| `/game-logs` | Game Logs | Historical browser |
| `/matchup-lab` | Matchup Lab | Advanced analysis |
| `/team` | Team Central | Roster + team stats |
| `/settings` | Settings | API key management |
| `/vanguard` | Vanguard Control Room | System health + incident management |
| `/injury-admin` | Injury Admin | Injury CRUD |

---

## API Surface (all endpoints the frontend calls)

### Public / Core

| Method | Endpoint | Component | Polling |
|---|---|---|---|
| `GET` | `/health` | TopBar LEDs | Every 30s |
| `GET` | `/teams` | CascadingSelector | On page load |
| `GET` | `/schedule` | ScheduleWidget | On page load |
| `GET` | `/roster/${team_id}` | CascadingSelector | On team select |
| `GET` | `/players/search?q=` | OmniSearch (TopBar) | On keypress |
| `GET` | `/settings/keys` | SettingsPage | On page load |

### Player Analytics

| Method | Endpoint | Component |
|---|---|---|
| `GET` | `/players/${id}` | PlayerProfilePage |
| `GET` | `/players/${id}/stats` | PlayerProfilePage |
| `GET` | `/players/${id}/play-types` | PlayerProfilePage |
| `GET` | `/data/player-hustle/${id}` | PlayerProfilePage |
| `POST` | `/player-data/refresh/${id}` | PlayerProfilePage |
| `POST` | `/players/${id}/refresh` | PlayerProfilePage |

### Aegis Engine (Simulation)

| Method | Endpoint | Component |
|---|---|---|
| `GET` | `/aegis/player/${id}/stats` | MatchupEngine |
| `GET` | `/aegis/matchup/player/${id}/vs/${t}` | MatchupEngine |
| `POST` | `/aegis/simulate/${player_id}` | MatchupEngine |
| `GET` | `/aegis/ledger/trace/${id}` | MatchupEngine |
| `GET` | `/aegis/stats` | MatchupEngine |

### Nexus (Routing Intelligence)

| Method | Endpoint | Component |
|---|---|---|
| `GET` | `/nexus/overview` | Vanguard health panels |
| `GET` | `/nexus/health` | Vanguard |
| `GET` | `/nexus/cooldowns` | Vanguard |
| `GET` | `/nexus/route-matrix` | Vanguard |

> ⚠️ **Note:** `NEXUS_ROUTES_AVAILABLE = False` in `main.py` — Nexus routes are disabled backend-side. Frontend calls will 404 silently.

### Vanguard Control Room

| Method | Endpoint | Notes | Polling |
|---|---|---|---|
| `GET` | `/vanguard/health` | Admin health tab | Every 30s |
| `GET` | `/vanguard/admin/incidents?limit=2000` | Full incident list | Every 30s |
| `GET` | `/vanguard/admin/incidents/{fp}/analysis` | AI analysis modal open | On demand |
| `POST` | `/vanguard/admin/incidents/analyze-all` | "Analyze All" button | On click |
| `POST` | `/vanguard/admin/resolve/{fp}` | Single resolve | On click |
| `POST` | `/vanguard/admin/resolve/bulk` | Bulk resolve (sends fingerprint list) | On click |
| `GET` | `/vanguard/admin/learning/status` | Learning tab | Every 30s |

### Admin

| Method | Endpoint | Component |
|---|---|---|
| `POST` | `/admin/injuries/add` | InjuryAdmin |
| `DELETE` | `/admin/injuries/remove/${id}` | InjuryAdmin |

---

## Vanguard Control Room — Detailed

**Tabs:** Health | Incidents | Archives | Learning

### Health Tab

- Overall score (0–100 calculation from active incidents)
- Subsystem status cards: Redis, model sampling rate, retention days
- Polls `/vanguard/health` + `/nexus/health` every 30s

### Incidents Tab

- Fetches `/vanguard/admin/incidents?limit=2000` every 30s (81.92 KB payload!)
- Incident card list with fingerprint, endpoint, severity, count
- Click incident → opens modal calling `GET /vanguard/admin/incidents/{fp}/analysis`
- Modal shows: Confidence %, Root Cause, Impact, Recommended Fix (from AI)
- Modal buttons: **Regenerate** (stub `console.log` in deployed bundle), **Close**, **Mark Resolved**
- Bulk resolve: select multiple → `POST /vanguard/admin/resolve/bulk`

### Learning Tab

- Polls `/vanguard/admin/learning/status` every 30s
- Displays pattern recognition stats

### Key Bug (deployed bundle `index-BKviPUhI.js`)

```js
onRegenerate: E => { console.log("Regenerating analysis for", E) }
// ↑ This is a no-op stub. Never calls the backend.
// Backend endpoint exists: POST /vanguard/admin/incidents/{fp}/analyze
// Fix: replace stub with fetch call
```

---

## Context System

### OrbitalContext

- Persisted to `localStorage` key: `quantsight_context`
- Holds: selected player, selected team, comparison targets
- Available across all pages

### Electron / IPC Dual Mode

```js
if (window.electronAPI) {
  // Use IPC bridge to Python backend
} else {
  // Fallback to fetch() calls
}
```

Components with dual-mode: `OmniSearch`, `ScheduleWidget`, `CascadingSelector`

---

## TopBar Components

| Component | Function |
|---|---|
| `CascadingSelector` | Team → Player context selection. Calls `/teams` then `/roster/${id}` |
| `OmniSearch` | "Search players..." box. Calls `/players/search?q=` then filters with Fuse.js |
| Health LEDs | NBA 🟢/🔴, AI 🟢/🔴, DB 🟢/🔴 — driven by `/health` every 30s |

---

## Health Endpoint Performance Issue

`/health` calls these **on every invocation** (no cache):

1. `GET cdn.nba.com` (timeout 8s) — same CDN the pulse producer hits
2. `GET stats.nba.com` (timeout 5s) — **always blocked on Cloud Run VPC**, always times out
3. `Firestore db.collections()` — lists all collections (network call)

**Result:** `/health` P50 = 5–9 seconds in logs.

**Fix applied (2026-02-24):** 25s TTL in-memory cache on `run_all_checks()` + removed `stats.nba.com` check. Expected P50 after fix: ~5ms on cache hits, ~500ms on miss (CDN + Firestore in parallel).

---

## Key Data Contracts

### `/health` response shape

```json
{
  "status": "healthy | warning | degraded",
  "nba_api": "healthy | warning | critical",
  "gemini": "healthy | warning | critical",
  "database": "healthy | warning | critical",
  "details": { ... },
  "producer": { ... },
  "timestamp": "ISO8601"
}
```

### `/vanguard/health` response shape

```json
{
  "status": "operational | degraded",
  "mode": "...",
  "role": "...",
  "version": "..."
}
```

### `/vanguard/admin/incidents?limit=2000` response shape

```json
[
  {
    "fingerprint": "570d277...",
    "endpoint": "/aegis/simulate/2544",
    "error_type": "HTTPError503",
    "severity": "high",
    "count": 3,
    "created_at": "...",
    "resolved": false
  }
]
```

### `/vanguard/admin/incidents/{fp}/analysis` response shape

```json
{
  "fingerprint": "...",
  "confidence": 0.85,
  "root_cause": "...",
  "impact": "...",
  "recommended_fix": "...",
  "cached": true | false
}
```

---

## Known Issues (as of 2026-02-24)

| Issue | Impact | Status |
|---|---|---|
| Regenerate button is `console.log` stub | Cannot trigger individual AI re-analysis | 🔴 Open (frontend rebuild needed) |
| `/vanguard/admin/incidents?limit=2000` polled every 30s | 81.92 KB every 30s bandwidth waste | 🟡 Monitor |
| `/health` 5–9s latency | TopBar LEDs always show stale/yellow | ✅ Fixed (25s cache) |
| Nexus routes 404 from frontend | Vanguard shows Nexus as "offline" | 🟡 Backend disabled intentionally |
| `stats.nba.com` health check always times out | Adds 5s to `/health` baseline | ✅ Fixed (removed check) |

---

## Frontend Source Location

**Current deployed build:** `quantsight-prod.web.app/assets/index-BKviPUhI.js`
**Local source:** `c:\Users\georg\quantsight_engine\quantsight_cloud_build\src\`
**Note:** The deployed bundle (`BKviPUhI`) was built from a prior source version. Current `src/` contains `VanguardControlRoom.tsx` that was reconstructed — its component structure differs from the bundle's `qce` component pattern. A new build will update the hash.
