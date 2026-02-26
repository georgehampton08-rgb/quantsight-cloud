"""
Live Stream Routes — Phase 5 Step 5.4.0
=========================================
SSE and REST endpoints for the live pulse system.
Bridges the CloudAsyncPulseProducer in-memory snapshot to frontend clients.

Endpoints:
  GET /live/stream   — SSE endpoint (EventSource) pushing LivePulseData every 1s
  GET /live/leaders  — REST snapshot of top 10 players by PIE
  GET /live/games    — REST snapshot of current live game data
  GET /live/status   — Health check for the live pulse system

Frontend contract:
  - useLiveStats.ts connects to /live/stream via EventSource
  - Expects: { games, meta, changes } shape (LivePulseData)
  - Auto-reconnect on disconnect
  - /live/games returns same data as /live/stream but as a single REST snapshot

Registration:
  main.py imports this as `from api.live_stream_routes import router as live_stream_router`
  Registered with NO prefix — frontend hardcodes /live/stream
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Live Pulse"])


def _get_producer():
    """Lazy import to avoid circular imports during module registration."""
    try:
        from services.async_pulse_producer_cloud import get_cloud_producer
        return get_cloud_producer()
    except ImportError:
        logger.error("CloudAsyncPulseProducer not importable")
        return None


# ── SSE Stream (/live/stream) ────────────────────────────────────────────────

async def _sse_event_generator():
    """
    Generates SSE events from the producer's in-memory snapshot.
    Yields every 1s, only when data is available.
    Sends heartbeat comments every 15s to keep the connection alive.
    """
    heartbeat_counter = 0
    last_timestamp = None

    while True:
        try:
            producer = _get_producer()

            if producer is None:
                # Producer not running — send a degraded status event
                degraded = {
                    "games": [],
                    "meta": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "game_count": 0,
                        "live_count": 0,
                        "update_cycle": 0,
                    },
                    "changes": {},
                }
                yield f"data: {json.dumps(degraded)}\n\n"
                await asyncio.sleep(5)  # slower poll when degraded
                continue

            snapshot = producer.get_latest_snapshot()

            if snapshot is not None:
                current_ts = snapshot.get("meta", {}).get("timestamp")

                # Only push if data has changed since last push
                if current_ts != last_timestamp:
                    yield f"data: {json.dumps(snapshot)}\n\n"
                    last_timestamp = current_ts
                    heartbeat_counter = 0

            # Heartbeat every 15s to prevent proxy/LB timeout
            heartbeat_counter += 1
            if heartbeat_counter >= 15:
                yield ": heartbeat\n\n"
                heartbeat_counter = 0

            await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("SSE stream cancelled (client disconnect)")
            break
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(5)


@router.get("/live/stream")
async def live_stats_stream():
    """
    SSE endpoint for real-time live game stats.
    All clients stream from shared CloudAsyncPulseProducer snapshot.

    Updates pushed every 1s (checks for changes).
    Data includes:
    - All live games with scores and clock
    - Top 10 players by in-game PIE
    - Stat changes for gold pulse animation
    """
    return StreamingResponse(
        _sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ── REST Endpoints ───────────────────────────────────────────────────────────

@router.get("/live/leaders")
async def get_live_leaders_endpoint():
    """
    Get top live players from the producer by PIE.
    Used for Alpha Leaderboard component.
    """
    producer = _get_producer()

    if producer is None:
        return JSONResponse(
            status_code=503,
            content={
                "leaders": [],
                "error": "Producer not running",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    snapshot = producer.get_latest_snapshot()

    if snapshot is None:
        return {
            "leaders": [],
            "message": "No live data available — waiting for first update cycle",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "leaders": snapshot.get("leaders", []),
        "timestamp": snapshot.get("meta", {}).get("timestamp"),
    }


@router.get("/live/games")
async def get_live_games():
    """
    REST endpoint for current live game data.
    Returns the same data as /live/stream but as a single snapshot.
    """
    producer = _get_producer()

    if producer is None:
        return JSONResponse(
            status_code=503,
            content={
                "games": [],
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "game_count": 0,
                    "live_count": 0,
                    "update_cycle": 0,
                },
                "error": "Producer not running",
            },
        )

    snapshot = producer.get_latest_snapshot()

    if snapshot is None:
        return {
            "games": [],
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "game_count": 0,
                "live_count": 0,
                "update_cycle": 0,
            },
            "changes": {},
        }

    return snapshot


@router.get("/live/status")
async def get_live_status():
    """
    Health check for the live pulse system.
    Shows producer status, update count, and snapshot availability.
    """
    producer = _get_producer()

    if producer is None:
        return {
            "status": "offline",
            "producer_running": False,
            "message": "CloudAsyncPulseProducer not initialized",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    producer_status = producer.get_status()

    return {
        "status": "operational" if producer_status.get("running") else "stopped",
        "producer_running": producer_status.get("running", False),
        "version": producer_status.get("version"),
        "update_count": producer_status.get("update_count", 0),
        "firebase_enabled": producer_status.get("firebase_enabled", False),
        "snapshot_available": producer_status.get("snapshot_available", False),
        "last_update_duration_seconds": producer_status.get("last_update_duration_seconds", 0),
        "poll_interval_seconds": producer_status.get("poll_interval_seconds", 10),
        "firebase_write_errors": producer_status.get("firebase_write_errors", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
