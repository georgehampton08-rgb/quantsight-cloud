"""
Update Player Stats in player_rolling_averages
===============================================
Fetches 3PM, team, and position from NBA API and updates player_rolling_averages.
"""
import sqlite3
import requests
import logging
from pathlib import Path
from typing import Dict, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Player3PMUpdater:
    """Updates player_rolling_averages with 3PM, team, and position data from NBA API"""
    
    PLAYER_STATS_URL = "https://stats.nba.com/stats/leaguedashplayerstats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Host': 'stats.nba.com',
    }
    
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = Path(__file__).parent / 'data' / 'nba_data.db'
        self.db_path = db_path
    
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_columns(self):
        """Ensure team_abbr and position columns exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(player_rolling_averages)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'team_abbr' not in columns:
            logger.info("Adding team_abbr column")
            cursor.execute("ALTER TABLE player_rolling_averages ADD COLUMN team_abbr TEXT DEFAULT ''")
        if 'position' not in columns:
            logger.info("Adding position column")
            cursor.execute("ALTER TABLE player_rolling_averages ADD COLUMN position TEXT DEFAULT ''")
        
        conn.commit()
        conn.close()
    
    def fetch_stats_from_api(self, season: str = "2024-25") -> Dict[str, Tuple[float, str, str]]:
        """Fetch FG3M, team, position for all players from NBA API"""
        params = {
            'PerMode': 'PerGame', 'Season': season, 'SeasonType': 'Regular Season',
            'LeagueID': '00', 'MeasureType': 'Base', 'Month': '0', 'LastNGames': '0',
            'OpponentTeamID': '0', 'Period': '0', 'PaceAdjust': 'N', 'PlusMinus': 'N',
            'Rank': 'N', 'Conference': '', 'DateFrom': '', 'DateTo': '', 'Division': '',
            'GameScope': '', 'GameSegment': '', 'Height': '', 'Location': '',
            'Outcome': '', 'PORound': '0', 'PlayerExperience': '', 'PlayerPosition': '',
            'SeasonSegment': '', 'ShotClockRange': '', 'StarterBench': '', 'TeamID': '0',
            'VsConference': '', 'VsDivision': '', 'Weight': '',
        }
        
        logger.info(f"Fetching player stats from NBA API for {season}...")
        
        try:
            response = requests.get(self.PLAYER_STATS_URL, headers=self.HEADERS, 
                                    params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            result_sets = data.get('resultSets', [])
            if not result_sets:
                return {}
            
            headers = result_sets[0].get('headers', [])
            rows = result_sets[0].get('rowSet', [])
            
            player_id_idx = headers.index('PLAYER_ID')
            fg3m_idx = headers.index('FG3M')
            team_idx = headers.index('TEAM_ABBREVIATION') if 'TEAM_ABBREVIATION' in headers else None
            
            # Map player_id -> (fg3m, team, position)
            player_data = {}
            for row in rows:
                player_id = str(row[player_id_idx])
                fg3m = round(row[fg3m_idx] or 0, 1)
                team = row[team_idx] if team_idx else ''
                # Position not in this endpoint, we'll get from another source
                player_data[player_id] = (fg3m, team, '')
            
            logger.info(f"Fetched stats for {len(player_data)} players")
            return player_data
            
        except Exception as e:
            logger.error(f"API fetch failed: {e}")
            return {}
    
    def update_database(self, player_data: Dict[str, Tuple[float, str, str]]) -> int:
        """Update player_rolling_averages with 3PM, team, position data"""
        self._ensure_columns()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT player_id, player_name FROM player_rolling_averages")
        existing = cursor.fetchall()
        
        updated = 0
        for row in existing:
            player_id = row['player_id']
            if player_id in player_data:
                fg3m, team, position = player_data[player_id]
                cursor.execute("""
                    UPDATE player_rolling_averages 
                    SET avg_three_pm = ?, team_abbr = ?
                    WHERE player_id = ?
                """, (fg3m, team, player_id))
                updated += 1
        
        conn.commit()
        
        print(f"\n✅ Updated {updated}/{len(existing)} players with 3PM and team data")
        
        # Show sample
        cursor.execute("""
            SELECT player_name, team_abbr, avg_three_pm, avg_points 
            FROM player_rolling_averages 
            WHERE avg_three_pm > 2 AND team_abbr != ''
            ORDER BY avg_three_pm DESC LIMIT 5
        """)
        print("\nTop 3PM shooters with team:")
        for row in cursor.fetchall():
            print(f"  {row['player_name']} ({row['team_abbr']}): {row['avg_three_pm']} 3PM")
        
        conn.close()
        return updated
    
    def run(self):
        """Main entry point"""
        print("=" * 50)
        print("Player Stats Integration (3PM + Team)")
        print("=" * 50)
        
        player_data = self.fetch_stats_from_api()
        if not player_data:
            print("❌ Failed to fetch from NBA API")
            return False
        
        self.update_database(player_data)
        return True


if __name__ == '__main__':
    updater = Player3PMUpdater()
    updater.run()
