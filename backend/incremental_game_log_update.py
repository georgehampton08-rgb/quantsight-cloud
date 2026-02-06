"""
Incremental Game Log Updater
Fetches only NEW games since last sync for each player.
Designed for daily/periodic updates without re-fetching all data.
"""
import sqlite3
import csv
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from nba_api.stats.endpoints import playergamelog
    from nba_api.stats.static import players
    HAS_NBA_API = True
except ImportError:
    HAS_NBA_API = False
    logger.warning("nba_api not installed")


class IncrementalGameLogUpdater:
    """
    Fetches only new games since last update.
    Appends to game_logs.csv and updates database.
    """
    
    RATE_LIMIT = 1.0  # seconds
    
    def __init__(self, db_path: Optional[str] = None, csv_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent / 'data' / 'nba_data.db'
        if csv_path is None:
            csv_path = Path(__file__).parent / 'data' / 'game_logs.csv'
        
        self.db_path = str(db_path)
        self.csv_path = str(csv_path)
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        return conn
    
    def _ensure_tables(self):
        """Create game log tables"""
        conn = self._get_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_game_logs (
                player_id TEXT NOT NULL,
                game_id TEXT NOT NULL,
                game_date TEXT NOT NULL,
                opponent TEXT,
                home_away TEXT,
                result TEXT,
                mins INTEGER,
                pts INTEGER,
                reb INTEGER,
                ast INTEGER,
                stl INTEGER,
                blk INTEGER,
                tov INTEGER,
                fgm INTEGER,
                fga INTEGER,
                fg3m INTEGER,
                fg3a INTEGER,
                ftm INTEGER,
                fta INTEGER,
                plus_minus INTEGER,
                sync_timestamp TEXT,
                PRIMARY KEY (player_id, game_id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_log_sync (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                last_game_date TEXT,
                last_sync TEXT,
                games_count INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_last_game_date(self, player_id: str) -> Optional[str]:
        """Get the most recent game date for a player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT MAX(game_date) as last_date 
            FROM player_game_logs 
            WHERE player_id = ?
        """, (str(player_id),))
        
        row = cursor.fetchone()
        conn.close()
        
        return row['last_date'] if row and row['last_date'] else None
    
    def fetch_new_games(self, player_id: str, player_name: str = '') -> Dict:
        """
        Fetch only games after the last known game date.
        Returns new games found.
        """
        if not HAS_NBA_API:
            return {'success': False, 'error': 'nba_api not installed'}
        
        last_date = self.get_last_game_date(player_id)
        logger.info(f"Player {player_id}: Last game = {last_date or 'None'}")
        
        try:
            time.sleep(self.RATE_LIMIT)
            
            log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season='2024-25',
                season_type_all_star='Regular Season'
            )
            df = log.get_data_frames()[0]
            
            if df.empty:
                return {'success': True, 'new_games': 0, 'message': 'No games found'}
            
            # Filter to only new games
            if last_date:
                df['GAME_DATE_DT'] = df['GAME_DATE'].apply(
                    lambda x: datetime.strptime(x, '%b %d, %Y').strftime('%Y-%m-%d')
                )
                df = df[df['GAME_DATE_DT'] > last_date]
            
            if df.empty:
                return {
                    'success': True, 
                    'new_games': 0, 
                    'message': f'No new games since {last_date}'
                }
            
            # Parse and save new games
            new_games = []
            for _, row in df.iterrows():
                game_date = datetime.strptime(row['GAME_DATE'], '%b %d, %Y').strftime('%Y-%m-%d')
                
                # Parse matchup (e.g., "LAL vs. GSW" or "LAL @ BOS")
                matchup = row.get('MATCHUP', '')
                if ' vs. ' in matchup:
                    opponent = matchup.split(' vs. ')[1]
                    home_away = 'home'
                elif ' @ ' in matchup:
                    opponent = matchup.split(' @ ')[1]
                    home_away = 'away'
                else:
                    opponent = matchup[-3:]
                    home_away = 'unknown'
                
                game = {
                    'player_id': str(player_id),
                    'player_name': player_name or str(player_id),
                    'game_id': str(row.get('Game_ID', '')),
                    'game_date': game_date,
                    'opponent': opponent,
                    'home_away': home_away,
                    'result': row.get('WL', ''),
                    'mins': int(row.get('MIN', 0) or 0),
                    'pts': int(row.get('PTS', 0) or 0),
                    'reb': int(row.get('REB', 0) or 0),
                    'ast': int(row.get('AST', 0) or 0),
                    'stl': int(row.get('STL', 0) or 0),
                    'blk': int(row.get('BLK', 0) or 0),
                    'tov': int(row.get('TOV', 0) or 0),
                    'fgm': int(row.get('FGM', 0) or 0),
                    'fga': int(row.get('FGA', 0) or 0),
                    'fg3m': int(row.get('FG3M', 0) or 0),
                    'fg3a': int(row.get('FG3A', 0) or 0),
                    'ftm': int(row.get('FTM', 0) or 0),
                    'fta': int(row.get('FTA', 0) or 0),
                    'plus_minus': int(row.get('PLUS_MINUS', 0) or 0),
                }
                new_games.append(game)
            
            # Save to database
            self._save_games(new_games)
            
            # Append to CSV
            self._append_to_csv(new_games)
            
            # Update sync status
            self._update_sync_status(player_id, player_name, new_games)
            
            return {
                'success': True,
                'new_games': len(new_games),
                'latest_date': new_games[0]['game_date'] if new_games else None,
            }
            
        except Exception as e:
            logger.error(f"Fetch error for {player_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _save_games(self, games: List[Dict]):
        """Save games to database"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        
        for game in games:
            conn.execute("""
                INSERT OR REPLACE INTO player_game_logs
                (player_id, game_id, game_date, opponent, home_away, result,
                 mins, pts, reb, ast, stl, blk, tov, fgm, fga, fg3m, fg3a,
                 ftm, fta, plus_minus, sync_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game['player_id'], game['game_id'], game['game_date'],
                game['opponent'], game['home_away'], game['result'],
                game['mins'], game['pts'], game['reb'], game['ast'],
                game['stl'], game['blk'], game['tov'], game['fgm'], game['fga'],
                game['fg3m'], game['fg3a'], game['ftm'], game['fta'],
                game['plus_minus'], now
            ))
        
        conn.commit()
        conn.close()
    
    def _append_to_csv(self, games: List[Dict]):
        """Append new games to CSV file"""
        csv_path = Path(self.csv_path)
        
        # Ensure header exists
        write_header = not csv_path.exists() or csv_path.stat().st_size == 0
        
        fieldnames = [
            'player_id', 'player_name', 'game_date', 'opponent', 
            'points', 'rebounds', 'assists', 'minutes', 'sync_timestamp', 'source'
        ]
        
        with open(csv_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if write_header:
                writer.writeheader()
            
            now = datetime.now().isoformat()
            for game in games:
                writer.writerow({
                    'player_id': game['player_id'],
                    'player_name': game['player_name'],
                    'game_date': game['game_date'],
                    'opponent': game['opponent'],
                    'points': game['pts'],
                    'rebounds': game['reb'],
                    'assists': game['ast'],
                    'minutes': game['mins'],
                    'sync_timestamp': now,
                    'source': 'nba_api_incremental',
                })
    
    def _update_sync_status(self, player_id: str, player_name: str, games: List[Dict]):
        """Update sync tracking"""
        conn = self._get_connection()
        
        latest_date = max(g['game_date'] for g in games) if games else None
        
        conn.execute("""
            INSERT OR REPLACE INTO game_log_sync
            (player_id, player_name, last_game_date, last_sync, games_count)
            VALUES (?, ?, ?, ?, 
                    COALESCE((SELECT games_count FROM game_log_sync WHERE player_id = ?), 0) + ?)
        """, (
            str(player_id), player_name, latest_date, 
            datetime.now().isoformat(), str(player_id), len(games)
        ))
        
        conn.commit()
        conn.close()
    
    def update_active_players(self, player_ids: List[str], player_names: Dict[str, str] = None) -> Dict:
        """
        Update game logs for multiple players (incremental only).
        """
        results = {
            'total_players': len(player_ids),
            'updated': 0,
            'new_games': 0,
            'errors': 0,
        }
        
        for i, pid in enumerate(player_ids):
            name = player_names.get(pid, '') if player_names else ''
            print(f"[{i+1}/{len(player_ids)}] Updating {name or pid}...")
            
            result = self.fetch_new_games(pid, name)
            
            if result.get('success'):
                new_count = result.get('new_games', 0)
                results['new_games'] += new_count
                if new_count > 0:
                    results['updated'] += 1
                    print(f"   ✅ {new_count} new games")
                else:
                    print(f"   ⏭️ Up to date")
            else:
                results['errors'] += 1
                print(f"   ❌ {result.get('error', 'Unknown error')}")
        
        return results


def get_updater() -> IncrementalGameLogUpdater:
    return IncrementalGameLogUpdater()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    updater = get_updater()
    
    # Test with sample players
    test_players = [
        ('2544', 'LeBron James'),
        ('201142', 'Kevin Durant'),
        ('203999', 'Nikola Jokic'),
    ]
    
    print("="*60)
    print("INCREMENTAL GAME LOG UPDATE")
    print("="*60)
    
    for pid, name in test_players:
        print(f"\n{name}:")
        result = updater.fetch_new_games(pid, name)
        print(f"  Result: {result}")
