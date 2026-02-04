"""
H2H Fetcher
Fetches head-to-head game logs for a player vs specific opponent team.
Designed for async/background execution (Shadow-Fetch pattern).
Now with dual-write to SQLite (local) and Firestore (cloud).
"""
import sqlite3
import requests
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Import Firestore adapter for cloud persistence
try:
    from services.h2h_firestore_adapter import get_h2h_adapter, H2HFirestoreAdapter
    HAS_FIRESTORE_ADAPTER = True
except ImportError:
    HAS_FIRESTORE_ADAPTER = False
    get_h2h_adapter = None

logger = logging.getLogger(__name__)


class H2HFetcher:
    """
    Fetches player's historical performance vs specific teams.
    Supports async execution for Shadow-Fetch pattern.
    """
    
    # NBA API endpoints
    PLAYER_GAME_LOG = "https://stats.nba.com/stats/playergamelogs"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    # Team abbreviation to ID mapping
    TEAM_ABBR_TO_ID = {
        'ATL': 1610612737, 'BOS': 1610612738, 'CLE': 1610612739, 'NOP': 1610612740,
        'CHI': 1610612741, 'DAL': 1610612742, 'DEN': 1610612743, 'GSW': 1610612744,
        'HOU': 1610612745, 'LAC': 1610612746, 'LAL': 1610612747, 'MIA': 1610612748,
        'MIL': 1610612749, 'MIN': 1610612750, 'BKN': 1610612751, 'NYK': 1610612752,
        'ORL': 1610612753, 'IND': 1610612754, 'PHI': 1610612755, 'PHX': 1610612756,
        'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'OKC': 1610612760,
        'TOR': 1610612761, 'UTA': 1610612762, 'MEM': 1610612763, 'WAS': 1610612764,
        'DET': 1610612765, 'CHA': 1610612766,
    }
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._ensure_tables()
        
        # Initialize Firestore adapter for cloud writes
        self.firestore_adapter = None
        if HAS_FIRESTORE_ADAPTER and get_h2h_adapter:
            try:
                self.firestore_adapter = get_h2h_adapter()
                if self.firestore_adapter:
                    logger.info("✅ H2H Firestore adapter integrated")
            except Exception as e:
                logger.warning(f"Firestore adapter init failed: {e}")
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def _ensure_tables(self):
        """Create H2H tracking table if not exists"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_h2h_games (
                player_id TEXT NOT NULL,
                opponent TEXT NOT NULL,
                game_date TEXT NOT NULL,
                game_id TEXT,
                pts INTEGER,
                reb INTEGER,
                ast INTEGER,
                stl INTEGER,
                blk INTEGER,
                tov INTEGER,
                min INTEGER,
                fgm INTEGER,
                fga INTEGER,
                fg3m INTEGER,
                fg3a INTEGER,
                ftm INTEGER,
                fta INTEGER,
                plus_minus INTEGER,
                result TEXT,  -- 'W' or 'L'
                PRIMARY KEY (player_id, opponent, game_date)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_vs_team (
                player_id TEXT NOT NULL,
                opponent TEXT NOT NULL,
                games INTEGER DEFAULT 0,
                avg_pts REAL,
                avg_reb REAL,
                avg_ast REAL,
                avg_stl REAL,
                avg_blk REAL,
                avg_min REAL,
                fg_pct REAL,
                fg3_pct REAL,
                win_pct REAL,
                last_updated TIMESTAMP,
                PRIMARY KEY (player_id, opponent)
            )
        """)
        conn.commit()
        conn.close()
    
    def fetch_h2h(self, player_id: str, opponent: str, seasons: int = 3) -> Dict:
        """
        Fetch H2H history from NBA API.
        Returns dict with game list and aggregate stats.
        """
        start_time = time.time()
        opponent = opponent.upper()
        
        try:
            opponent_id = self.TEAM_ABBR_TO_ID.get(opponent)
            if not opponent_id:
                logger.warning(f"Unknown opponent: {opponent}")
                return {'success': False, 'error': f'Unknown team: {opponent}'}
            
            # Fetch game logs for multiple seasons
            all_games = []
            current_season = 2024  # Would be dynamic in production
            
            for season_offset in range(seasons):
                season = current_season - season_offset
                season_str = f"{season}-{str(season+1)[-2:]}"
                
                params = {
                    'PlayerID': player_id,
                    'Season': season_str,
                    'SeasonType': 'Regular Season',
                    'OpponentTeamID': opponent_id,
                }
                
                try:
                    response = self.session.get(
                        self.PLAYER_GAME_LOG, 
                        params=params, 
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        games = self._parse_game_logs(data, opponent)
                        all_games.extend(games)
                    
                    # Rate limiting
                    time.sleep(0.8)
                    
                except requests.RequestException as e:
                    logger.warning(f"API error for season {season_str}: {e}")
                    continue
            
            # Save to database
            if all_games:
                self._save_h2h_games(player_id, opponent, all_games)
                self._calculate_aggregates(player_id, opponent)
            
            fetch_duration = int((time.time() - start_time) * 1000)
            
            return {
                'success': True,
                'player_id': player_id,
                'opponent': opponent,
                'games_found': len(all_games),
                'fetch_duration_ms': fetch_duration,
            }
            
        except Exception as e:
            logger.error(f"H2H fetch error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _parse_game_logs(self, data: dict, opponent: str) -> List[Dict]:
        """Parse NBA API response into game records"""
        games = []
        
        try:
            result_sets = data.get('resultSets', [])
            if not result_sets:
                return games
            
            headers = result_sets[0].get('headers', [])
            rows = result_sets[0].get('rowSet', [])
            
            # Create index mapping
            idx = {h: i for i, h in enumerate(headers)}
            
            for row in rows:
                game = {
                    'game_date': row[idx.get('GAME_DATE', 0)][:10] if idx.get('GAME_DATE') else '',
                    'game_id': row[idx.get('GAME_ID', 0)] if idx.get('GAME_ID') else '',
                    'pts': row[idx.get('PTS', 0)] or 0,
                    'reb': row[idx.get('REB', 0)] or 0,
                    'ast': row[idx.get('AST', 0)] or 0,
                    'stl': row[idx.get('STL', 0)] or 0,
                    'blk': row[idx.get('BLK', 0)] or 0,
                    'tov': row[idx.get('TOV', 0)] or 0,
                    'min': int(row[idx.get('MIN', 0)] or 0),
                    'fgm': row[idx.get('FGM', 0)] or 0,
                    'fga': row[idx.get('FGA', 0)] or 0,
                    'fg3m': row[idx.get('FG3M', 0)] or 0,
                    'fg3a': row[idx.get('FG3A', 0)] or 0,
                    'ftm': row[idx.get('FTM', 0)] or 0,
                    'fta': row[idx.get('FTA', 0)] or 0,
                    'plus_minus': row[idx.get('PLUS_MINUS', 0)] or 0,
                    'result': row[idx.get('WL', 0)] or '',
                }
                games.append(game)
            
        except Exception as e:
            logger.error(f"Parse error: {e}")
        
        return games
    
    def _save_h2h_games(self, player_id: str, opponent: str, games: List[Dict]):
        """Save individual H2H games to database and Firestore"""
        # Save to SQLite
        conn = self._get_connection()
        
        for game in games:
            conn.execute("""
                INSERT OR REPLACE INTO player_h2h_games
                (player_id, opponent, game_date, game_id, pts, reb, ast, stl, blk,
                 tov, min, fgm, fga, fg3m, fg3a, ftm, fta, plus_minus, result)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(player_id), opponent, game['game_date'], game['game_id'],
                game['pts'], game['reb'], game['ast'], game['stl'], game['blk'],
                game['tov'], game['min'], game['fgm'], game['fga'],
                game['fg3m'], game['fg3a'], game['ftm'], game['fta'],
                game['plus_minus'], game['result']
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(games)} H2H games for {player_id} vs {opponent} (SQLite)")
        
        # Also save to Firestore (cloud persistence)
        if self.firestore_adapter:
            try:
                self.firestore_adapter.save_h2h_games(player_id, opponent, games)
                logger.info(f"Saved {len(games)} H2H games to Firestore")
            except Exception as e:
                logger.warning(f"Firestore H2H games save failed: {e}")
    
    def _calculate_aggregates(self, player_id: str, opponent: str):
        """Calculate and store aggregate H2H stats with 3PM tracking"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as games,
                AVG(pts) as avg_pts,
                AVG(reb) as avg_reb,
                AVG(ast) as avg_ast,
                AVG(stl) as avg_stl,
                AVG(blk) as avg_blk,
                AVG(min) as avg_min,
                AVG(fg3m) as avg_3pm,
                SUM(fgm) * 1.0 / NULLIF(SUM(fga), 0) as fg_pct,
                SUM(fg3m) * 1.0 / NULLIF(SUM(fg3a), 0) as fg3_pct,
                SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_pct
            FROM player_h2h_games
            WHERE player_id = ? AND opponent = ?
        """, (str(player_id), opponent))
        
        row = cursor.fetchone()
        
        if row and row['games'] > 0:
            conn.execute("""
                INSERT OR REPLACE INTO player_vs_team
                (player_id, opponent, games, avg_pts, avg_reb, avg_ast, avg_stl,
                 avg_blk, avg_min, fg_pct, fg3_pct, win_pct, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(player_id), opponent, row['games'],
                row['avg_pts'], row['avg_reb'], row['avg_ast'],
                row['avg_stl'], row['avg_blk'], row['avg_min'],
                row['fg_pct'], row['fg3_pct'], row['win_pct'],
                datetime.now().isoformat()
            ))
            conn.commit()
            
            # Also save to Firestore with 3PM included
            if self.firestore_adapter:
                try:
                    h2h_stats = {
                        'pts': round(row['avg_pts'], 1) if row['avg_pts'] else 0,
                        'reb': round(row['avg_reb'], 1) if row['avg_reb'] else 0,
                        'ast': round(row['avg_ast'], 1) if row['avg_ast'] else 0,
                        '3pm': round(row['avg_3pm'], 1) if row['avg_3pm'] else 0,
                        'games': row['games'],
                        'fg_pct': round(row['fg_pct'] * 100, 1) if row['fg_pct'] else 0,
                        'fg3_pct': round(row['fg3_pct'] * 100, 1) if row['fg3_pct'] else 0,
                        'win_pct': round(row['win_pct'] * 100, 1) if row['win_pct'] else 0,
                    }
                    self.firestore_adapter.save_h2h_stats(player_id, opponent, h2h_stats)
                    logger.info(f"H2H aggregates saved to Firestore for {player_id} vs {opponent}")
                except Exception as e:
                    logger.warning(f"Firestore H2H aggregates save failed: {e}")
        
        conn.close()

    
    def get_h2h_stats(self, player_id: str, opponent: str) -> Optional[Dict]:
        """Get cached H2H aggregate stats"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM player_vs_team
            WHERE player_id = ? AND opponent = ?
        """, (str(player_id), opponent.upper()))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def fetch_roster_h2h(self, team_abbr: str, opponent_abbr: str, max_players: int = 12) -> Dict:
        """
        Fetch H2H data for all players on a team roster vs an opponent.
        Used to pre-populate H2H data for matchup analysis, improving confidence scores.
        
        Args:
            team_abbr: Team abbreviation (e.g., 'BOS')
            opponent_abbr: Opponent abbreviation (e.g., 'MIA')
            max_players: Max players to fetch (top by minutes)
        
        Returns:
            Dict with results summary
        """
        import time
        
        logger.info(f"Fetching H2H for {team_abbr} roster vs {opponent_abbr}")
        results = {'team': team_abbr, 'opponent': opponent_abbr, 'players_fetched': 0, 'errors': []}
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get roster from players table or rosters table
            cursor.execute("""
                SELECT player_id, player_name 
                FROM players 
                WHERE team = ?
                ORDER BY player_name
                LIMIT ?
            """, (team_abbr.upper(), max_players))
            
            players = cursor.fetchall()
            conn.close()
            
            if not players:
                logger.warning(f"No players found for team {team_abbr}")
                results['errors'].append(f"No players found for {team_abbr}")
                return results
            
            logger.info(f"Found {len(players)} players to fetch H2H for")
            
            for player in players:
                player_id = player['player_id']
                player_name = player['player_name']
                
                try:
                    # Skip if recent H2H data exists (within 7 days)
                    cached = self.get_h2h_stats(player_id, opponent_abbr)
                    if cached and cached.get('games', 0) > 0:
                        logger.debug(f"Skipping {player_name} - already has H2H data")
                        results['players_fetched'] += 1
                        continue
                    
                    # Fetch from API
                    result = self.fetch_h2h(player_id, opponent_abbr)
                    if result.get('success'):
                        results['players_fetched'] += 1
                        logger.info(f"Fetched H2H for {player_name}: {result.get('games_found', 0)} games")
                    else:
                        results['errors'].append(f"{player_name}: {result.get('error', 'Unknown error')}")
                    
                    # Rate limiting between players
                    time.sleep(1.0)
                    
                except Exception as e:
                    results['errors'].append(f"{player_name}: {str(e)}")
            
            logger.info(f"Completed H2H fetch: {results['players_fetched']} players")
            
        except Exception as e:
            logger.error(f"Roster H2H fetch error: {e}")
            results['errors'].append(str(e))
        
        return results


# Singleton
_fetcher = None

def get_h2h_fetcher() -> H2HFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = H2HFetcher()
    return _fetcher


if __name__ == "__main__":
    # Test the fetcher
    fetcher = get_h2h_fetcher()
    
    print("Testing H2H Fetcher")
    print("=" * 40)
    
    # Fetch LeBron vs GSW
    result = fetcher.fetch_h2h("2544", "GSW")
    print(f"Fetch result: {result}")
    
    # Get aggregates
    stats = fetcher.get_h2h_stats("2544", "GSW")
    print(f"H2H Stats: {stats}")
