"""
Game Log Updater Service
========================
Incrementally fetches new game logs from NBA API and merges with existing data.
Only fetches games AFTER the last logged game for each player.
"""

import csv
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import time

logger = logging.getLogger(__name__)

# NBA API endpoints
NBA_GAME_LOG_URL = "https://stats.nba.com/stats/playergamelog"
NBA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com"
}


class GameLogUpdater:
    """Incremental game log fetcher and merger"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent.parent / "data"
        self.csv_path = self.data_dir / "game_logs.csv"
        self.backup_path = self.data_dir / "game_logs_backup.csv"
        
    def get_player_last_game(self, player_id: str) -> Optional[date]:
        """Get the most recent game date for a player from existing logs"""
        if not self.csv_path.exists():
            return None
            
        last_game = None
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle both uppercase and lowercase column names
                    row_player_id = row.get('PLAYER_ID') or row.get('player_id', '')
                    if str(row_player_id) == str(player_id):
                        date_str = row.get('GAME_DATE') or row.get('game_date', '')
                        if date_str:
                            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d']:
                                try:
                                    gd = datetime.strptime(date_str[:10], fmt).date()
                                    if last_game is None or gd > last_game:
                                        last_game = gd
                                    break
                                except ValueError:
                                    continue
        except Exception as e:
            logger.error(f"Error reading game logs: {e}")
            
        return last_game
    
    def _get_current_season(self) -> str:
        """Get the current NBA season string based on today's date"""
        today = date.today()
        # NBA season typically runs Oct-Apr, so if we're in Oct-Dec, season is YYYY-(YYYY+1)
        # If we're in Jan-June, season is (YYYY-1)-YYYY
        if today.month >= 10:  # Oct-Dec
            return f"{today.year}-{str(today.year + 1)[-2:]}"
        else:  # Jan-Sept
            return f"{today.year - 1}-{str(today.year)[-2:]}"
    
    def fetch_new_games(self, player_id: str, season: str = None) -> Tuple[List[Dict], str]:
        """
        Fetch games from NBA API that are newer than our last logged game.
        
        Returns:
            Tuple of (new_games_list, status_message)
        """
        # Auto-detect current season if not specified
        if season is None:
            season = self._get_current_season()
            
        last_game = self.get_player_last_game(player_id)
        
        try:
            params = {
                "PlayerID": player_id,
                "Season": season,
                "SeasonType": "Regular Season",
                "LeagueID": "00"
            }
            
            logger.info(f"[UPDATER] Fetching game logs for {player_id}, season {season}")
            
            response = requests.get(
                NBA_GAME_LOG_URL,
                headers=NBA_HEADERS,
                params=params,
                timeout=15
            )
            
            if response.status_code != 200:
                return [], f"API returned {response.status_code}"
                
            data = response.json()
            
            # Parse response
            result_sets = data.get('resultSets', [])
            if not result_sets:
                return [], "No result sets in response"
                
            game_log_set = result_sets[0]
            headers = game_log_set.get('headers', [])
            rows = game_log_set.get('rowSet', [])
            
            if not rows:
                return [], "No games found in response"
            
            # Convert to dicts
            new_games = []
            for row in rows:
                game = dict(zip(headers, row))
                
                # Parse game date
                game_date_str = game.get('GAME_DATE', '')
                try:
                    # NBA API returns dates like "JAN 25, 2026"
                    game_date = datetime.strptime(game_date_str, "%b %d, %Y").date()
                except ValueError:
                    try:
                        game_date = datetime.strptime(game_date_str[:10], "%Y-%m-%d").date()
                    except ValueError:
                        continue
                
                # Only include games after our last logged game
                if last_game is None or game_date > last_game:
                    # Normalize date format
                    game['GAME_DATE'] = game_date.strftime('%Y-%m-%d')
                    game['PLAYER_ID'] = str(player_id)
                    new_games.append(game)
            
            if new_games:
                logger.info(f"[UPDATER] Found {len(new_games)} new games for player {player_id}")
                return new_games, f"Found {len(new_games)} new games"
            else:
                return [], f"No new games since {last_game}"
                
        except requests.exceptions.Timeout:
            return [], "API timeout"
        except requests.exceptions.RequestException as e:
            return [], f"API error: {str(e)}"
        except Exception as e:
            logger.error(f"[UPDATER] Fetch failed: {e}")
            return [], f"Error: {str(e)}"
    
    def merge_games(self, new_games: List[Dict]) -> int:
        """
        Append new games to the CSV file.
        Returns count of games added.
        """
        if not new_games:
            return 0
            
        try:
            # Read existing headers from CSV
            existing_headers = []
            if self.csv_path.exists():
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    existing_headers = reader.fieldnames or []
            
            # If no existing file, use headers from new games
            if not existing_headers:
                existing_headers = list(new_games[0].keys())
            
            # Create backup before modifying
            if self.csv_path.exists():
                import shutil
                shutil.copy(self.csv_path, self.backup_path)
            
            # Append new games
            file_exists = self.csv_path.exists()
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=existing_headers, extrasaction='ignore')
                
                if not file_exists:
                    writer.writeheader()
                
                for game in new_games:
                    writer.writerow(game)
            
            logger.info(f"[UPDATER] Added {len(new_games)} games to CSV")
            return len(new_games)
            
        except Exception as e:
            logger.error(f"[UPDATER] Merge failed: {e}")
            # Restore from backup if available
            if self.backup_path.exists():
                import shutil
                shutil.copy(self.backup_path, self.csv_path)
            return 0
    
    def refresh_player(self, player_id: str, season: str = None) -> Dict:
        """
        Full refresh flow for a single player.
        
        Returns:
            Dict with status, games_added, last_game_date, etc.
        """
        start = time.perf_counter()
        
        # Get current state
        old_last_game = self.get_player_last_game(player_id)
        
        # Fetch new games
        new_games, fetch_status = self.fetch_new_games(player_id, season)
        
        # Merge if we have new games
        games_added = 0
        if new_games:
            games_added = self.merge_games(new_games)
        
        # Get updated state
        new_last_game = self.get_player_last_game(player_id)
        
        elapsed = (time.perf_counter() - start) * 1000
        
        # Calculate days rest from today
        today = date.today()
        days_rest = (today - new_last_game).days if new_last_game else None
        
        return {
            "player_id": player_id,
            "status": "success" if games_added > 0 or "No new games" in fetch_status else "warning",
            "message": fetch_status,
            "games_added": games_added,
            "previous_last_game": old_last_game.isoformat() if old_last_game else None,
            "new_last_game": new_last_game.isoformat() if new_last_game else None,
            "days_rest": days_rest,
            "execution_time_ms": round(elapsed, 1)
        }


# Singleton instance
_updater = None

def get_game_log_updater(data_dir: Optional[Path] = None) -> GameLogUpdater:
    """Get or create singleton GameLogUpdater instance"""
    global _updater
    if _updater is None:
        _updater = GameLogUpdater(data_dir)
    return _updater
