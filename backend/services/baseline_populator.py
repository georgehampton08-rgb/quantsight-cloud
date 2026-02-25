"""
Baseline Populator — NBA API → Firestore Writer
=================================================
Fetches season averages from NBA API and writes to Firestore for the
season_baseline_service to read during live games.

Data Sources:
    - Player season averages: nba_api.stats.endpoints.leaguedashplayerstats
    - Team defense/pace: nba_api.stats.endpoints.leaguedashteamstats

Can be triggered:
    1. Admin endpoint: POST /admin/baselines/populate
    2. Cloud Scheduler → Cloud Function (daily 5 AM ET)
    3. Auto-update on game FINAL (producer-triggered)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

CURRENT_SEASON = "2025-26"
NBA_API_SEASON = "2025-26"  # nba_api expects 'YYYY-YY' format


# ============================================================================
# NBA API FETCHERS (synchronous — nba_api is sync-only)
# ============================================================================

def _fetch_player_stats_sync() -> List[dict]:
    """
    Fetch all player per-game stats for current season from NBA API.
    Returns list of player stat dicts.
    """
    try:
        from nba_api.stats.endpoints import leaguedashplayerstats

        logger.info(f"📊 Fetching player stats from NBA API (season={NBA_API_SEASON})...")
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season=NBA_API_SEASON,
            per_mode_detailed='PerGame',
            timeout=30
        )
        df = stats.get_data_frames()[0]
        logger.info(f"✅ Fetched {len(df)} player records from NBA API")

        players = []
        for _, row in df.iterrows():
            player = {
                'player_id': str(row.get('PLAYER_ID', '')),
                'player_name': row.get('PLAYER_NAME', ''),
                'team_tricode': row.get('TEAM_ABBREVIATION', ''),
                'age': int(row.get('AGE', 25)) if row.get('AGE') else 25,
                'gp': int(row.get('GP', 0)),
                'min_pg': float(row.get('MIN', 0) or 0),
                'ppg': float(row.get('PTS', 0) or 0),
                'rpg': float(row.get('REB', 0) or 0),
                'apg': float(row.get('AST', 0) or 0),
                'spg': float(row.get('STL', 0) or 0),
                'bpg': float(row.get('BLK', 0) or 0),
                'tpg': float(row.get('TOV', 0) or 0),
                'fgm': float(row.get('FGM', 0) or 0),
                'fga': float(row.get('FGA', 0) or 0),
                'fg_pct': float(row.get('FG_PCT', 0) or 0),
                'fg3m': float(row.get('FG3M', 0) or 0),
                'fg3a': float(row.get('FG3A', 0) or 0),
                'fg3_pct': float(row.get('FG3_PCT', 0) or 0),
                'ftm': float(row.get('FTM', 0) or 0),
                'fta': float(row.get('FTA', 0) or 0),
                'ft_pct': float(row.get('FT_PCT', 0) or 0),
                'oreb': float(row.get('OREB', 0) or 0),
                'dreb': float(row.get('DREB', 0) or 0),
                'pf': float(row.get('PF', 0) or 0),
                'plus_minus': float(row.get('PLUS_MINUS', 0) or 0),
            }

            # Calculate derived stats
            fga = player['fga']
            fta = player['fta']
            pts = player['ppg']

            # True shooting %
            tsa = fga + (0.44 * fta)
            player['ts_pct'] = round(pts / (2 * tsa), 4) if tsa > 0 else 0.0

            # Effective FG%
            player['efg_pct'] = round((player['fgm'] + 0.5 * player['fg3m']) / fga, 4) if fga > 0 else 0.0

            # Usage rate (approximate from per-game data)
            player['usage_pct'] = round(
                (fga + 0.44 * fta + player['tpg']) /
                (fga + 0.44 * fta + player['tpg'] + 0.001) * 0.20,  # Rough scaling
                4
            )

            players.append(player)

        return players

    except ImportError:
        logger.error("nba_api is not installed — cannot fetch player stats")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch player stats from NBA API: {e}")
        return []


def _fetch_team_stats_sync() -> List[dict]:
    """
    Fetch team defensive/offensive ratings and pace for current season.
    Returns list of team stat dicts.
    """
    try:
        from nba_api.stats.endpoints import leaguedashteamstats

        logger.info(f"📊 Fetching team stats from NBA API (season={NBA_API_SEASON})...")
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season=NBA_API_SEASON,
            per_mode_detailed='PerGame',
            measure_type_detailed_defense='Advanced',
            timeout=30
        )
        df = stats.get_data_frames()[0]
        logger.info(f"✅ Fetched {len(df)} team records from NBA API")

        teams = []
        for _, row in df.iterrows():
            team = {
                'team_id': str(row.get('TEAM_ID', '')),
                'team_name': row.get('TEAM_NAME', ''),
                'team_tricode': row.get('TEAM_ABBREVIATION', ''),
                'gp': int(row.get('GP', 0)),
                'wins': int(row.get('W', 0)),
                'losses': int(row.get('L', 0)),
                'def_rating': float(row.get('DEF_RATING', 110.0) or 110.0),
                'off_rating': float(row.get('OFF_RATING', 110.0) or 110.0),
                'net_rating': float(row.get('NET_RATING', 0) or 0),
                'pace': float(row.get('PACE', 100.0) or 100.0),
            }

            # Classify defense
            dr = team['def_rating']
            if dr < 106:
                team['matchup_difficulty'] = 'elite'
            elif dr < 110:
                team['matchup_difficulty'] = 'tough'
            elif dr < 114:
                team['matchup_difficulty'] = 'average'
            else:
                team['matchup_difficulty'] = 'weak'

            teams.append(team)

        return teams

    except ImportError:
        logger.error("nba_api is not installed — cannot fetch team stats")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch team stats from NBA API: {e}")
        return []


# ============================================================================
# FIRESTORE WRITERS
# ============================================================================

def _write_player_baselines(players: List[dict], season: str = CURRENT_SEASON) -> int:
    """Write player baselines to Firestore. Returns count written."""
    try:
        from firebase_admin import firestore
        db = firestore.client()
    except Exception as e:
        logger.error(f"Cannot write to Firestore: {e}")
        return 0

    count = 0
    batch = db.batch()
    now = datetime.now(timezone.utc).isoformat()

    for i, player in enumerate(players):
        pid = player.get('player_id', '')
        if not pid:
            continue

        doc_ref = (
            db.collection("season_baselines")
            .document(season)
            .collection("players")
            .document(pid)
        )

        doc_data = {**player, 'last_updated': now}
        batch.set(doc_ref, doc_data, merge=True)
        count += 1

        # Firestore batch limit is 500
        if (i + 1) % 450 == 0:
            batch.commit()
            batch = db.batch()
            logger.info(f"   Committed batch ({count} players so far)...")

    # Final commit
    if count % 450 != 0:
        batch.commit()

    return count


def _write_team_baselines(teams: List[dict], season: str = CURRENT_SEASON) -> int:
    """Write team baselines to Firestore. Returns count written."""
    try:
        from firebase_admin import firestore
        db = firestore.client()
    except Exception as e:
        logger.error(f"Cannot write to Firestore: {e}")
        return 0

    count = 0
    batch = db.batch()
    now = datetime.now(timezone.utc).isoformat()

    for team in teams:
        tricode = team.get('team_tricode', '')
        if not tricode:
            continue

        doc_ref = (
            db.collection("season_baselines")
            .document(season)
            .collection("teams")
            .document(tricode)
        )

        doc_data = {**team, 'last_updated': now}
        batch.set(doc_ref, doc_data, merge=True)
        count += 1

    batch.commit()
    return count


# ============================================================================
# ASYNC WRAPPERS (for calling from async FastAPI endpoints)
# ============================================================================

async def populate_all_baselines(season: str = CURRENT_SEASON) -> dict:
    """
    Full population: fetch from NBA API → write to Firestore.
    Returns summary of what was written.
    """
    loop = asyncio.get_event_loop()
    result = {
        'season': season,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'players_fetched': 0,
        'players_written': 0,
        'teams_fetched': 0,
        'teams_written': 0,
        'errors': [],
        'duration_seconds': 0,
    }

    start = time.time()

    # Fetch player stats (runs in thread pool because nba_api is sync)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            players_future = loop.run_in_executor(executor, _fetch_player_stats_sync)
            teams_future = loop.run_in_executor(executor, _fetch_team_stats_sync)

            players = await players_future
            teams = await teams_future
    except Exception as e:
        result['errors'].append(f"Fetch failed: {e}")
        result['duration_seconds'] = round(time.time() - start, 2)
        return result

    result['players_fetched'] = len(players)
    result['teams_fetched'] = len(teams)

    # Write to Firestore
    if players:
        try:
            written = _write_player_baselines(players, season)
            result['players_written'] = written
        except Exception as e:
            result['errors'].append(f"Player write failed: {e}")

    if teams:
        try:
            written = _write_team_baselines(teams, season)
            result['teams_written'] = written
        except Exception as e:
            result['errors'].append(f"Team write failed: {e}")

    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    result['duration_seconds'] = round(time.time() - start, 2)
    result['success'] = len(result['errors']) == 0

    if result['success']:
        logger.info(
            f"✅ Baseline population complete: "
            f"{result['players_written']} players, "
            f"{result['teams_written']} teams in {result['duration_seconds']}s"
        )

        # Warm the cache with fresh data
        from services.season_baseline_service import warm_cache
        warm_cache(season)
    else:
        logger.error(f"❌ Baseline population had errors: {result['errors']}")

    return result


async def populate_players_only(player_ids: List[str] = None, season: str = CURRENT_SEASON) -> dict:
    """
    Incremental player update — fetch and write specific players or all.
    Used after game FINAL for participating players.
    """
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=1) as executor:
        players = await loop.run_in_executor(executor, _fetch_player_stats_sync)

    if player_ids:
        players = [p for p in players if p.get('player_id') in player_ids]

    written = _write_player_baselines(players, season)

    return {
        'season': season,
        'players_fetched': len(players),
        'players_written': written,
        'filtered_by_ids': player_ids is not None,
    }


# ---------------------------------------------------------------------------
# Public aliases — backwards-compatible names expected by smoke harness
# and external callers that pre-date the _sync/_async refactor.
# ---------------------------------------------------------------------------

def fetch_player_season_stats(season: str = CURRENT_SEASON) -> List[dict]:
    """Public alias for _fetch_player_stats_sync (used by smoke harness + external callers)."""
    return _fetch_player_stats_sync()


def fetch_team_season_stats(season: str = CURRENT_SEASON) -> List[dict]:
    """Public alias for _fetch_team_stats_sync."""
    return _fetch_team_stats_sync()
