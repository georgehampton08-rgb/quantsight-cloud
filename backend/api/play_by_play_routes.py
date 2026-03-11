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




# ── Date-based calendar browsing ─────────────────────────────────────────────

def _build_nba_to_espn_map(db, date: str) -> dict:
    """Build NBA_ID → ESPN_ID lookup from game_id_map for a given date."""
    try:
        docs = list(db.collection("game_id_map").where("date", "==", date).stream())
        result = {}
        for d in docs:
            data = d.to_dict()
            nba = data.get("nba_id", "")
            espn = data.get("espn_id", "")
            if nba and espn:
                result[nba] = espn
        return result
    except Exception:
        return {}


def _enrich_with_scores(db, date: str, nba_game_id: str, game: dict) -> dict:
    """Add scoreHome/scoreAway from pulse_stats FINAL quarter (best effort)."""
    try:
        final_q = (
            db.collection("pulse_stats")
            .document(date)
            .collection("games")
            .document(nba_game_id)
            .collection("quarters")
            .document("FINAL")
            .get()
        )
        if final_q.exists:
            qd = final_q.to_dict()
            game.setdefault("scoreHome", qd.get("home_score", 0))
            game.setdefault("scoreAway", qd.get("away_score", 0))
    except Exception:
        pass
    return game


@router.get("/by-date/{date}")
async def get_games_by_date(date: str):
    """
    List all games on a given date (YYYY-MM-DD format).
    Multi-source: calendar → pulse_stats → schedule (for today).

    Each game includes:
      - gameId: ESPN ID when available (plays stored under ESPN ID), else NBA ID
      - nbaId: original NBA ID preserved for reference
      - homeTeam, awayTeam, status
      - hasPbp (bool): True if ESPN tracking data exists for this game
      - scoreHome, scoreAway: final scores from pulse_stats FINAL quarter
    """
    try:
        from services.firebase_game_service import FirebaseGameService
        from firestore_db import get_firestore_db
        db = get_firestore_db()

        raw_games = FirebaseGameService.get_games_for_date(date)
        games = []

        if raw_games:
            nba_to_espn = _build_nba_to_espn_map(db, date)
            for g in raw_games:
                nba_id = g.get("gameId", "")
                espn_id = nba_to_espn.get(nba_id, "")
                g["hasPbp"] = bool(espn_id)
                if espn_id:
                    g["gameId"] = espn_id
                    g["nbaId"] = nba_id
                g = _enrich_with_scores(db, date, nba_id, g)
                games.append(g)
            return {"status": "success", "date": date, "count": len(games), "games": games}

        # Source 2: pulse_stats/{date}/games/
        nba_to_espn = _build_nba_to_espn_map(db, date)
        try:
            pulse_docs = list(db.collection("pulse_stats").document(date).collection("games").stream())
            for doc in pulse_docs:
                d = doc.to_dict()
                nba_id = doc.id
                espn_id = nba_to_espn.get(nba_id, "")
                game = {
                    "gameId": espn_id if espn_id else nba_id,
                    "nbaId": nba_id,
                    "homeTeam": d.get("home_team", ""),
                    "awayTeam": d.get("away_team", ""),
                    "status": "Final",
                    "hasPbp": bool(espn_id),
                }
                game = _enrich_with_scores(db, date, nba_id, game)
                games.append(game)
        except Exception as e:
            logger.debug(f"[by-date] pulse_stats fallback: {e}")

        if games:
            return {"status": "success", "date": date, "count": len(games), "games": games}

        # Source 3: Today's schedule
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if date == today:
            try:
                from services.schedule_service import get_schedule_service
                svc = get_schedule_service()
                sched = await svc.get_schedule()
                if sched and sched.get("games"):
                    for g in sched["games"]:
                        gid = g.get("game_id") or g.get("gameId", "")
                        home = g.get("home") or (g.get("home_team", {}).get("tricode") if isinstance(g.get("home_team"), dict) else g.get("home_team", ""))
                        away = g.get("away") or (g.get("away_team", {}).get("tricode") if isinstance(g.get("away_team"), dict) else g.get("away_team", ""))
                        status = g.get("status", "UPCOMING")
                        games.append({
                            "gameId": gid,
                            "homeTeam": home,
                            "awayTeam": away,
                            "status": status if isinstance(status, str) else "UPCOMING",
                            "hasPbp": False,
                        })
            except Exception as e:
                logger.debug(f"[by-date] schedule fallback: {e}")

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


