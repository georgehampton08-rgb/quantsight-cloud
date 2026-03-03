# NBA Play-by-Play Pipeline Architecture

Last Updated: 2026-03-03

---

## Overview

QuantSight's Play-by-Play (PBP) pipeline delivers real-time NBA play data from
external sports APIs to the frontend with sub-second latency, using a
**dual-source ingestion**, **Firestore persistence**, and **Server-Sent Events
(SSE)** streaming approach.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Cloud Run (Backend)                  │
│                                                         │
│  ┌─────────────────┐     ┌─────────────────────────┐   │
│  │  ESPN Scoreboard│────▶│   NBAPlayByPlayClient    │   │
│  │  (Primary)      │     │   fetch_espn_plays()     │   │
│  └─────────────────┘     └──────────┬──────────────┘   │
│  ┌─────────────────┐                │ fallback          │
│  │  cdn.nba.com    │────────────────┘                   │
│  │  (Fallback CDN) │     ┌──────────▼──────────────┐   │
│  └─────────────────┘     │   PlayEvent (Pydantic)   │   │
│                          │   Unified Data Model     │   │
│                          └──────────┬──────────────┘   │
│                                     │                   │
│                          ┌──────────▼──────────────┐   │
│                          │  PBPPollingService       │   │
│                          │  asyncio task per game   │   │
│                          │  poll every 10s          │   │
│                          └──────────┬──────────────┘   │
│                    ┌────────────────┼──────────┐        │
│                    ▼                ▼          ▼        │
│         ┌──────────────┐  ┌───────────┐  ┌─────────┐  │
│         │  Firestore   │  │SSE Queues │  │  Cache  │  │
│         │  live_games/ │  │per game_id│  │Snapshot │  │
│         │  {game_id}/  │  └─────┬─────┘  └─────────┘  │
│         │  plays/{id}  │        │                       │
│         └──────────────┘        │                       │
└─────────────────────────────────┼─────────────────────┘
                                  │ SSE text/event-stream
                    ┌─────────────▼──────────────────┐
                    │     React Frontend              │
                    │  useLivePlayByPlay hook         │
                    │  - Hydrates from /plays         │
                    │  - Streams from /stream SSE     │
                    │  - Deduplicates by sequenceNum  │
                    └────────────────────────────────┘
```

---

## Firestore Document Structure

```
live_games/                        (collection)
  {espn_game_id}/                  (document — game metadata)
    plays/                         (subcollection)
      {playId}/                    (document — one per play event)
        playId: string
        sequenceNumber: int        ← sort key, unique per game
        eventType: string
        description: string
        period: int
        clock: string
        homeScore: int
        awayScore: int
        teamId: string | null
        teamTricode: string | null
        primaryPlayerId: string | null
        primaryPlayerName: string | null
        secondaryPlayerId: string | null   ← assist/block/steal player
        secondaryPlayerName: string | null
        involvedPlayers: string[]
        isScoringPlay: bool
        isShootingPlay: bool
        pointsValue: int
        shotDistance: float | null
        shotArea: string | null    ← e.g. "Left Corner 3"
        shotResult: "Made"|"Missed"|null
        coordinateX: float | null  ← NBA court X (0-50 range)
        coordinateY: float | null  ← NBA court Y (0-94 range)
        rawData: {}                ← preserved original payload
        source: "espn" | "nba_cdn"

game_cache/                        (collection)
  {espn_game_id}/                  (document — fast-read snapshot)
    playsCount: int
    lastPolled: ISO timestamp
```

**Key Design Decisions:**

- `playId` is used as the Firestore document ID → guarantees idempotency on re-poll
- `merge=True` on all writes → safe to re-run without duplicating
- `sequenceNumber` is the sort index → consistent chronological order across sources
- `rawData` stored for full backward compatibility and debugging

---

## Dual-Source Strategy

| Source | URL | Priority | Notes |
|--------|-----|----------|-------|
| ESPN Summary API | `site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={id}` | Primary | Full participants, coordinates, scoring flags |
| NBA CDN | `cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{id}.json` | Fallback | Shot area, assist IDs, free throw tracking |

Both sources pipe through their respective `map_*_to_unified()` functions and
produce identical `PlayEvent` Pydantic objects — the frontend never knows which
source provided the data.

**ESPN coordinate validation:** Raw ESPN coordinates can be nonsense values
(`-214748340`) for non-shot plays. The mapper nullifies any coordinate outside
the range `[-100, 200]` on both axes.

---

## API Rate Limits & Backoff

The poller runs every 10 seconds per game. On consecutive ESPN failures:

```
sleep_time = min(10 * (2 ** consecutive_errors), 60)
```

| Errors | Sleep |
|--------|-------|
| 0 | 10s |
| 1 | 20s |
| 2 | 40s |
| 3+ | 60s (cap) |

ESPN public endpoints do not publish rate limits. In practice, 10s polling of
the summary endpoint has not triggered any throttling during testing.

---

## REST + SSE Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/games/live` | List all ESPN games (pre/in/post state) |
| POST | `/v1/games/{id}/start-tracking` | Manually wake the poller for a game |
| GET | `/v1/games/{id}/plays?limit=N` | Hydration: all Firestore-cached plays |
| GET | `/v1/games/{id}/stream` | SSE stream: new plays pushed in real-time |

**SSE Protocol:**

- On connect: `data: {"type":"connection","status":"connected","gameId":"..."}`
- On new plays: `data: {"type":"plays_update","plays":[...]}`
- Every 15s with no plays: `: heartbeat` (SSE comment — keeps load balancer alive)

---

## Frontend Data Flow

1. User selects a game from `LiveGameSelector`
2. `useLivePlayByPlay(gameId)` triggers:
   - REST call to `/plays` → sets initial state from Firestore cache
   - Opens `EventSource` to `/stream`
3. New plays arriving via SSE are merged into state:
   - Deduplication: `Set` of existing `sequenceNumber`s
   - Always re-sorted ascending by `sequenceNumber`
4. `InteractiveShotChart` maps `coordinateX`/`coordinateY` → SVG court positions
5. `PlayItem` renders color-coded rows with player headshots from NBA CDN

---

## Mobile Responsive Layout

The PBP tab uses a **mobile-first** CSS approach:

| Breakpoint | Layout |
|-----------|--------|
| `>1024px` | Side-by-side: court left `(flex:2)`, feed right `(flex:1)` |
| `640–1024px` | Stacked: court on top, feed below (480px fixed height) |
| `<640px` | Compact: reduced padding, smaller fonts, `clamp()` scaling, tooltip moves to bottom of screen |
