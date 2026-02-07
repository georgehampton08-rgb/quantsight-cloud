"""
Season Baseline Service — Firestore-Backed
============================================
Replaces the dead `cloud_sql_data_service` with Firestore reads.
Provides player and team season baselines for the live pulse producer.

Firestore Schema:
    season_baselines/{season}/players/{player_id}
        - ppg, rpg, apg, usage_pct, ts_pct, efg_pct, fg3_pct, min_pg
        - game_count, last_updated

    season_baselines/{season}/teams/{team_tricode}
        - def_rating, off_rating, pace, matchup_difficulty
        - last_updated

Caching:
    In-memory LRU cache with 15-minute TTL to avoid per-request Firestore reads.
    Cache is warm after first request and refreshed lazily.
"""

import logging
import time
from typing import Dict, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

CURRENT_SEASON = "2025-26"
LEAGUE_AVG_DEF_RATING = 110.0
LEAGUE_AVG_USAGE = 0.20
LEAGUE_AVG_TS = 0.55
CACHE_TTL_SECONDS = 900  # 15 minutes

# Defense rating tiers
_DEF_TIERS = {
    'elite': (0, 106),
    'tough': (106, 110),
    'average': (110, 114),
    'weak': (114, float('inf')),
}


# ============================================================================
# FIRESTORE CONNECTION
# ============================================================================

_db = None

def _get_db():
    """Get Firestore client (lazy init)."""
    global _db
    if _db is None:
        try:
            from firebase_admin import firestore
            _db = firestore.client()
        except Exception as e:
            logger.error(f"Failed to get Firestore client: {e}")
            return None
    return _db


# ============================================================================
# IN-MEMORY CACHE
# ============================================================================

class _BaselineCache:
    """Simple TTL cache for season baselines."""

    def __init__(self, ttl: int = CACHE_TTL_SECONDS):
        self._ttl = ttl
        self._player_cache: Dict[str, Tuple[dict, float]] = {}
        self._team_cache: Dict[str, Tuple[dict, float]] = {}
        self._all_players_loaded = False
        self._all_teams_loaded = False
        self._last_full_load = 0.0

    def get_player(self, player_id: str) -> Optional[dict]:
        if player_id in self._player_cache:
            data, ts = self._player_cache[player_id]
            if time.time() - ts < self._ttl:
                return data
        return None

    def set_player(self, player_id: str, data: dict):
        self._player_cache[player_id] = (data, time.time())

    def get_team(self, tricode: str) -> Optional[dict]:
        if tricode in self._team_cache:
            data, ts = self._team_cache[tricode]
            if time.time() - ts < self._ttl:
                return data
        return None

    def set_team(self, tricode: str, data: dict):
        self._team_cache[tricode] = (data, time.time())

    def bulk_load_players(self, players: Dict[str, dict]):
        now = time.time()
        for pid, data in players.items():
            self._player_cache[pid] = (data, now)
        self._all_players_loaded = True
        self._last_full_load = now

    def bulk_load_teams(self, teams: Dict[str, dict]):
        now = time.time()
        for tricode, data in teams.items():
            self._team_cache[tricode] = (data, now)
        self._all_teams_loaded = True

    def needs_full_load(self) -> bool:
        return (
            not self._all_players_loaded or
            time.time() - self._last_full_load > self._ttl
        )

    @property
    def player_count(self) -> int:
        return len(self._player_cache)

    @property
    def team_count(self) -> int:
        return len(self._team_cache)


_cache = _BaselineCache()


# ============================================================================
# BULK WARM-UP (called once at startup or on-demand)
# ============================================================================

def warm_cache(season: str = CURRENT_SEASON) -> bool:
    """
    Load all season baselines into memory cache.
    Returns True if successful, False if Firestore unavailable.
    """
    db = _get_db()
    if db is None:
        logger.warning("Cannot warm cache — Firestore unavailable")
        return False

    try:
        # Load all players
        players_ref = db.collection("season_baselines").document(season).collection("players")
        player_docs = players_ref.stream()
        players = {}
        for doc in player_docs:
            players[doc.id] = doc.to_dict()
        _cache.bulk_load_players(players)
        logger.info(f"✅ Warmed player baseline cache: {len(players)} players")

        # Load all teams
        teams_ref = db.collection("season_baselines").document(season).collection("teams")
        team_docs = teams_ref.stream()
        teams = {}
        for doc in team_docs:
            teams[doc.id] = doc.to_dict()
        _cache.bulk_load_teams(teams)
        logger.info(f"✅ Warmed team baseline cache: {len(teams)} teams")

        return True

    except Exception as e:
        logger.error(f"Failed to warm cache: {e}")
        return False


# ============================================================================
# PLAYER BASELINE READS
# ============================================================================

def get_player_season_usage(player_id: str) -> float:
    """
    Get player's season-average usage rate.

    Returns:
        Usage rate as decimal (0.0-1.0). Falls back to league average (0.20).
    """
    data = _get_player_data(player_id)
    if data and 'usage_pct' in data:
        return data['usage_pct']
    return LEAGUE_AVG_USAGE


