"""
Data API Routes — Cloud-Native endpoints for missing frontend calls
====================================================================
These endpoints are called by frontend components (EnrichedPlayerCard,
PulsePage) and the test suites.  They were present in the legacy desktop
server.py but never migrated to the Cloud Run modular routers.

The desktop version used SQLite-backed TrackingDataFetcher.
This cloud version calls the NBA API directly and caches in Firestore.
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])

CURRENT_SEASON = "2024-25"


# ── Firestore cache helper ──────────────────────────────────────────────────

def _firestore_cache_get(collection: str, doc_id: str, max_age_hours: int = 24):
    """Read from Firestore cache. Returns None if missing or stale."""
    try:
        from firestore_db import get_firestore_db
        db = get_firestore_db()
        doc = db.collection(collection).document(str(doc_id)).get()
        if doc.exists:
            data = doc.to_dict()
            cached_at = data.get("_cached_at")
            if cached_at:
                # Firestore stores as datetime, string, or timestamp
                if isinstance(cached_at, str):
                    cached_at = datetime.fromisoformat(cached_at)
                age = datetime.utcnow() - cached_at
                if age < timedelta(hours=max_age_hours):
                    return data
        return None
    except Exception as e:
        logger.debug(f"[CACHE] Firestore read failed for {collection}/{doc_id}: {e}")
        return None


def _firestore_cache_set(collection: str, doc_id: str, data: dict):
    """Write to Firestore cache."""
    try:
        from firestore_db import get_firestore_db
        db = get_firestore_db()
        data["_cached_at"] = datetime.utcnow().isoformat()
        db.collection(collection).document(str(doc_id)).set(data, merge=True)
    except Exception as e:
        logger.warning(f"[CACHE] Firestore write failed for {collection}/{doc_id}: {e}")


# ─── Player Hustle Stats ────────────────────────────────────────────────────

@router.get("/data/player-hustle/{player_id}")
async def get_player_hustle(player_id: str):
    """
    Get hustle stats for a player from NBA API with Firestore caching.
    Real implementation — calls LeagueHustleStatsPlayer and filters.
    """
    # 1) Check Firestore cache first
    cached = _firestore_cache_get("player_hustle", player_id)
    if cached:
        cached.pop("_cached_at", None)
        cached["data_available"] = True
        cached["source"] = "cache"
        return cached

    # 2) Fetch from NBA API
    try:
        from nba_api.stats.endpoints import leaguehustlestatsplayer
        time.sleep(0.6)  # rate limit
        hustle = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season=CURRENT_SEASON,
            season_type_all_star="Regular Season",
            per_mode_time="PerGame",
            timeout=15,
        )
        df = hustle.get_data_frames()[0]

        # Filter to the requested player
        player_row = df[df["PLAYER_ID"].astype(str) == str(player_id)]
        if player_row.empty:
            return {
                "player_id": player_id,
                "data_available": False,
                "message": f"No hustle stats found for player {player_id} in {CURRENT_SEASON}",
            }

        row = player_row.iloc[0]
        result = {
            "player_id": str(row["PLAYER_ID"]),
            "player_name": row.get("PLAYER_NAME", ""),
            "team": row.get("TEAM_ABBREVIATION", ""),
            "contested_shots": float(row.get("CONTESTED_SHOTS", 0)),
            "contested_shots_2pt": float(row.get("CONTESTED_SHOTS_2PT", 0)),
            "contested_shots_3pt": float(row.get("CONTESTED_SHOTS_3PT", 0)),
            "deflections": float(row.get("DEFLECTIONS", 0)),
            "charges_drawn": float(row.get("CHARGES_DRAWN", 0)),
            "screen_assists": float(row.get("SCREEN_ASSISTS", 0)),
            "loose_balls_recovered": float(row.get("LOOSE_BALLS_RECOVERED", 0)),
            "off_boxouts": float(row.get("OFF_BOXOUTS", 0)),
            "def_boxouts": float(row.get("DEF_BOXOUTS", 0)),
            "data_available": True,
            "source": "nba_api",
        }

        # 3) Cache in Firestore for 24h
        _firestore_cache_set("player_hustle", player_id, result)

        return result

    except ImportError:
        logger.error("[HUSTLE] nba_api not installed")
        raise HTTPException(status_code=503, detail="NBA API dependency not available")
    except Exception as e:
        logger.error(f"[HUSTLE] NBA API fetch failed for {player_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch hustle stats from NBA API: {str(e)}"
        )


# ─── Box Scores (alternate path) ────────────────────────────────────────────

@router.get("/api/box-scores/game/{game_id}")
async def get_boxscore_alias(game_id: str):
    """
    Alias for /boxscore/{game_id} — some frontend components use
    the /api/box-scores/game/ prefix.
    Delegates to the canonical boxscore handler in public_routes.
    """
    try:
        from api.public_routes import get_boxscore
        return await get_boxscore(game_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BOXSCORE ALIAS] Failed for {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Player Play Types ──────────────────────────────────────────────────────

@router.get("/players/{player_id}/play-types")
async def get_player_play_types(player_id: str):
    """
    Get play-type breakdown for a player.
    Calls NBA API SynergyPlayTypes and caches in Firestore.
    """
    # 1) Check Firestore cache
    cached = _firestore_cache_get("player_play_types", player_id)
    if cached:
        cached.pop("_cached_at", None)
        cached["data_available"] = True
        cached["source"] = "cache"
        return cached

    # 2) Fetch from NBA API
    try:
        from nba_api.stats.endpoints import synergyplaytypes
        time.sleep(0.6)  # rate limit

        play_types = []
        for play_type in ["Isolation", "Transition", "PRBallHandler", "PRRollman",
                          "Postup", "Spotup", "Handoff", "Cut", "OffScreen"]:
            try:
                synergy = synergyplaytypes.SynergyPlayTypes(
                    season=CURRENT_SEASON,
                    play_type_nullable=play_type,
                    player_or_team_abbreviation="P",
                    type_grouping_nullable="offensive",
                    per_mode_simple="PerGame",
                    timeout=15,
                )
                df = synergy.get_data_frames()[0]
                player_row = df[df["PLAYER_ID"].astype(str) == str(player_id)]
                if not player_row.empty:
                    row = player_row.iloc[0]
                    play_types.append({
                        "play_type": play_type,
                        "frequency": float(row.get("POSS_PCT", 0)),
                        "ppp": float(row.get("PPP", 0)),
                        "percentile": float(row.get("PERCENTILE", 0)),
                        "gp": int(row.get("GP", 0)),
                        "possessions": float(row.get("POSS", 0)),
                    })
                time.sleep(0.6)  # rate limit between calls
            except Exception as e:
                logger.warning(f"[PLAY-TYPES] {play_type} fetch failed for {player_id}: {e}")
                continue

        result = {
            "player_id": player_id,
            "play_types": play_types,
            "season": CURRENT_SEASON,
            "data_available": len(play_types) > 0,
            "source": "nba_api",
        }

        if play_types:
            _firestore_cache_set("player_play_types", player_id, result)

        return result

    except ImportError:
        logger.error("[PLAY-TYPES] nba_api not installed")
        raise HTTPException(status_code=503, detail="NBA API dependency not available")
    except Exception as e:
        logger.error(f"[PLAY-TYPES] NBA API fetch failed for {player_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch play-type data from NBA API: {str(e)}"
        )


# ─── /api/today — Schedule shortcut ─────────────────────────────────────────

@router.get("/api/today")
async def api_today():
    """
    Convenience alias returning today's games.
    Frontend components may call /api/today instead of /schedule.
    """
    try:
        from services.nba_schedule import get_schedule_service
        service = get_schedule_service()
        games_raw = service.get_todays_games()

        games = []
        for g in games_raw:
            games.append({
                "game_id": g.get("game_id", ""),
                "home": g.get("home_team", ""),
                "away": g.get("away_team", ""),
                "home_score": g.get("home_score", 0),
                "away_score": g.get("away_score", 0),
                "status": g.get("status", "scheduled"),
                "time": g.get("status_text", ""),
            })

        return {
            "games": games,
            "date": str(datetime.now().date()),
            "total": len(games),
        }
    except Exception as e:
        logger.error(f"[API/TODAY] Error: {e}")
        return {"games": [], "date": str(datetime.now().date()), "total": 0}


# ─── /api/live/today — Live scores shortcut ──────────────────────────────────

@router.get("/api/live/today")
async def api_live_today():
    """
    Alias for today's live scores — some frontend widgets hit /api/live/today.
    """
    return await api_today()
