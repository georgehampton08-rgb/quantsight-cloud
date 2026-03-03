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


# ─── Box Score: Player Stats ──────────────────────────────────────────────────

@router.get("/api/box-scores/players")
def get_box_score_players(
    date: str = Query(..., description="Game date YYYY-MM-DD"),
    game_id: str = Query(..., description="NBA game ID e.g. 0022500858")
):
    """
    Return player-level stats for a completed game from pulse_stats.

    Path: pulse_stats/{date}/games/{game_id}/quarters/FINAL.players

    Returns:
        {
          "date": "2026-02-28",
          "game_id": "0022500858",
          "home_team": "DET",
          "away_team": "CLE",
          "home_score": 122,
          "away_score": 119,
          "status": "FINAL",
          "quarter_used": "FINAL",
          "home_players": [ { player_id, name, team, pts, reb, ast, stl, blk,
                               min, fgm, fga, fg3m, fta, ftm, plus_minus,
                               ts_pct, efg_pct, usage_pct } ],
          "away_players": [ ... ]
        }
    """
    _validate_date(date)

    svc = _get_firebase_service()
    if svc is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    try:
        db = svc.db
        quarters_ref = (
            db.collection('pulse_stats')
            .document(date)
            .collection('games')
            .document(game_id)
            .collection('quarters')
            .stream()
        )
        quarters = {q.id: q.to_dict() or {} for q in quarters_ref}

        if not quarters:
            raise HTTPException(
                status_code=404,
                detail=f"No quarter data found for game {game_id} on {date}."
            )

        # Prefer FINAL; fallback to most recent quarter
        def _q_sort_key(label: str) -> int:
            if label == 'FINAL': return 99
            if label.startswith('OT'): return 10 + int(label[2:] or 1)
            if label.startswith('Q'):  return int(label[1:] or 0)
            return 0

        if 'FINAL' in quarters:
            quarter_used = 'FINAL'
        else:
            quarter_used = max(quarters.keys(), key=_q_sort_key)

        q_data = quarters[quarter_used]
        home_team  = q_data.get('home_team', '')
        away_team  = q_data.get('away_team', '')
        home_score = int(q_data.get('home_score', 0) or 0)
        away_score = int(q_data.get('away_score', 0) or 0)
        players_map = q_data.get('players', {}) or {}

        home_players: List[Dict[str, Any]] = []
        away_players: List[Dict[str, Any]] = []

        for pid, pdata in players_map.items():
            if not isinstance(pdata, dict):
                continue
            # min is stored as string "36:12" or int — do NOT cast to int()
            # int("36:12") silently becomes 0, marking every player DNP in the UI
            raw_min = pdata.get('min', None)
            if raw_min is None:
                min_val: Any = 0
            elif isinstance(raw_min, (int, float)):
                min_val = int(raw_min)
            else:
                # keep string form "36:12" — frontend renderPlayerRow handles it
                min_val = str(raw_min)

            player = {
                "player_id":   pid,
                "name":        pdata.get('name', f'Player {pid}'),
                "team":        pdata.get('team', ''),
                "pts":         int(pdata.get('pts', 0) or 0),
                "reb":         int(pdata.get('reb', 0) or 0),
                "ast":         int(pdata.get('ast', 0) or 0),
                "stl":         int(pdata.get('stl', 0) or 0),
                "blk":         int(pdata.get('blk', 0) or 0),
                "to":          int(pdata.get('to', 0) or 0),
                "min":         min_val,
                "fgm":         int(pdata.get('fgm', 0) or 0),
                "fga":         int(pdata.get('fga', 0) or 0),
                "fg3m":        int(pdata.get('fg3m', 0) or 0),
                "ftm":         int(pdata.get('ftm', 0) or 0),
                "fta":         int(pdata.get('fta', 0) or 0),
                "plus_minus":  int(pdata.get('plus_minus', 0) or 0),
                "ts_pct":      round(float(pdata.get('ts_pct', 0) or 0), 3),
                "efg_pct":     round(float(pdata.get('efg_pct', 0) or 0), 3),
                "usage_pct":   round(float(pdata.get('usage_pct', 0) or 0), 3),
            }
            team = player["team"]
            if team == home_team:
                home_players.append(player)
            elif team == away_team:
                away_players.append(player)
            else:
                # Assign by count fallback
                if len(home_players) <= len(away_players):
                    home_players.append(player)
                else:
                    away_players.append(player)

        # Sort by pts desc within each team
        home_players.sort(key=lambda p: p['pts'], reverse=True)
        away_players.sort(key=lambda p: p['pts'], reverse=True)

        return {
            "date":         date,
            "game_id":      game_id,
            "home_team":    home_team,
            "away_team":    away_team,
            "home_score":   home_score,
            "away_score":   away_score,
            "status":       "FINAL" if quarter_used == 'FINAL' else f"THRU {quarter_used}",
            "quarter_used": quarter_used,
            "home_players": home_players,
            "away_players": away_players,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_box_score_players({date}/{game_id}) failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))




