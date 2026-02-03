"""
Cloud SQL Data Service
======================
Provides database queries for Alpha metrics calculations.
Used by CloudAsyncPulseProducer to fetch player baselines.
"""
import os
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Database connection (lazy initialization)
_engine = None
_session_factory = None


def get_db_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        db_url = os.getenv('DATABASE_URL', '')
        if not db_url:
            logger.warning("DATABASE_URL not set - Cloud SQL features disabled")
            return None
        
        try:
            from sqlalchemy import create_engine
            if db_url.startswith('postgres://'):
                db_url = db_url.replace('postgres://', 'postgresql://', 1)
            _engine = create_engine(db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
            logger.info("✅ Cloud SQL engine initialized")
        except Exception as e:
            logger.error(f"❌ Failed to create database engine: {e}")
            return None
    return _engine


def get_session():
    """Get a database session."""
    global _session_factory
    if _session_factory is None:
        engine = get_db_engine()
        if engine is None:
            return None
        from sqlalchemy.orm import sessionmaker
        _session_factory = sessionmaker(bind=engine)
    return _session_factory()


# =============================================================================
# TEAM DEFENSE CACHE
# =============================================================================

_team_defense_cache: Dict[str, float] = {}
_cache_expiry: Optional[datetime] = None
CACHE_TTL_HOURS = 4
LEAGUE_AVG_DEF_RATING = 112.0


def get_team_defense_rating(team_abbr: str, season: str = '2024-25') -> Tuple[float, str]:
    """
    Get team defensive rating from cache or database.
    
    Returns:
        Tuple of (defensive_rating, matchup_difficulty)
    """
    global _team_defense_cache, _cache_expiry
    
    # Check if cache needs refresh
    if _cache_expiry is None or datetime.utcnow() > _cache_expiry:
        _refresh_defense_cache(season)
    
    def_rating = _team_defense_cache.get(team_abbr, LEAGUE_AVG_DEF_RATING)
    
    # Classify matchup difficulty
    if def_rating < 108:
        difficulty = 'elite'
    elif def_rating > 115:
        difficulty = 'soft'
    else:
        difficulty = 'average'
    
    return def_rating, difficulty


def _refresh_defense_cache(season: str = '2024-25'):
    """Refresh team defense cache from database."""
    global _team_defense_cache, _cache_expiry
    
    session = get_session()
    if session is None:
        logger.warning("No database session - using default defense ratings")
        _cache_expiry = datetime.utcnow() + timedelta(minutes=5)
        return
    
    try:
        from sqlalchemy import text
        result = session.execute(text("""
            SELECT team_abbreviation, defensive_rating 
            FROM team_defense 
            WHERE season = :season
        """), {"season": season})
        
        _team_defense_cache = {row[0]: row[1] for row in result}
        _cache_expiry = datetime.utcnow() + timedelta(hours=CACHE_TTL_HOURS)
        logger.info(f"✅ Refreshed defense cache with {len(_team_defense_cache)} teams")
        
    except Exception as e:
        logger.error(f"❌ Failed to refresh defense cache: {e}")
        _cache_expiry = datetime.utcnow() + timedelta(minutes=5)
    finally:
        session.close()


# =============================================================================
# PLAYER STATS QUERIES
# =============================================================================

def get_player_season_usage(player_id: int, season: str = '2024-25') -> Optional[float]:
    """Get player's season average usage rate."""
    session = get_session()
    if session is None:
        return None
    
    try:
        from sqlalchemy import text
        result = session.execute(text("""
            SELECT usage_rate FROM player_stats 
            WHERE player_id = :player_id AND season = :season
        """), {"player_id": player_id, "season": season})
        
        row = result.fetchone()
        return row[0] if row else None
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch usage rate for player {player_id}: {e}")
        return None
    finally:
        session.close()


def get_player_rolling_ts(player_id: int, season: str = '2024-25') -> Optional[float]:
    """Get player's rolling true shooting percentage."""
    session = get_session()
    if session is None:
        return None
    
    try:
        from sqlalchemy import text
        result = session.execute(text("""
            SELECT rolling_ts_pct FROM player_rolling_averages 
            WHERE player_id = :player_id AND season = :season
            ORDER BY computed_at DESC LIMIT 1
        """), {"player_id": player_id, "season": season})
        
        row = result.fetchone()
        return row[0] if row else None
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch rolling TS% for player {player_id}: {e}")
        return None
    finally:
        session.close()


# =============================================================================
# ALPHA METRICS CALCULATION
# =============================================================================

def calculate_usage_vacuum(
    current_usage: float,
    season_avg_usage: Optional[float],
    threshold_multiplier: float = 1.25
) -> bool:
    """
    Detect if player is in a usage vacuum (significantly higher usage than normal).
    
    Returns True if current usage > season average * threshold
    """
    if season_avg_usage is None or season_avg_usage <= 0:
        return False
    return current_usage > (season_avg_usage * threshold_multiplier)


def calculate_heat_scale(
    current_ts: float,
    season_avg_ts: Optional[float],
    min_scale: int = 0,
    max_scale: int = 100,
    multiplier: float = 500
) -> Optional[int]:
    """
    Calculate Heat Scale based on TS% alpha gap.
    
    Heat Scale represents how much better (or worse) a player is performing
    compared to their season average, scaled to 0-100.
    """
    if season_avg_ts is None or season_avg_ts <= 0:
        return None
    
    alpha_gap = current_ts - season_avg_ts
    heat_scale = int(alpha_gap * multiplier)
    return max(min_scale, min(max_scale, heat_scale))
