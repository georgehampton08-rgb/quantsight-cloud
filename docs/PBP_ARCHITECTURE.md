# NBA Play-by-Play Pipeline Architecture

Last Updated: 2026-03-04
Schema Version: v2.0 (6-Collection Hybrid)

---

## Overview

QuantSight's Play-by-Play (PBP) pipeline delivers real-time NBA play data from
external sports APIs to the frontend with sub-second latency, using
**dual-source ingestion**, **Firestore persistence**, and **Server-Sent Events (SSE)**
streaming.

**Key v2.0 improvements:**

- Date-first indexing for calendar view (`calendar/{date}/games/`)
- Crash-recoverable cursor: polling service persists `lastSequenceNumber` to Firestore
- Append-only PBP stream: ordered by zero-padded sequence number doc ID (no `.orderBy()` needed)
- Shot chart extraction as an inline side-effect of PBP writes
- Final freeze: `final_games/{gameId}` snapshot created at game-end

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Cloud Run (Backend)                      │
│                                                             │
│  ┌─────────────────┐     ┌─────────────────────────┐       │
│  │  ESPN Scoreboard│────▶│   NBAPlayByPlayClient    │       │
│  │  (Primary)      │     │   fetch_espn_plays()     │       │
│  └─────────────────┘     └──────────┬──────────────┘       │
│  ┌─────────────────┐                │ fallback              │
│  │  cdn.nba.com    │────────────────┘                       │
│  │  (Fallback CDN) │     ┌──────────▼──────────────┐       │
│  └─────────────────┘     │   PlayEvent (Pydantic)   │       │
│                          │   Unified Data Model     │       │
│                          └──────────┬──────────────┘       │
│                                     │                       │
│                          ┌──────────▼──────────────┐       │
│                          │  PBPPollingService       │       │
│                          │  asyncio task per game   │       │
│                          │  - reads cursor from FS  │       │
│                          │  - throttle: 5s/write    │       │
│                          │  - detects game end      │       │
│                          └──────┬────────────┬──────┘       │
│               ┌─────────────────┼────────────┼───────────┐  │
│               ▼                 ▼            ▼           ▼  │
│  ┌────────────────────┐  ┌──────────┐  ┌────────┐  ┌──────┐│
│  │  FirebasePBPService│  │SSE Queue │  │ Game   │  │Final ││
│  │  save_plays_v2()   │  │per gameId│  │Service │  │ize() ││
│  │  extract_shot_doc()│  └────┬─────┘  └────────┘  └──────┘│
│  └─────────┬──────────┘       │                             │
│            │                  │ SSE text/event-stream       │
└────────────┼──────────────────┼─────────────────────────────┘
             │                  │
             ▼                  ▼
      ┌─────────────┐    ┌────────────────────────┐
      │  Firestore  │    │  React Frontend         │
      │  6 collections│  │  useLivePlayByPlay hook │
      │  (see below)│    │  - Hydrates /plays      │
      └─────────────┘    │  - Streams /stream SSE  │
                         │  - Shot chart /shots    │
                         │  - Calendar /by-date    │
                         └────────────────────────┘
