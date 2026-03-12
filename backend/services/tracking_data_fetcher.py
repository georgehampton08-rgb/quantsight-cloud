"""
Tracking Data Fetcher Service — ESPN Edition (v2)
==================================================
Fetches and persists advanced tracking data layers.

MIGRATION (Mar 2026):
  - REMOVED: nba_api leaguehustlestatsplayer, leaguedashptdefend,
    leaguedashplayerptshot, leaguedashplayerstats, playerdashptpass
    (rate-limited on Cloud Run, 3-8s per call, often 429/timeout)
  - ADDED:   ESPN /athletes/{id}/stats and ESPN season-level stats endpoints
    (public, no auth, ~200-500ms, consistent JSON structure)

ESPN endpoints used:
  Player stats:   https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/stats
  Player gamelog: https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/gamelog?season=2026
  Season stats:   https://site.api.espn.com/apis/site/v2/sports/basketball/nba/statistics/athletes
"""
import sqlite3
import time
import json
import logging
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)

ESPN_ATHLETE_STATS = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
    "/athletes/{athlete_id}/stats?region=us&lang=en&contentorigin=espn"
)
ESPN_ATHLETE_GAMELOG = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
    "/athletes/{athlete_id}/gamelog?season=2026"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.espn.com/nba/",
}


