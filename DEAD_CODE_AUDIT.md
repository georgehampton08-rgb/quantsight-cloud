# Dead Code Audit Plan

*Created: 2026-02-25 | As-found during Vanguard wiring session*

This is a living document. Items are added as dead/broken code is discovered during active development. Each item is assessed before deletion to avoid breaking a live dependency.

---

## STATUS LEGEND

- 🔴 **DEAD** — Confirmed unused, safe to delete
- 🟡 **ZOMBIE** — Imported somewhere but the endpoint it calls is 404 in production
- 🟠 **ORPHAN** — File exists but is never imported anywhere in the app
- 🟢 **LIVE** — Confirmed in use, do not touch

---

## FRONTEND — `src/`

### Services

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `services/nexusApi.ts` | 🟡 ZOMBIE | Calls `/nexus/overview`, `/nexus/cooldowns` — both 404 in prod. Only imported by `hooks/useNexusHealth.ts` and `VanguardHealthWidget` (now fixed). | Delete after confirming no other consumers |
| `services/aegisApi.ts` | 🟡 ZOMBIE | Calls `/aegis/*` — need to verify if any routes are live | Audit aegis routes first |
| `services/playerApi.ts` | 🟢 LIVE | Used in SettingsPage (purge), PlayerProfilePage | Keep |
| `services/prefetchService.ts` | 🟠 ORPHAN | Not imported anywhere visible | Investigate then delete |

### Hooks

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `hooks/useNexusHealth.ts` | 🔴 DEAD | Uses `NexusApi` which is 🟡. Hook itself not imported in any page. | Delete |
| `hooks/` (others) | TBD | Need full import scan | Audit next session |

### Components

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `components/nexus/NexusHealthPanel.tsx` | 🟠 ORPHAN | Not imported in any page. Uses `useNexusHealth` (dead). | Delete entire `components/nexus/` folder |
| `components/nexus/CooldownIndicator.tsx` | 🟠 ORPHAN | Only imported in `components/nexus/index.ts`. `index.ts` itself not consumed. | Delete |
| `components/nexus/index.ts` | 🟠 ORPHAN | Not imported in any page. | Delete |
| `components/nexus/NexusHealthPanel.css` | 🔴 DEAD | Only used by orphaned `NexusHealthPanel.tsx` | Delete |
| `components/nexus/CooldownIndicator.css` | 🔴 DEAD | Only used by orphaned component | Delete |
| `components/aegis/AegisHealthDashboard.tsx` | 🟠 ORPHAN | Not imported in any page (only referenced internally via `index.ts`) | Audit |
| `components/common/NextDayDriftToast.tsx` | TBD | Need import scan | Audit |
| `components/common/FreshnessHalo.tsx` | TBD | Need import scan | Audit |
| `components/common/GameModeIndicator.tsx` | TBD | Need import scan | Audit |
| `components/ui/` (shadcn stubs) | TBD | `alert.tsx`, `button.tsx`, `card.tsx`, `input.tsx`, `label.tsx`, `select.tsx` — check if any page uses these vs raw HTML | Audit |

### Context

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `context/OrbitalContext.tsx` | TBD | Unclear if consumed | Audit |
| `context/ProgressContext.tsx` | TBD | Unclear if consumed | Audit |
| `context/LiveGameContext.tsx` | TBD | Was part of SSE — check if still wired to live SSE stream or orphaned | Audit |

### Pages

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `pages/PlayerProfilePage.tsx` | 🟡 ZOMBIE | Uses `CooldownIndicator` (orphan) from nexus component | Fix import or remove CooldownIndicator usage |

---

## BACKEND — Python

### Routes

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `api/live_stream_routes.py` | 🟡 ZOMBIE | Imports fail silently in Cloud Run. Root cause was previously suppressed. | Investigate why it fails to import in container |
| `nexus/` module | 🟡 ZOMBIE | `/nexus/*` all return 404 in production. Routes registered but module likely has import error. | Check `nexus/__init__.py` and its deps |
| `app/routers/aegis.py` | TBD | `/aegis/*` — some routes are live (`/aegis/matchup`, `/aegis/simulate`) — others may not be | Verify each route |
| `vanguard/api/surgeon_routes.py` | 🟡 ZOMBIE | SURGEON subsystem is disabled. Routes register but endpoint returns 500. | Either enable surgeon or remove its routes |

### Scripts

| File | Status | Evidence | Action |
|------|--------|----------|--------|
| `scripts/smoke_frontend_contract.ts` | 🟡 ZOMBIE | Hardcoded to `localhost:8000` — useless against cloud. Replaced by `smoke_vanguard.ts`. | Update base URL or delete |

---

## DELETION PLAN (Ordered by Safety)

### Phase A — Zero Risk (confirmed orphans, not imported anywhere)

1. `src/hooks/useNexusHealth.ts`
2. `src/components/nexus/` (entire folder: NexusHealthPanel, CooldownIndicator, index, CSS files)
3. `src/services/prefetchService.ts` (after confirming no imports)

### Phase B — Low Risk (zombie services, just need to clean call sites)

4. `src/services/nexusApi.ts` — already removed from `VanguardHealthWidget`, confirm `PlayerProfilePage` no longer uses it
2. Fix `PlayerProfilePage.tsx` if it references `CooldownIndicator`

### Phase C — Needs Backend Investigation First

6. `nexus/` backend module — needs a Python import test to confirm import failure
2. `api/live_stream_routes.py` — trace the exact import failure
3. `vanguard/api/surgeon_routes.py` — verify if surgeon is intended to be disabled long-term

### Phase D — Context/Page Audit (next session)

9. Full scan of remaining `context/` and `components/common/` files

---

## HOW TO RUN THE NEXT AUDIT

```powershell
# Find all tsx/ts files that import from nexus
grep -r "nexus" src/ --include="*.ts" --include="*.tsx" -l

# Find all components that are never imported in pages
# (manual cross-reference of App.tsx route tree vs component files)

# Check which services are actually called
grep -r "import.*from.*services/" src/pages/ --include="*.tsx"
```

---
*Next session: Execute Phase A deletions, then run `npm run build` to confirm zero broken imports.*
