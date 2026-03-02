"""
Game Logs & Box Scores API Endpoints
======================================
Provides two categories of endpoints:

1. /api/game-logs  — Legacy stub (preserved; do not remove)
2. /api/box-scores — Historical final scores from Firestore game_logs collection
   - GET /api/box-scores/dates  : list all dates with saved game data
   - GET /api/box-scores        : final team scores for a specific date
"""
import re
import logging
from datetime import date as date_type, datetime
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Date validation ──────────────────────────────────────────────────────────
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _validate_date(date_str: str) -> None:
    """Raise 400 if date_str is not YYYY-MM-DD or represents an impossible date."""
    if not _DATE_RE.match(date_str):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format '{date_str}'. Expected YYYY-MM-DD."
        )
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible date '{date_str}'. Please provide a real calendar date."
        )

def _get_firebase_service():
    """
    Lazy-import Firebase service to avoid import-time crashes if SDK not
    installed or credentials are absent. Returns None on failure.
    """
    try:
        from services.firebase_admin_service import get_firebase_service
        svc = get_firebase_service()
        if svc is None:
            logger.warning("Firebase service returned None (degraded mode).")
        return svc
    except Exception as e:
        logger.error(f"Failed to import/init Firebase service: {e}")
        return None


# ─── Legacy stub (kept to avoid breaking existing references) ─────────────────

@router.get("/api/game-logs")
async def get_game_logs(
    player_id: Optional[str] = Query(None, description="NBA player ID"),
    team_id: Optional[str] = Query(None, description="Team tricode"),
    game_id: Optional[str] = Query(None, description="NBA game ID"),
    date: Optional[date_type] = Query(None, description="Game date (YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of logs to return")
):
    """
    Legacy game logs endpoint (stub — preserved for backward compatibility).
    Use /api/box-scores for historical data.
    """
    if not any([player_id, team_id, game_id, date]):
        raise HTTPException(
            status_code=400,
            detail="Must provide at least one filter: player_id, team_id, game_id, or date"
        )
    return {
        "filters": {
            "player_id": player_id,
            "team_id": team_id,
            "game_id": game_id,
            "date": date.isoformat() if date else None
        },
        "count": 0,
        "limit": limit,
        "logs": [],
        "note": "Use /api/box-scores for historical final score data."
    }


# ─── Box Scores: Available Dates ──────────────────────────────────────────────

@router.get("/api/box-scores/dates")
def get_box_score_dates():
    """
    Returns a list of all dates that have at least one saved game log
    in the Firestore `game_logs` collection.

    Used by the Box Scores UI to highlight dates in the date picker
    and auto-select the most recent date with data.

    Response:
        {
            "dates": ["2026-02-25", "2026-02-26", ...],  // sorted descending
            "count": 2
        }

    Error conditions:
        503 — Firebase unavailable
        200 + empty list — No game data saved yet
    """
    svc = _get_firebase_service()
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Cannot retrieve game dates."
        )

    try:
        dates = svc.get_game_dates()
        return {
            "dates": dates,
            "count": len(dates)
        }
    except Exception as e:
        logger.error(f"get_box_score_dates failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to retrieve game dates: {str(e)}"
        )


# ─── Box Scores: Final Scores for a Date ──────────────────────────────────────

@router.get("/api/box-scores")
def get_box_scores_for_date(
    date: str = Query(..., description="Game date in YYYY-MM-DD format")
):
    """
    Returns final team scores for all games saved on a given date.
    Only reads from persisted Firestore `game_logs` — never hits the live NBA API.

    Scoring priority:
      1. metadata.home_score / metadata.away_score (written by GameLogPersister)
      2. Sum of player pts per team (fallback for older saved documents)

    Response:
        {
            "date": "2026-02-25",
            "is_today": false,
            "games": [
                {
                    "game_id": "0022500641",
                    "matchup": "DEN @ DET",
                    "home_team": "DET",
                    "away_team": "DEN",
                    "home_score": 112,
                    "away_score": 98,
                    "status": "FINAL",
                    "winner": "DET"
                }
            ],
            "total_games": 1
        }

    Error conditions:
        400 — Invalid date format
        503 — Firebase unavailable
        200 + empty games list — No data for that date (off day or not yet saved)
    """
    _validate_date(date)

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    is_today = (date == today_str)

    svc = _get_firebase_service()
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Cannot retrieve box scores."
        )

    try:
        games = svc.get_box_scores_for_date(date)
        return {
            "date": date,
            "is_today": is_today,
            "games": games,
            "total_games": len(games)
        }
    except Exception as e:
        logger.error(f"get_box_scores_for_date({date}) failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to retrieve box scores for {date}: {str(e)}"
        )
