# NBA Play-by-Play Pipeline Architecture

*Revision: 2026-03-03*

## Overview

The QuantSight Play-by-Play (PBP) Pipeline is a robust, near real-time data ingestion and streaming service. It captures granular event-level actions from live NBA games, standardizes them into a unified schema, persists them idempotently in Firestore, and streams them downstream to frontend clients via Server-Sent Events (SSE).

## Core Strategy

1. **Primary Source (ESPN)**
   - Selected for high reliability, fast update cadence, and resistance to Cloud IP blocking.
   - Provides rich participant details, clock values, scoring, and standardized event descriptions.

2. **Fallback Source (NBA Live CDN)**
   - `cdn.nba.com` provides true play-by-play payloads and escapes the rigorous Datacenter IPS checks imposed on `stats.nba.com`.
   - Used defensively if ESPN API encounters a prolonged outage.

3. **Unified Schema (`PlayEvent`)**
   - Both sources are mapped identically to a strict `PlayEvent` Pydantic model.
   - Protects the frontend from upstream data source changes.

## Backend Infrastructure (FastAPI)

1. **`nba_pbp_service.py`**
   - **`NBAPlayByPlayClient`**: HTTP API Client logic parsing raw feeds.
   - **Data Mappers**: `map_espn_to_unified()` & `map_nba_cdn_to_unified()`.

2. **`pbp_polling_service.py`**
   - The heart of the async engine.
   - Maintains an `asyncio.Task` loop per active game to poll the PBP APIs.
   - Implements exponential backoff on HTTP/JSON errors.
   - Acts as an in-memory Pub/Sub broker pushing JSON payloads directly to active SSE connections.

3. **`firebase_pbp_service.py`**
   - **Idempotent Writes**: Uses `sequenceNumber` (from ESPN) or `actionNumber` (from CDN) directly as the Firestore Document ID using `merge=True`.
   - Protects against duplicate inserts naturally via NoSQL architecture.

## Frontend Infrastructure (React/Vite)

1. **`useLivePlayByPlay.ts` (Custom Hook)**
   - Orchestrates the full connection lifecycle.
   - Fetches the initial monolithic historical block via standard REST.
   - Immediately attaches an `EventSource` web-socket-like stream binding to `GET /v1/games/{id}/stream`.
   - Deduplicates incoming SSE events via `sequenceNumber`.

2. **`InteractiveShotChart.tsx`**
   - An interactive visual mapping leveraging `coordinateX` and `coordinateY` spatial telemetry to plot shots physically dynamically as they happen.

## Deployment Notes

- Backend routes are registered securely in `main.py` under `/v1/games`.
- Firestore Rules exclusively limit client writes to the `/live_games` ecosystem, delegating all mutation trust to the backend via the Admin SDK.
