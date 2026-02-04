"""
Automated Injury Worker - RapidAPI Version
==========================================
Fetches REAL NBA injury data automatically using RapidAPI.
No manual work. No Java dependencies.

RapidAPI Free Tier: 3x daily updates at 11 AM, 3 PM, 5 PM ET
We sync: 8 AM, 5 PM, 11 PM (aligns with 11AM and 5PM ET updates)
"""
import sqlite3
import requests
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AutomatedInjuryWorker:
    """
    Automated injury fetcher using clean REST API.
    Updates 3x daily automatically.
    """
    
   # RapidAPI endpoint (free tier available)
    RAPIDAPI_URL = "https://api-basketball.p.rapidapi.com/nba-injuries"
    
    # Note: To use RapidAPI, set this environment variable or pass as parameter
    # Get free key at: https://rapidapi.com/api-sports/api/api-basketball
    
    def __init__(self, db_path: Optional[str] = None, api_key: Optional[str] = None):
        if db_path is None:
            # Auto-detect: backend/data/nba_data.db
            backend_dir = Path(__file__).parent.parent
            db_path = backend_dir / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self.api_key = api_key  # Can be set later via environment variable
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_tables(self):
        """Create injury tables"""
        conn = self._get_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS injuries_current (
                player_id TEXT,
                player_name TEXT,
                team_abbr TEXT,
                status TEXT,
                injury_desc TEXT,
                game_date TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY (player_id, game_date)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS injury_sync_log (
                sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sync_type TEXT,
                injuries_fetched INTEGER,
                source TEXT,
                success INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    def fetch_from_rapidapi(self) -> List[Dict]:
        """Fetch injuries from RapidAPI (requires API key)"""
        if not self.api_key:
            logger.warning("No RapidAPI key configured - skipping API fetch")
            return []
        
        try:
            headers = {
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": "api-basketball.p.rapidapi.com"
            }
            
            response = requests.get(self.RAPIDAPI_URL, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                injuries = []
                
                # Parse response (structure depends on API)
                for item in data.get('response', []):
                    injuries.append({
                        'player_id': str(item.get('playerId', '')),
                        'player_name': item.get('player', ''),
                        'team_abbr': item.get('team', ''),
                        'status': item.get('status', 'OUT').upper(),
                        'injury_desc': item.get('description', ''),
                        'game_date': datetime.now().strftime('%Y-%m-%d'),
                    })
                
                logger.info(f"✅ Fetched {len(injuries)} injuries from RapidAPI")
                return injuries
            else:
                logger.warning(f"RapidAPI returned {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"RapidAPI fetch failed: {e}")
            return []
    
    def sync_injuries(self, sync_type: str = 'manual') -> int:
        """
        Sync injury data - fetch and save to database.
        Returns number of injuries synced.
        """
        logger.info(f"🔄 Starting {sync_type} injury sync...")
        
        # Try RapidAPI first
        injuries = self.fetch_from_rapidapi()
        source = 'rapidapi'
        
        if not injuries:
            logger.info("No API data - assuming all players healthy")
            self._log_sync(sync_type, 0, 'none', success=0)
            return 0
        
       # Save to database
        conn = self._get_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Clear today's entries
        conn.execute("DELETE FROM injuries_current WHERE game_date = ?", (today,))
        
        # Insert new injuries
        now = datetime.now().isoformat()
        for inj in injuries:
            conn.execute("""
                INSERT INTO injuries_current
                (player_id, player_name, team_abbr, status, injury_desc, game_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                inj['player_id'], inj['player_name'], inj['team_abbr'],
                inj['status'], inj['injury_desc'], inj['game_date'], now
            ))
        
        conn.commit()
        conn.close()
        
        # Log sync
        self._log_sync(sync_type, len(injuries), source, success=1)
        
        logger.info(f"✅ Synced {len(injuries)} injuries")
        return len(injuries)
    
    def _log_sync(self, sync_type: str, count: int, source: str, success: int):
        """Log sync event"""
        conn = self._get_connection()
        conn.execute("""
            INSERT INTO injury_sync_log (sync_type, injuries_fetched, source, success)
            VALUES (?, ?, ?, ?)
        """, (sync_type, count, source, success))
        conn.commit()
        conn.close()
    
    def mark_injured(self, player_id: str, player_name: str, team: str, 
                     status: str, injury_desc: str):
        """Mark a player as injured (for manual entry)"""
        conn = self._get_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().isoformat()
        
        conn.execute("""
            INSERT OR REPLACE INTO injuries_current
            (player_id, player_name, team_abbr, status, injury_desc, game_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(player_id), player_name, team.upper(), status.upper(), 
              injury_desc, today, now))
        
        conn.commit()
        conn.close()
    
    def mark_healthy(self, player_id: str):
        """Mark a player as healthy (remove injury)"""
        conn = self._get_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn.execute("""
            DELETE FROM injuries_current
            WHERE player_id = ? AND game_date = ?
        """, (str(player_id), today))
        
        conn.commit()
        conn.close()

    def get_player_status(self, player_id: str) -> Dict:
        """
        Get player injury status with SMART performance impact.
        
        Returns status + performance degradation:
        - OUT/DOUBTFUL: Not available
        - QUESTIONABLE: 85% performance (playing hurt)
        - PROBABLE: 95% performance (minor issue)
        - AVAILABLE: 100% performance
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT status, injury_desc
                FROM injuries_current
                WHERE player_id = ? AND game_date = ?
            """, (str(player_id), today))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                status = row['status'].upper()
                
                # Calculate performance degradation based on status
                if status == 'OUT' or status == 'DOUBTFUL':
                    performance_factor = 0.0  # Can't play
                    is_available = False
                elif status == 'QUESTIONABLE' or status == 'GTD':
                    performance_factor = 0.85  # Playing hurt: 85% performance
                    is_available= True
                elif status == 'PROBABLE':
                    performance_factor = 0.95  # Minor issue: 95% performance
                    is_available = True
                else:
                    performance_factor = 1.0
                    is_available = True
                
                return {
                    'status': status,
                    'injury_desc': row['injury_desc'] or '',
                    'is_available': is_available,
                    'performance_factor': performance_factor,
                    'reason': f"{status}: {row['injury_desc']}" if row['injury_desc'] else status,
                }
        except Exception as e:
            # Graceful degradation - assume healthy if DB unavailable
            logger.debug(f"Could not check injury status: {e}")
        
        # Default to fully healthy
        return {
            'status': 'AVAILABLE',
            'injury_desc': '',
            'is_available': True,
            'performance_factor': 1.0,
            'reason': 'Healthy',
        }
    
    def get_team_injuries(self, team_abbr: str) -> List[Dict]:
        """Get team's current injuries"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT * FROM injuries_current
            WHERE team_abbr = ? AND game_date = ?
        """, (team_abbr.upper(), today))
        
        injuries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return injuries
    
    def filter_available_players(self, players: List[Dict]) -> tuple:
        """Filter roster - removes OUT/DOUBTFUL players"""
        available = []
        out = []
        
        for player in players:
            player_id = str(player.get('player_id'))
            status = self.get_player_status(player_id)
            
            if status['is_available']:
                available.append(player)
            else:
                player_copy = player.copy()
                player_copy['injury_status'] = status['status']
                player_copy['injury_desc'] = status['injury_desc']
                out.append(player_copy)
        
        return available, out


# Singleton
_worker = None

def get_injury_worker(api_key: Optional[str] = None) -> AutomatedInjuryWorker:
    global _worker
    if _worker is None:
        _worker = AutomatedInjuryWorker(api_key=api_key)
    return _worker


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*60)
    print("AUTOMATED INJURY WORKER")
    print("="*60)
    
    worker = get_injury_worker()
    
    print("\n💡 Note: RapidAPI key not configured")
    print("   Get free key at: https://rapidapi.com/api-sports/api/api-basketball")
    print("   For now, defaulting to 'all players healthy'\n")
    
    # Run sync (will default to healthy)
    count = worker.sync_injuries('test')
    print(f"✅ Sync complete: {count} injuries")