def get_player_rolling_ts(player_id: str) -> float:
    """
    Get player's season-average true shooting percentage.

    Returns:
        TS% as decimal (0.0-1.0). Falls back to league average (0.55).
    """
    data = _get_player_data(player_id)
    if data and 'ts_pct' in data:
        return data['ts_pct']
    return LEAGUE_AVG_TS


def get_player_season_ppg(player_id: str) -> float:
    """
    Get player's season-average points per game.

    Returns:
        PPG as float. Falls back to 10.0 (rough league average for active players).
    """
    data = _get_player_data(player_id)
    if data and 'ppg' in data:
        return data['ppg']
    return 10.0


def get_player_baselines(player_id: str) -> Optional[dict]:
    """Get full player baseline document."""
    return _get_player_data(player_id)


def _get_player_data(player_id: str) -> Optional[dict]:
    """Internal: get player data from cache or Firestore."""
    # 1. Check cache
    cached = _cache.get_player(player_id)
    if cached is not None:
        return cached

    # 2. If cache needs full reload, load everything
    if _cache.needs_full_load():
        warm_cache()
        cached = _cache.get_player(player_id)
        if cached is not None:
            return cached

    # 3. Single-document fallback
    db = _get_db()
    if db is None:
        return None

    try:
        doc = db.collection("season_baselines").document(CURRENT_SEASON).collection("players").document(str(player_id)).get()
        if doc.exists:
            data = doc.to_dict()
            _cache.set_player(player_id, data)
            return data
    except Exception as e:
        logger.debug(f"Failed to fetch player baseline {player_id}: {e}")

    return None


# ============================================================================
# TEAM DEFENSE / PACE READS
# ============================================================================

def get_team_defense_rating(team_tricode: str) -> Tuple[float, str]:
    """
    Get team defensive rating and matchup difficulty classification.

    Returns:
        Tuple of (def_rating, difficulty) where difficulty is:
        'elite', 'tough', 'average', or 'weak'.
        Falls back to (110.0, 'average').
    """
    data = _get_team_data(team_tricode)
    if data and 'def_rating' in data:
        rating = data['def_rating']
        difficulty = _classify_defense(rating)
        return rating, difficulty
    return LEAGUE_AVG_DEF_RATING, 'average'


def get_team_pace(team_tricode: str) -> float:
    """
    Get team pace factor.

    Returns:
        Pace as float (possessions per 48 min). Falls back to 100.0.
    """
    data = _get_team_data(team_tricode)
    if data and 'pace' in data:
        return data['pace']
    return 100.0


def _get_team_data(team_tricode: str) -> Optional[dict]:
    """Internal: get team data from cache or Firestore."""
    cached = _cache.get_team(team_tricode)
    if cached is not None:
        return cached

    db = _get_db()
    if db is None:
        return None

    try:
        doc = db.collection("season_baselines").document(CURRENT_SEASON).collection("teams").document(team_tricode).get()
        if doc.exists:
            data = doc.to_dict()
            _cache.set_team(team_tricode, data)
            return data
    except Exception as e:
        logger.debug(f"Failed to fetch team baseline {team_tricode}: {e}")

    return None


def _classify_defense(rating: float) -> str:
    """Classify defensive rating into tiers."""
    for tier, (low, high) in _DEF_TIERS.items():
        if low <= rating < high:
            return tier
    return 'average'


# ============================================================================
# PURE MATH FUNCTIONS (replace stubs from cloud_sql_data_service)
# ============================================================================

def calculate_usage_vacuum(current_usage: float, season_avg_usage: float) -> bool:
    """
    Detect if a player is in a 'usage vacuum' — taking significantly more
    possessions than their season average (e.g. teammate injury, hot hand).

    Returns True if current in-game usage exceeds season average by 20%+.
    """
    if season_avg_usage <= 0:
        return False
    return current_usage > (season_avg_usage * 1.20)


def calculate_heat_scale(current_ts: float, season_avg_ts: float) -> str:
    """
    Classify a player's current shooting efficiency relative to season baseline.

    Returns:
        'hot' (>= +5% above season TS),
        'cold' (<= -5% below season TS),
        'steady' (within ±5%)
    """
    if season_avg_ts <= 0:
        return 'steady'

    delta = current_ts - season_avg_ts

    if delta >= 0.05:
        return 'hot'
    elif delta <= -0.05:
        return 'cold'
    else:
        return 'steady'


# ============================================================================
# STATUS / DIAGNOSTICS
# ============================================================================

def get_baseline_status() -> dict:
    """Get current baseline service status for health checks."""
    return {
        "service": "season_baseline_service",
        "season": CURRENT_SEASON,
        "players_cached": _cache.player_count,
        "teams_cached": _cache.team_count,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "firestore_available": _get_db() is not None,
    }