```

---

## Firestore Document Structure (v2.0)

All collection path strings are defined in `services/firestore_collections.py`.
Never use magic strings — always import from that module.

### A) Canonical Game Record — `games/{gameId}`

Complete game metadata. The single source of truth for a game.

```json
{
  "gameId": "0022500789",
  "gameDate": "2026-03-03",
  "season": "2025-26",
  "homeTeam": { "teamId": "1610612747", "tricode": "LAL", "name": "Los Angeles Lakers" },
  "awayTeam": { "teamId": "1610612738", "tricode": "BOS", "name": "Boston Celtics" },
  "status": "Final",
  "startTime": "2026-03-03T19:30:00-05:00",
  "createdAt": "2026-03-03T19:25:00Z",
  "updatedAt": "2026-03-03T22:45:00Z"
}
```

### B) Date Index — `calendar/{YYYY-MM-DD}/games/{gameId}`

Thin pointer used for calendar/date-browsing views. Intentionally lean.

```json
{
  "gameId": "0022500789",
  "status": "Final",
  "homeTeam": "LAL",
  "awayTeam": "BOS",
  "startTime": "2026-03-03T19:30:00-05:00",
  "refPath": "games/0022500789",
  "updatedAt": "2026-03-03T22:45:00Z"
}
```

### C) Live State Cache — `live_games/{gameId}`

Hot doc updated at ≤5s cadence during live games. Stores current scoreboard + cursor.

```json
{
  "status": "In Progress",
  "period": 3,
  "clock": "8:42",
  "homeScore": 78,
  "awayScore": 72,
  "lastSequenceNumber": 287,
  "lastPlayId": "4019284891",
  "ingestHeartbeat": "2026-03-03T21:42:00Z",
  "updatedAt": "2026-03-03T21:42:00Z",
  "trackingEnabled": true,
  "gameDate": "2026-03-03",
  "homeTeam": { "tricode": "LAL" },
  "awayTeam": { "tricode": "BOS" },
  "season": "2025-26"
}
```

### D) Play-by-Play Event Stream — `pbp_events/{gameId}/events/{sequenceNumber}`

**Document ID = zero-padded sequenceNumber** (e.g., `"000042"`).
Firestore sorts doc IDs lexicographically — padding makes that order == chronological order.
Append-only: never update an existing event doc (idempotent via `merge=True`).

```json
{
  "playId": "4019284573",
  "sequenceNumber": 42,
  "eventType": "Three Point Jumper",
  "description": "Curry makes 27-foot three point jumper (Green assists)",
  "period": 2,
  "clock": "5:32",
  "homeScore": 54,
  "awayScore": 48,
  "teamId": "1610612744",
  "teamTricode": "GSW",
  "primaryPlayerId": "201939",
  "primaryPlayerName": "Stephen Curry",
  "secondaryPlayerId": "203110",
  "secondaryPlayerName": "Draymond Green",
  "isScoringPlay": true,
  "isShootingPlay": true,
  "pointsValue": 3,
  "shotDistance": 27.0,
  "shotResult": "Made",
  "coordinateX": 23.5,
  "coordinateY": 8.2,
  "source": "espn"
}
```

### E) Shot Chart Attempts — `shots/{gameId}/attempts/{sequenceNumber}`

Lean shot-only doc, same doc IDs as `pbp_events/`. Created only for `isShootingPlay == True`.

```json
{
  "sequenceNumber": 42,
  "playerId": "201939",
  "playerName": "Stephen Curry",
  "teamId": "1610612744",
  "teamTricode": "GSW",
  "shotType": "Three Point Jumper",
  "distance": 27.0,
  "made": true,
  "period": 2,
  "clock": "5:32",
  "x": 23.5,
  "y": 8.2,
  "pointsValue": 3,
  "ts": "2026-03-03T21:32:00Z"
}
```

### F) Final Game Snapshot — `final_games/{gameId}`

Written once at game end. Pointers to full PBP and shot collections.
Safe to preserve across migrations (`createdAt` preserved, never overwritten).

```json
{
  "gameId": "0022500789",
  "gameDate": "2026-03-03",
  "season": "2025-26",
  "homeTeam": { "tricode": "LAL", "name": "Los Angeles Lakers" },
  "awayTeam": { "tricode": "BOS", "name": "Boston Celtics" },
  "homeScore": 112,
  "awayScore": 108,
  "period": 4,
  "status": "Final",
  "totalPlays": 487,
  "lastSequenceNumber": 487,
  "pbpPath": "pbp_events/0022500789/events",
  "shotsPath": "shots/0022500789/attempts",
  "finalizedAt": "2026-03-03T22:45:00Z",
  "createdAt": "2026-03-03T22:45:00Z"
}
```

---

## REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/games/live` | Live game list from ESPN |
| GET | `/v1/games/by-date/{date}` | **NEW** — Calendar view (YYYY-MM-DD) |
| POST | `/v1/games/{id}/start-tracking` | Trigger PBP poller for a game |
| GET | `/v1/games/{id}/plays` | PBP hydration (v2 path, legacy fallback) |
| GET | `/v1/games/{id}/shots` | **NEW** — Shot chart data |
| GET | `/v1/games/{id}/stream` | SSE real-time play stream |

---

## Key Design Decisions

### 1. Sequence-Number Doc IDs (Zero-Padded)

Using `pad_sequence(seq, width=6)` → `"000042"` as the Firestore document ID gives us:

- Free chronological ordering (Firestore sorts doc IDs lexicographically)
- No `.orderBy()` query needed → cheaper reads
- Idempotency: writing the same play twice just merges, no duplicates

### 2. Shot Chart as PBP Side-Effect

Shot docs in `shots/` are written as part of `save_plays_batch_v2()`. This means:

- No second pass over plays
- Shot chart is always in sync with PBP
- Adding a shot play adds to both `pbp_events/` and `shots/` in the same batch

### 3. Throttled Live State Writes

`live_games/{gameId}` is updated at most once every 5 seconds (`LIVE_STATE_CADENCE_SEC`).
This prevents Firestore write hotspots during busy game periods (fast-break sequences).

### 4. Crash-Recoverable Cursor

`lastSequenceNumber` is persisted to `live_games/{gameId}` on every throttled write.
When Cloud Run cold-starts mid-game, `_read_cursor()` reads it back and resumes without re-ingesting.

### 5. Dual-Write During Transition

`save_plays_batch()` (legacy) now also calls `save_plays_batch_v2()`. This means:

- Old code continues to work unchanged
- New schema gets populated automatically
- After running the migration script, the legacy writes can be disabled

### 6. Non-Destructive Migration

The migration script (`scripts/migrate_firestore_schema.py`) never deletes anything by default.
Run `--cleanup` only after `--verify` confirms counts match.

---

## File Map

| File | Role |
|------|------|
| `services/firestore_collections.py` | **Central constants** — all collection path strings |
| `services/firebase_game_service.py` | Writes to `games/` + `calendar/` |
| `services/firebase_pbp_service.py` | PBP + shot writes, finalization |
| `services/pbp_polling_service.py` | Polling loop with cursor persistence + cadence |
| `api/play_by_play_routes.py` | REST + SSE endpoints |
| `scripts/migrate_firestore_schema.py` | One-time migration script |
| `tests/test_phase0_foundation.py` | Constants + helpers |
| `tests/test_phase1_game_service.py` | Game service + calendar |
| `tests/test_phase2_pbp_refactor.py` | PBP v2 + shots |
| `tests/test_phase3_polling.py` | Cursor + live state |
| `tests/test_phase4_finalization.py` | finalize_game() |
| `tests/test_phase5_routes.py` | API routes + compat |
| `tests/test_phase6_migration.py` | Migration script |
| `tests/test_phase7_integration.py` | End-to-end pipeline |
| `tests/run_all_phases.py` | Full suite runner |
