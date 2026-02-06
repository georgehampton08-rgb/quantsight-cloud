"""
Tracking Data Fetcher Service
Fetches and persists all 5 advanced tracking data layers for intelligent reuse.
"""
import sqlite3
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)

# nba_api imports
try:
    from nba_api.stats.endpoints import (
        leaguehustlestatsplayer,
        leaguedashptdefend,
        leaguedashplayerptshot,
        leaguedashplayerstats,
        playerdashptpass,
        playerdashboardbyyearoveryear,
    )
    HAS_NBA_API = True
except ImportError:
    HAS_NBA_API = False
    logger.warning("nba_api not installed - tracking data unavailable")


class TrackingDataFetcher:
    """
    Fetches and caches all 5 advanced NBA tracking data layers.
    Data is persisted to SQLite for intelligent reuse across sessions.
    """
    
    RATE_LIMIT = 1.5  # seconds between API calls
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def _ensure_tables(self):
        """Create all tracking data tables"""
        conn = self._get_connection()
        
        # Hustle stats table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_hustle (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                team TEXT,
                contested_shots REAL,
                contested_shots_2pt REAL,
                contested_shots_3pt REAL,
                deflections REAL,
                charges_drawn REAL,
                screen_assists REAL,
                loose_balls_recovered REAL,
                off_boxouts REAL,
                def_boxouts REAL,
                updated_at TIMESTAMP
            )
        """)
        
        # Defensive tracking table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_defense_tracking (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                team TEXT,
                position TEXT,
                d_fgm REAL,
                d_fga REAL,
                d_fg_pct REAL,
                normal_fg_pct REAL,
                pct_plusminus REAL,
                freq REAL,
                updated_at TIMESTAMP
            )
        """)
        
        # Shot clock distribution table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_shot_clock (
                player_id TEXT,
                player_name TEXT,
                team TEXT,
                clock_range TEXT,
                fga_freq REAL,
                fgm REAL,
                fga REAL,
                fg_pct REAL,
                efg_pct REAL,
                updated_at TIMESTAMP,
                PRIMARY KEY (player_id, clock_range)
            )
        """)
        
        # Advanced stats table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_advanced_stats (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                team TEXT,
                off_rating REAL,
                def_rating REAL,
                net_rating REAL,
                ast_pct REAL,
                ast_to REAL,
                ast_ratio REAL,
                oreb_pct REAL,
                dreb_pct REAL,
                reb_pct REAL,
                ts_pct REAL,
                efg_pct REAL,
                usg_pct REAL,
                pace REAL,
                pie REAL,
                updated_at TIMESTAMP
            )
        """)
        
        # Player passing table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_passing (
                player_id TEXT,
                team_id TEXT,
                pass_to_player_id TEXT,
                pass_to_name TEXT,
                frequency REAL,
                passes REAL,
                assists REAL,
                fg_pct REAL,
                fg3_pct REAL,
                updated_at TIMESTAMP,
                PRIMARY KEY (player_id, pass_to_player_id)
            )
        """)
        
        # Fetch metadata table
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
    
    def _rate_limit(self):
        """Apply rate limiting"""
        time.sleep(self.RATE_LIMIT)
    
    # ==========================================================================
    # FETCH METHODS
    # ==========================================================================
    
    def fetch_hustle_stats(self) -> Dict:
        """Fetch and save hustle stats for all players"""
        if not HAS_NBA_API:
            return {'success': False, 'error': 'nba_api not installed'}
        
        logger.info("Fetching hustle stats...")
        start = time.time()
        
        try:
            self._rate_limit()
            hustle = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
                season=CURRENT_SEASON,
                season_type_all_star='Regular Season',
                per_mode_time='PerGame'
            )
            df = hustle.get_data_frames()[0]
            
            conn = self._get_connection()
            now = datetime.now().isoformat()
            
            for _, row in df.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO player_hustle
                    (player_id, player_name, team, contested_shots, contested_shots_2pt,
                     contested_shots_3pt, deflections, charges_drawn, screen_assists,
                     loose_balls_recovered, off_boxouts, def_boxouts, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row['PLAYER_ID']), row['PLAYER_NAME'], row['TEAM_ABBREVIATION'],
                    row['CONTESTED_SHOTS'], row['CONTESTED_SHOTS_2PT'], row['CONTESTED_SHOTS_3PT'],
                    row['DEFLECTIONS'], row['CHARGES_DRAWN'], row['SCREEN_ASSISTS'],
                    row['LOOSE_BALLS_RECOVERED'], row.get('OFF_BOXOUTS', 0), row.get('DEF_BOXOUTS', 0),
                    now
                ))
            
            duration = int((time.time() - start) * 1000)
            conn.execute("""
                INSERT OR REPLACE INTO tracking_fetch_log (data_type, last_fetch, rows_fetched, duration_ms)
                VALUES (?, ?, ?, ?)
            """, ('hustle', now, len(df), duration))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved {len(df)} hustle records in {duration}ms")
            return {'success': True, 'rows': len(df), 'duration_ms': duration}
            
        except Exception as e:
            logger.error(f"Hustle fetch error: {e}")
            return {'success': False, 'error': str(e)}
    
    def fetch_defense_tracking(self) -> Dict:
        """Fetch and save defensive tracking for all players"""
        if not HAS_NBA_API:
            return {'success': False, 'error': 'nba_api not installed'}
        
        logger.info("Fetching defense tracking...")
        start = time.time()
        
        try:
            self._rate_limit()
            defense = leaguedashptdefend.LeagueDashPtDefend(
                season=CURRENT_SEASON,
                season_type_all_star='Regular Season',
                per_mode_simple='PerGame',
                defense_category='Overall'
            )
            df = defense.get_data_frames()[0]
            
            conn = self._get_connection()
            now = datetime.now().isoformat()
            
            for _, row in df.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO player_defense_tracking
                    (player_id, player_name, team, position, d_fgm, d_fga, d_fg_pct,
                     normal_fg_pct, pct_plusminus, freq, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row['CLOSE_DEF_PERSON_ID']), row['PLAYER_NAME'],
                    row['PLAYER_LAST_TEAM_ABBREVIATION'], row.get('PLAYER_POSITION', ''),
                    row['D_FGM'], row['D_FGA'], row['D_FG_PCT'],
                    row['NORMAL_FG_PCT'], row['PCT_PLUSMINUS'], row['FREQ'],
                    now
                ))
            
            duration = int((time.time() - start) * 1000)
            conn.execute("""
                INSERT OR REPLACE INTO tracking_fetch_log (data_type, last_fetch, rows_fetched, duration_ms)
                VALUES (?, ?, ?, ?)
            """, ('defense', now, len(df), duration))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved {len(df)} defense records in {duration}ms")
            return {'success': True, 'rows': len(df), 'duration_ms': duration}
            
        except Exception as e:
            logger.error(f"Defense fetch error: {e}")
            return {'success': False, 'error': str(e)}
    
    def fetch_shot_clock(self) -> Dict:
        """Fetch and save shot clock distribution for all players"""
        if not HAS_NBA_API:
            return {'success': False, 'error': 'nba_api not installed'}
        
        logger.info("Fetching shot clock distribution...")
        start = time.time()
        
        try:
            self._rate_limit()
            shots = leaguedashplayerptshot.LeagueDashPlayerPtShot(
                season=CURRENT_SEASON,
                season_type_all_star='Regular Season',
                per_mode_simple='PerGame'
            )
            df = shots.get_data_frames()[0]
            
            conn = self._get_connection()
            now = datetime.now().isoformat()
            
            for _, row in df.iterrows():
                # Shot clock range is derived from the data
                clock_range = 'all'  # Default, would parse from actual data
                conn.execute("""
                    INSERT OR REPLACE INTO player_shot_clock
                    (player_id, player_name, team, clock_range, fga_freq, fgm, fga, 
                     fg_pct, efg_pct, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row['PLAYER_ID']), row['PLAYER_NAME'],
                    row['PLAYER_LAST_TEAM_ABBREVIATION'], clock_range,
                    row['FGA_FREQUENCY'], row['FGM'], row['FGA'],
                    row['FG_PCT'], row['EFG_PCT'],
                    now
                ))
            
            duration = int((time.time() - start) * 1000)
            conn.execute("""
                INSERT OR REPLACE INTO tracking_fetch_log (data_type, last_fetch, rows_fetched, duration_ms)
                VALUES (?, ?, ?, ?)
            """, ('shot_clock', now, len(df), duration))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved {len(df)} shot clock records in {duration}ms")
            return {'success': True, 'rows': len(df), 'duration_ms': duration}
            
        except Exception as e:
            logger.error(f"Shot clock fetch error: {e}")
            return {'success': False, 'error': str(e)}
    
    def fetch_advanced_stats(self) -> Dict:
        """Fetch and save advanced stats for all players"""
        if not HAS_NBA_API:
            return {'success': False, 'error': 'nba_api not installed'}
        
        logger.info("Fetching advanced stats...")
        start = time.time()
        
        try:
            self._rate_limit()
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=CURRENT_SEASON,
                season_type_all_star='Regular Season',
                per_mode_detailed='PerGame',
                measure_type_detailed_defense='Advanced'
            )
            df = stats.get_data_frames()[0]
            
            conn = self._get_connection()
            now = datetime.now().isoformat()
            
            for _, row in df.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO player_advanced_stats
                    (player_id, player_name, team, off_rating, def_rating, net_rating,
                     ast_pct, ast_to, ast_ratio, oreb_pct, dreb_pct, reb_pct,
                     ts_pct, efg_pct, usg_pct, pace, pie, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row['PLAYER_ID']), row['PLAYER_NAME'], row['TEAM_ABBREVIATION'],
                    row.get('OFF_RATING', 0), row.get('DEF_RATING', 0), row.get('NET_RATING', 0),
                    row.get('AST_PCT', 0), row.get('AST_TO', 0), row.get('AST_RATIO', 0),
                    row.get('OREB_PCT', 0), row.get('DREB_PCT', 0), row.get('REB_PCT', 0),
                    row.get('TS_PCT', 0), row.get('EFG_PCT', 0), row.get('USG_PCT', 0),
                    row.get('PACE', 0), row.get('PIE', 0),
                    now
                ))
            
            duration = int((time.time() - start) * 1000)
            conn.execute("""
                INSERT OR REPLACE INTO tracking_fetch_log (data_type, last_fetch, rows_fetched, duration_ms)
                VALUES (?, ?, ?, ?)
            """, ('advanced', now, len(df), duration))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved {len(df)} advanced stat records in {duration}ms")
            return {'success': True, 'rows': len(df), 'duration_ms': duration}
            
        except Exception as e:
            logger.error(f"Advanced stats fetch error: {e}")
            return {'success': False, 'error': str(e)}
    
    def fetch_all(self) -> Dict:
        """Fetch and save all tracking data layers"""
        logger.info("="*60)
        logger.info("FETCHING ALL TRACKING DATA")
        logger.info("="*60)
        
        results = {
            'hustle': self.fetch_hustle_stats(),
            'defense': self.fetch_defense_tracking(),
            'shot_clock': self.fetch_shot_clock(),
            'advanced': self.fetch_advanced_stats(),
        }
        
        success_count = sum(1 for r in results.values() if r.get('success'))
        total_rows = sum(r.get('rows', 0) for r in results.values())
        
        logger.info(f"Completed: {success_count}/4 layers, {total_rows} total records")
        
        return {
            'success': success_count == 4,
            'layers': results,
            'total_rows': total_rows,
        }
    
    # ==========================================================================
    # QUERY METHODS
    # ==========================================================================
    
    def get_player_hustle(self, player_id: str) -> Optional[Dict]:
        """Get cached hustle stats for a player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM player_hustle WHERE player_id = ?", (str(player_id),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_player_defense(self, player_id: str) -> Optional[Dict]:
        """Get cached defensive tracking for a player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM player_defense_tracking WHERE player_id = ?", (str(player_id),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_player_advanced(self, player_id: str) -> Optional[Dict]:
        """Get cached advanced stats for a player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM player_advanced_stats WHERE player_id = ?", (str(player_id),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_player_full_profile(self, player_id: str) -> Dict:
        """Get complete tracking profile for a player"""
        return {
            'player_id': player_id,
            'hustle': self.get_player_hustle(player_id),
            'defense': self.get_player_defense(player_id),
            'advanced': self.get_player_advanced(player_id),
        }
    
    def get_fetch_status(self) -> Dict:
        """Get status of all tracking data fetches"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracking_fetch_log")
        rows = cursor.fetchall()
        conn.close()
        return {row['data_type']: dict(row) for row in rows}


# Singleton
_fetcher = None

def get_tracking_fetcher() -> TrackingDataFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = TrackingDataFetcher()
    return _fetcher


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = get_tracking_fetcher()
    
    print("Fetching all tracking data...")
    result = fetcher.fetch_all()
    
    print(f"\nResults: {json.dumps(result, indent=2)}")
    
    # Test query
    print("\n" + "="*50)
    print("Testing LeBron James profile:")
    profile = fetcher.get_player_full_profile("2544")
    print(json.dumps(profile, indent=2, default=str))