# ─── AI-Generated Daily Insights ─────────────────────────────────────────────

@router.get("/api/insights/daily")
def get_daily_insights():
    """
    Returns AI-generated daily insights for the Command Center.

    Flow:
      1. Check Firestore cache (insights/daily/{today}) — return if < 30 min old
      2. Fetch today's schedule from NBA public API
      3. Fetch active injury data
      4. Assemble DailyContext payload
      5. Call GeminiInsights.generate_daily_insights()
      6. Cache result, return JSON

    Response shape:
      {
        "date": "YYYY-MM-DD",
        "generated_at": "ISO string",
        "headline": "...",
        "bullets": ["...", "...", "..."],
        "top_watch": { "player": ..., "stat": ..., "grade": ..., "reason": ... },
        "risk_flag": { "player": ..., "reason": ..., "severity": ... },
        "games_tonight": N,
        "ai_powered": true/false,
        "cached": true/false
      }
    """
    import os, json, requests
    from datetime import datetime, timezone, timedelta

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── 1. Check Firestore cache ───────────────────────────────────────────
    cached_result = None
    try:
        from services.firebase_admin_service import FirebaseAdminService
        firebase = FirebaseAdminService()
        if firebase.enabled and firebase.db:
            cache_doc = firebase.db.collection("insights").document("daily").collection("cache").document(today_str).get()
            if cache_doc.exists:
                data = cache_doc.to_dict()
                generated_at_str = data.get("generated_at", "")
                if generated_at_str:
                    generated_at = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
                    age_minutes = (datetime.now(timezone.utc) - generated_at).total_seconds() / 60
                    if age_minutes < 30:
                        data["cached"] = True
                        logger.info(f"✅ Returning cached daily insights (age: {age_minutes:.1f}min)")
                        return data
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")

    # ── 2. Fetch today's schedule ──────────────────────────────────────────
    schedule_games = []
    try:
        CLOUD_API = os.getenv("CLOUD_API_BASE", "https://quantsight-cloud-458498663186.us-central1.run.app")
        resp = requests.get(f"{CLOUD_API}/schedule", timeout=8)
        if resp.ok:
            schedule_data = resp.json()
            schedule_games = schedule_data.get("games", [])
    except Exception as e:
        logger.warning(f"Schedule fetch failed: {e}")

    # ── 3. Fetch injury data ───────────────────────────────────────────────
    injuries = []
    try:
        inj_resp = requests.get(f"{CLOUD_API}/injuries", timeout=8)
        if inj_resp.ok:
            inj_data = inj_resp.json()
            injuries = inj_data.get("injuries", inj_data) if isinstance(inj_data, dict) else inj_data
            injuries = injuries[:10] if isinstance(injuries, list) else []
    except Exception as e:
        logger.warning(f"Injury fetch failed: {e}")

    # ── 4. Assemble DailyContext ───────────────────────────────────────────
    daily_context = {
        "date": today_str,
        "games": schedule_games,
        "injuries": injuries,
    }

    # ── 5. Generate insights ───────────────────────────────────────────────
    try:
        from services.ai_insights import GeminiInsights
        ai = GeminiInsights()
        result = ai.generate_daily_insights(daily_context)
    except Exception as e:
        logger.error(f"GeminiInsights failed: {e}")
        result = {
            "headline": f"{len(schedule_games)} games on tonight's slate",
            "bullets": [
                "Live game data is syncing — check The Pulse for real-time stats.",
                "Injury report loaded — monitor status changes before game time.",
                "Use the Box Scores tab to view live player statistics.",
            ],
            "top_watch": None,
            "risk_flag": None,
            "ai_powered": False,
        }

    result["date"] = today_str
    result["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result["games_tonight"] = len(schedule_games)
    result["cached"] = False

    # ── 6. Save to Firestore cache ─────────────────────────────────────────
    try:
        from services.firebase_admin_service import FirebaseAdminService
        firebase = FirebaseAdminService()
        if firebase.enabled and firebase.db:
            firebase.db.collection("insights").document("daily").collection("cache").document(today_str).set(result)
            logger.info(f"✅ Cached daily insights for {today_str}")
    except Exception as e:
        logger.warning(f"Cache write failed (non-critical): {e}")

    return result

