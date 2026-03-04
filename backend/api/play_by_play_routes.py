"""
Play-by-Play API Routes — Refactored (Phase 5)
===============================================
Changes from original:
  - GET /{game_id}/plays  → reads from pbp_events/ first, legacy fallback
  - GET /{game_id}/shots  → NEW: shot chart data from shots/{gameId}/attempts/
  - GET /by-date/{date}   → NEW: calendar browsing from calendar/{date}/games/
  - GET /live             → unchanged
  - POST /{game_id}/start-tracking → unchanged
  - GET /{game_id}/stream → unchanged (SSE from in-memory queue)
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
import asyncio
import logging
import json
from datetime import datetime

from services.nba_pbp_service import pbp_client
from services.firebase_pbp_service import firebase_pbp_service, FirebasePBPService
from services.pbp_polling_service import pbp_polling_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/games", tags=["play-by-play"])


# ── Existing: live game list ──────────────────────────────────────────────────

@router.get("/live")
async def get_live_games():
    """
    Returns a list of currently active or recently finished live games
    from ESPN to populate the game selector.
    """
    try:
        games = pbp_client.fetch_live_game_ids()
        tracked = pbp_polling_manager.get_tracked_games()
        for g in games:
            g["is_tracked"] = g["game_id"] in tracked
        return {"status": "success", "games": games}
    except Exception as e:
        logger.error(f"Error fetching live games: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch live schedule")


# ── NEW: date-based calendar browsing ────────────────────────────────────────

@router.get("/by-date/{date}")
async def get_games_by_date(date: str):
    """
    List all games on a given date (YYYY-MM-DD format).
    Reads from calendar/{date}/games/ — the thin date index.

    Example: GET /v1/games/by-date/2026-03-03
    """
    try:
        from services.firebase_game_service import FirebaseGameService
        games = FirebaseGameService.get_games_for_date(date)
        return {"status": "success", "date": date, "count": len(games), "games": games}
    except Exception as e:
        logger.error(f"Error fetching games for date {date}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch games for {date}")


# ── Existing: start tracking ──────────────────────────────────────────────────

@router.post("/{game_id}/start-tracking")
async def start_tracking_game(game_id: str):
    """
    Triggers the backend poller to start actively fetching and broadcasting
    this game. Usually called automatically or by an admin.
    """
    try:
        await pbp_polling_manager.start_tracking(game_id)
        return {"status": "success", "message": f"Tracking initiated for {game_id}"}
    except Exception as e:
        logger.error(f"Failed to start tracking {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not start tracking")


# ── Updated: PBP plays (new path with legacy fallback) ────────────────────────

@router.get("/{game_id}/plays")
async def get_game_plays(game_id: str, limit: int = 1500):
    """
    Initial hydration endpoint. Fetches all cached plays for the game ordered
    chronologically.

    Priority:
      1. pbp_events/{game_id}/events/ (new schema, ordered by padded seq doc ID)
      2. live_games/{game_id}/plays/  (legacy fallback during transition)

    The fallback ensures the frontend keeps working for any games that were
    tracked and stored before the schema migration ran.
    """
    try:
        # v2: reads from pbp_events/, falls back to legacy automatically
        plays = FirebasePBPService.get_cached_plays_v2(game_id, limit=limit)
        return {"status": "success", "count": len(plays), "plays": plays}
    except Exception as e:
        logger.error(f"Failed to fetch cached plays for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed fetching cached database plays")


# ── NEW: shot chart data ──────────────────────────────────────────────────────

@router.get("/{game_id}/shots")
async def get_game_shots(game_id: str):
    """
    Shot chart data for a game — lean docs from shots/{gameId}/attempts/,
    optimized for visualization.

    Returns only shot-relevant fields:
        sequenceNumber, playerId, playerName, teamId, teamTricode,
        shotType, distance, made, period, clock, x, y, pointsValue, ts

    Example: GET /v1/games/0022500789/shots
    """
    try:
        shots = FirebasePBPService.get_shot_chart(game_id)
        return {"status": "success", "gameId": game_id, "count": len(shots), "shots": shots}
    except Exception as e:
        logger.error(f"Failed to fetch shot chart for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed fetching shot chart data")


# ── Unchanged: SSE stream ─────────────────────────────────────────────────────

async def _sse_pbp_generator(request: Request, game_id: str):
    """
    Async SSE generator yielding new plays and 15-second heartbeats.
    Data comes from the in-memory SSE queue — Firestore is not read here.
    """
    await pbp_polling_manager.start_tracking(game_id)
    q = pbp_polling_manager.subscribe_sse(game_id)
    try:
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected', 'gameId': game_id})}\n\n"

        while True:
            if await request.is_disconnected():
                break

            try:
                payload = await asyncio.wait_for(q.get(), timeout=15.0)
                yield f"data: {json.dumps({'type': 'plays_update', 'plays': payload})}\n\n"
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": heartbeat\n\n"

    except asyncio.CancelledError:
        logger.info(f"SSE cancelled by client for game {game_id}")
    except Exception as e:
        logger.error(f"SSE error for {game_id}: {e}")
    finally:
        pbp_polling_manager.unsubscribe_sse(game_id, q)
        logger.info(f"SSE client detached from {game_id}")


@router.get("/{game_id}/stream")
async def stream_live_plays(request: Request, game_id: str):
    """
    Server-Sent Events endpoint pushing real-time play-by-play events.
    Returns `text/event-stream`.
    """
    return StreamingResponse(
        _sse_pbp_generator(request, game_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