# ── NEW: backfill player shots from historical game ────────────────────────────

@router.post("/{game_id}/backfill-player-shots")
async def backfill_player_shots(game_id: str):
    """
    Retro-populate player_shots/ from an already-stored game's shots/ docs.

    Safe to call multiple times (all Firestore writes use merge=True).
    Use this to backfill any games that were tracked before the per-player
    shot chart feature was added.

    Example: POST /v1/games/0022500789/backfill-player-shots
    """
    try:
        from firestore_db import get_firestore_db
        from services.firestore_collections import (
            SHOTS, SHOTS_ATTEMPTS_SUB, PLAYER_SHOTS, PLAYER_SHOTS_SUB, GAMES
        )
        db = get_firestore_db()

        # Get team metadata from games/ collection (best-effort)
        game_doc = db.collection(GAMES).document(str(game_id)).get()
        game_meta = game_doc.to_dict() if game_doc.exists else {}
        game_date = game_meta.get("gameDate", "")
        home_t = game_meta.get("homeTeam", {})
        away_t = game_meta.get("awayTeam", {})
        home_tricode = home_t.get("tricode", "") if isinstance(home_t, dict) else ""
        away_tricode = away_t.get("tricode", "") if isinstance(away_t, dict) else ""
        matchup = f"{away_tricode} @ {home_tricode}" if home_tricode and away_tricode else ""

        # Read existing shot docs for this game
        shots_col = (
            db.collection(SHOTS)
            .document(str(game_id))
            .collection(SHOTS_ATTEMPTS_SUB)
        )
        shot_docs = list(shots_col.stream())

        written = 0
        BATCH_SIZE = 450
        for i in range(0, len(shot_docs), BATCH_SIZE):
            chunk = shot_docs[i: i + BATCH_SIZE]
            batch = db.batch()
            for doc in chunk:
                data = doc.to_dict()
                data.setdefault("gameId", game_id)
                data.setdefault("gameDate", game_date)
                data.setdefault("matchup", matchup)
                player_id = data.get("playerId")
                if not player_id:
                    continue
                seq = data.get("sequenceNumber", 0)
                player_doc_id = f"{game_id}_{str(seq).zfill(6)}"
                ref = (
                    db.collection(PLAYER_SHOTS)
                    .document(str(player_id))
                    .collection(PLAYER_SHOTS_SUB)
                    .document(player_doc_id)
                )
                batch.set(ref, data, merge=True)
                written += 1
            batch.commit()

        logger.info(f"[Backfill] Wrote {written} player shot docs for game {game_id}")
        return {
            "status": "success",
            "gameId": game_id,
            "playerShotsWritten": written,
            "message": f"Backfilled {written} player shot docs from game {game_id}"
        }
    except Exception as e:
        logger.error(f"Backfill player shots failed for {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Backfill failed")


# ── NEW: per-player cross-game shot chart ─────────────────────────────────────

@router.get("/players/{player_id}/shots")
async def get_player_shots(
    player_id: str,
    date_from: str = None,
    date_to: str = None,
    limit: int = 2000,
):
    """
    Cross-game shot chart for a specific player.

    Reads player_shots/{player_id}/shots/ — populated in real-time as
    plays are tracked and retroactively via the backfill endpoint.

    Query params:
        date_from  YYYY-MM-DD inclusive lower bound (optional)
        date_to    YYYY-MM-DD inclusive upper bound (optional)
        limit      Max docs to return (default 2000)

    Example: GET /v1/games/players/1629029/shots?date_from=2026-01-01
    """
    try:
        shots = FirebasePBPService.get_player_shots(player_id, date_from, date_to, limit)
        return {
            "status": "success",
            "playerId": player_id,
            "count": len(shots),
            "shots": shots,
        }
    except Exception as e:
        logger.error(f"Failed to fetch player shots for {player_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed fetching player shot data")


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
                # Check for termination sentinel from the polling service.
                # Sending a game_ended event allows the client to close the
                # EventSource cleanly instead of auto-reconnecting into a
                # heartbeat loop (which would exhaust Cloud Run concurrency).
                if (
                    isinstance(payload, list)
                    and len(payload) == 1
                    and isinstance(payload[0], dict)
                    and payload[0].get("type") == "system_game_ended"
                ):
                    yield f"data: {json.dumps({'type': 'game_ended', 'gameId': game_id})}\n\n"
                    break
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
