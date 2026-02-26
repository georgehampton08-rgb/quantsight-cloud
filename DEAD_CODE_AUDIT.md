# Dead Code Audit — QuantSight Cloud Build

*Created: 2026-02-25 | Updated: 2026-02-26*

This is a living document. Items are added as dead/broken code is discovered during active development.

---

## STATUS LEGEND

- 🔴 **DEAD** — Confirmed unused, safe to delete
- 🟡 **ZOMBIE** — Imported somewhere but the endpoint it calls is 404 in production
- 🟠 **ORPHAN** — File exists but is never imported anywhere in the app
- 🟢 **LIVE** — Confirmed in use, do not touch
- ✅ **PURGED** — Deleted in a prior session, confirmed clean build

---

## FRONTEND — `src/`

### Services

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `services/nexusApi.ts` | ✅ PURGED | Zero consumers — deleted 2026-02-26 | Done |
| `services/aegisApi.ts` | ✅ PURGED | Zero consumers after call-site migration — deleted 2026-02-26 | Done |
| `services/playerApi.ts` | 🟢 LIVE | Used in SettingsPage (purge), PlayerProfilePage | Keep |
| `services/prefetchService.ts` | ✅ PURGED | Not found on disk — already removed | Done |

### Hooks

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `hooks/useNexusHealth.ts` | ✅ PURGED | Not found on disk — already removed | Done |
| `hooks/useSimulation.ts` | 🟢 LIVE | Migrated from AegisApi → direct fetch. Used in PlayerProfilePage | Keep |
| `hooks/` (others) | 🟢 LIVE | `useDataFreshness`, `useLiveStats`, `useServerSentEvents`, `useCrucibleSimulation`, `useUsageVacuum` — all importable and used | Keep |

### Components

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `components/nexus/` (entire folder) | ✅ PURGED | Already absent from disk — confirmed 2026-02-26 | Done |
| `components/aegis/AegisHealthDashboard.tsx` | ✅ PURGED | Zero page imports — deleted 2026-02-26 | Done |
| `components/aegis/ProjectionMatrix.tsx` | 🟢 LIVE | Migrated: inlined types, replaced `GameModeIndicator` with inline spans | Keep |
| `components/aegis/VertexMatchupCard.tsx` | 🟢 LIVE | Migrated: inlined types, uses direct fetch via ApiContract | Keep |
| `components/aegis/MatchupWarRoom.tsx` | TBD | Need import scan | Audit next |
| `components/common/NextDayDriftToast.tsx` | TBD | Exists on disk — not found in any page import scan | Investigate |
| `components/common/FreshnessHalo.tsx` | TBD | Exists on disk — not found in any page import scan | Investigate |
| `components/common/GameModeIndicator.tsx` | 🔴 DEAD | Replaced inline in ProjectionMatrix. Zero other consumers. | Safe to delete |
| `components/ui/` (shadcn stubs) | TBD | `alert.tsx`, etc. — check if any page uses these vs raw HTML | Audit next |

### Context

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `context/OrbitalContext.tsx` | 🟢 LIVE | Used in PlayerProfilePage, MatchupEnginePage — cleaned duplicate NBATeam interface | Keep |
| `context/ProgressContext.tsx` | TBD | Not found in any page import scan | Investigate |
| `context/LiveGameContext.tsx` | TBD | Was part of SSE — still needs wiring audit | Audit next |
| `context/HealthContext.tsx` | 🟢 LIVE | Used in Vanguard flow | Keep |
| `context/ToastContext.tsx` | 🟢 LIVE | Used widely | Keep |

### Pages

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `pages/PlayerProfilePage.tsx` | 🟢 LIVE | Migrated away from dead CooldownIndicator + AegisApi. Fully live. | Keep |
| `pages/MatchupEnginePage.tsx` | 🟢 LIVE | Migrated away from AegisApi. Fully live. | Keep |

---

## BACKEND — Python

### Routes

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `api/live_stream_routes.py` | 🟡 ZOMBIE | Imports fail silently in Cloud Run. SSE wiring under review. | Investigate |
| `nexus/` module | 🟡 ZOMBIE | `/nexus/*` all return 404 in production. Routes likely import-failing. | Investigate |
| `app/routers/aegis.py` | 🟢 LIVE (partial) | `/aegis/matchup`, `/aegis/simulate`, `/aegis/radar` all active | Keep |
| `vanguard/api/surgeon_routes.py` | 🟡 ZOMBIE | SURGEON subsystem disabled. Routes register but endpoint returns 500. | Investigate next |

### Scripts

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `scripts/smoke_frontend_contract.ts` | 🟡 ZOMBIE | Hardcoded to `localhost:8000` — useless against cloud | Delete or update |

---

## DELETION PLAN — Updated Status

### Phase A — ✅ COMPLETE (confirmed by clean build 2026-02-26)

1. ~~`src/hooks/useNexusHealth.ts`~~ — already gone
2. ~~`src/components/nexus/`~~ — already gone
3. ~~`src/services/prefetchService.ts`~~ — already gone

### Phase B — ✅ COMPLETE (deleted 2026-02-26, clean build confirmed)

4. ~~`src/services/nexusApi.ts`~~ — deleted, zero consumers
2. ~~`src/services/aegisApi.ts`~~ — deleted, call sites migrated to direct fetch
3. ~~`src/components/aegis/AegisHealthDashboard.tsx`~~ — deleted, orphan
4. CooldownIndicator JSX removed from PlayerProfilePage

### Phase C — Next Session (Backend audit)

- `nexus/` backend module — Python import test needed
- `api/live_stream_routes.py` — trace the exact import failure
- `vanguard/api/surgeon_routes.py` — verify if surgeon is intended to be disabled long-term

### Phase D — Frontend orphan cleanup

- `components/common/GameModeIndicator.tsx` — zero consumers, safe to delete
- `components/common/NextDayDriftToast.tsx` / `FreshnessHalo.tsx` — verify then delete
- `context/ProgressContext.tsx` / `LiveGameContext.tsx` — verify then delete

---

## HOW TO RUN THE NEXT AUDIT

```powershell
# Find all tsx/ts files that reference the common orphan components
rg "GameModeIndicator|NextDayDriftToast|FreshnessHalo|ProgressContext|LiveGameContext" `
  .\src\ --include="*.ts" --include="*.tsx" -l
```

---

*Phases A and B complete — clean build verified 2026-02-26. Phases C and D are next session.*
