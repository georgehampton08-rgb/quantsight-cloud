from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
import asyncio
import logging
import json
from datetime import datetime

from services.nba_pbp_service import pbp_client
from services.firebase_pbp_service import firebase_pbp_service
from services.pbp_polling_service import pbp_polling_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/games", tags=["play-by-play"])

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

@router.get("/{game_id}/plays")
async def get_game_plays(game_id: str, limit: int = 1500):
    """
    Initial hydration endpoint. Fetches all cached plays for the requested game
    ordered chronologically.
    """
    try:
        plays = firebase_pbp_service.get_cached_plays(game_id, limit=limit)
        return {"status": "success", "count": len(plays), "plays": plays}
    except Exception as e:
        logger.error(f"Failed to fetch cached plays for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed fetching cached database plays")

async def _sse_pbp_generator(request: Request, game_id: str):
    """
    Async SSE generator yielding new plays and 15-second heartbeats.
    """
    # Force tracker to start if it isn't already
    await pbp_polling_manager.start_tracking(game_id)
    
    q = pbp_polling_manager.subscribe_sse(game_id)
    try:
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected', 'gameId': game_id})}\n\n"
        
        while True:
            if await request.is_disconnected():
                break
            
            try:
                # wait 15 seconds for a new play payload
                payload = await asyncio.wait_for(q.get(), timeout=15.0)
                # payload is a list of json dicts representing newly fetched PlayEvents
                yield f"data: {json.dumps({'type': 'plays_update', 'plays': payload})}\n\n"
            except asyncio.TimeoutError:
                # 15s elapsed with no new plays, emit standard SSE heartbeat comment
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
            "X-Accel-Buffering": "no"
        }
    )