class TrackingDataFetcher:
    """
    Fetches and caches advanced NBA stats via ESPN public APIs.
    Data persisted in SQLite for reuse across sessions.
    """

    RATE_LIMIT = 0.5  # seconds between ESPN calls (much faster than nba_api)

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "nba_data.db"
        self.db_path = str(db_path)
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _ensure_tables(self):
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_advanced_stats (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                team TEXT,
                off_rating REAL, def_rating REAL, net_rating REAL,
                ast_pct REAL, ast_to REAL, ast_ratio REAL,
                oreb_pct REAL, dreb_pct REAL, reb_pct REAL,
                ts_pct REAL, efg_pct REAL, usg_pct REAL,
                pace REAL, pie REAL,
                pts REAL, reb REAL, ast REAL, stl REAL, blk REAL,
                updated_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_gamelog (
                player_id TEXT,
                game_id TEXT,
                game_date TEXT,
                opponent TEXT,
                pts INTEGER, reb INTEGER, ast INTEGER,
                stl INTEGER, blk INTEGER, to_ INTEGER,
                fg_pct REAL, fg3_pct REAL, ft_pct REAL,
                min TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY (player_id, game_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracking_fetch_log (
                data_type TEXT PRIMARY KEY,
                last_fetch TIMESTAMP,
                rows_fetched INTEGER,
                duration_ms INTEGER
            )
        """)
        conn.commit()
        conn.close()

    # ── ESPN Fetch Helpers ────────────────────────────────────────────────────

    def _espn_get(self, url: str) -> Optional[dict]:
        """Synchronous ESPN fetch with rate limiting."""
        import urllib.request
        import urllib.error
        time.sleep(self.RATE_LIMIT)
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            logger.warning(f"[TrackingFetcher] ESPN fetch failed {url}: {e}")
            return None

    # ── Fetch Methods ─────────────────────────────────────────────────────────

    def fetch_player_stats(self, espn_athlete_id: str) -> Dict:
        """Fetch and cache season stats for a single player via ESPN."""
        start = time.time()
        url = ESPN_ATHLETE_STATS.format(athlete_id=espn_athlete_id)
        data = self._espn_get(url)
        if not data:
            return {"success": False, "error": "ESPN fetch failed"}

        # ESPN stats structure: data.splits.categories[].stats[]
        try:
            splits = data.get("splits", {})
            categories = splits.get("categories", [])
            stat_map: Dict[str, float] = {}
            for cat in categories:
                for s in cat.get("stats", []):
                    stat_map[s.get("name", "")] = s.get("value", 0.0)

            athlete = data.get("athlete", {})
            name = athlete.get("displayName", "Unknown")
            team = (athlete.get("team") or {}).get("abbreviation", "")

            conn = self._get_connection()
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO player_advanced_stats
                (player_id, player_name, team,
                 pts, reb, ast, stl, blk,
                 fg_pct, fg3_pct, ts_pct, efg_pct, usg_pct,
                 off_rating, def_rating, net_rating,
                 updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                str(espn_athlete_id), name, team,
                stat_map.get("points", 0), stat_map.get("rebounds", 0),
                stat_map.get("assists", 0), stat_map.get("steals", 0),
                stat_map.get("blocks", 0),
                stat_map.get("fieldGoalPct", 0), stat_map.get("threePointFieldGoalPct", 0),
                stat_map.get("trueShootingPct", 0), stat_map.get("effectiveFieldGoalPct", 0),
                stat_map.get("usageRate", 0),
                stat_map.get("offensiveRating", 0), stat_map.get("defensiveRating", 0),
                stat_map.get("netRating", 0),
                now,
            ))
            duration = int((time.time() - start) * 1000)
            conn.execute(
                "INSERT OR REPLACE INTO tracking_fetch_log VALUES (?,?,?,?)",
                (f"stats_{espn_athlete_id}", now, 1, duration),
            )
            conn.commit()
            conn.close()
            return {"success": True, "player": name, "duration_ms": duration}
        except Exception as e:
            logger.error(f"[TrackingFetcher] Stat parse error: {e}")
            return {"success": False, "error": str(e)}

    def fetch_player_gamelog(self, espn_athlete_id: str) -> Dict:
        """Fetch and cache this season's game log for a player via ESPN."""
        start = time.time()
        url = ESPN_ATHLETE_GAMELOG.format(athlete_id=espn_athlete_id)
        data = self._espn_get(url)
        if not data:
            return {"success": False, "error": "ESPN fetch failed"}

        try:
            events = data.get("events", {})
            conn = self._get_connection()
            now = datetime.now().isoformat()
            rows = 0
            for game_id, event in events.items():
                stats = {s["name"]: s.get("value", 0) for s in event.get("stats", [])}
                conn.execute("""
                    INSERT OR REPLACE INTO player_gamelog
                    (player_id, game_id, game_date, opponent,
                     pts, reb, ast, stl, blk, to_,
                     fg_pct, fg3_pct, ft_pct, min, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    str(espn_athlete_id), game_id,
                    event.get("gameDate", ""),
                    event.get("opponent", {}).get("abbreviation", ""),
                    int(stats.get("points", 0)), int(stats.get("rebounds", 0)),
                    int(stats.get("assists", 0)), int(stats.get("steals", 0)),
                    int(stats.get("blocks", 0)), int(stats.get("turnovers", 0)),
                    stats.get("fieldGoalPct", 0), stats.get("threePointFieldGoalPct", 0),
                    stats.get("freeThrowPct", 0),
                    event.get("minutes", ""),
                    now,
                ))
                rows += 1
            duration = int((time.time() - start) * 1000)
            conn.execute(
                "INSERT OR REPLACE INTO tracking_fetch_log VALUES (?,?,?,?)",
                (f"gamelog_{espn_athlete_id}", now, rows, duration),
            )
            conn.commit()
            conn.close()
            return {"success": True, "rows": rows, "duration_ms": duration}
        except Exception as e:
            logger.error(f"[TrackingFetcher] Gamelog parse error: {e}")
            return {"success": False, "error": str(e)}

    # ── Query Methods ─────────────────────────────────────────────────────────

    def get_player_advanced(self, player_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM player_advanced_stats WHERE player_id = ?",
            (str(player_id),),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_player_gamelog(self, player_id: str, limit: int = 20) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM player_gamelog WHERE player_id = ? ORDER BY game_date DESC LIMIT ?",
            (str(player_id), limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_player_full_profile(self, player_id: str) -> Dict:
        return {
            "player_id": player_id,
            "advanced": self.get_player_advanced(player_id),
            "recent_games": self.get_player_gamelog(player_id, limit=10),
        }

    def get_fetch_status(self) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracking_fetch_log")
        rows = cursor.fetchall()
        conn.close()
        return {row["data_type"]: dict(row) for row in rows}


# Singleton
_fetcher = None


def get_tracking_fetcher() -> TrackingDataFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = TrackingDataFetcher()
    return _fetcher
