"""
Injury Report Manual Manager
============================
Simple, reliable injury tracking with manual updates.
No dependence on flaky APIs.
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class InjuryManager:
    """
    Simple injury tracking - manual updates via database.
    Run sync 3x daily: morning (8AM), pre-game (2hrs before), night (11PM)
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._ensure_table()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_table(self):
        """Create simple injury tracking table"""
        conn = self._get_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS injuries_current (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                team_abbr TEXT,
                status TEXT,  -- OUT, DOUBTFUL, QUESTIONABLE, PROBABLE
                injury_desc TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                return_date TEXT  -- Estimated return date
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS injury_sync_log (
                sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sync_type TEXT,  -- 'morning' | 'pregame' | 'night'
                players_checked INTEGER,
                injuries_found INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    def mark_injured(self, player_id: str, player_name: str, team: str, 
                    status: str, injury_desc: str = "", return_date: str = None):
        """Manually mark a player as injured"""
        conn = self._get_connection()
        
        conn.execute("""
            INSERT OR REPLACE INTO injuries_current
            (player_id, player_name, team_abbr, status, injury_desc, return_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(player_id), player_name, team.upper(), status.upper(), 
              injury_desc, return_date, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✍️ Marked {player_name} as {status}: {injury_desc}")
    
    def mark_healthy(self, player_id: str):
        """Remove player from injury list"""
        conn = self._get_connection()
        conn.execute("DELETE FROM injuries_current WHERE player_id = ?", (str(player_id),))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Cleared injury status for player {player_id}")
    
    def get_player_status(self, player_id: str) -> Dict:
        """Get injury status for a player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, injury_desc, return_date
            FROM injuries_current
            WHERE player_id = ?
        """, (str(player_id),))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            status = row['status'].upper()
            return {
                'status': status,
                'injury_desc': row['injury_desc'] or '',
                'is_available': status not in ('OUT', 'DOUBTFUL'),
                'return_date': row['return_date'],
            }
        
        # No injury record = healthy
        return {
            'status': 'AVAILABLE',
            'injury_desc': '',
            'is_available': True,
            'return_date': None,
        }
    
    def get_team_injuries(self, team_abbr: str) -> List[Dict]:
        """Get all injuries for a team"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM injuries_current
            WHERE team_abbr = ?
            ORDER BY status, player_name
        """, (team_abbr.upper(),))
        
        injuries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return injuries
    
    def get_all_injuries(self) -> List[Dict]:
        """Get all current injuries"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM injuries_current
            ORDER BY team_abbr, status, player_name
        """)
        
        injuries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return injuries
    
    def filter_available_players(self, players: List[Dict]) -> tuple:
        """Filter roster to available players"""
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
    
    def log_sync(self, sync_type: str, players_checked: int, injuries_found: int):
        """Log a sync event"""
        conn = self._get_connection()
        
        conn.execute("""
            INSERT INTO injury_sync_log (sync_type, players_checked, injuries_found)
            VALUES (?, ?, ?)
        """, (sync_type, players_checked, injuries_found))
        
        conn.commit()
        conn.close()
    
    def cleanup_old_injuries(self, days: int = 30):
        """Remove injury records older than X days"""
        conn = self._get_connection()
        
        cutoff = datetime.now() - timedelta(days=days)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM injuries_current
            WHERE updated_at < ?
        """, (cutoff.isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"🧹 Cleaned up {deleted} old injury records")
        
        return deleted


# Singleton
_manager = None

def get_injury_manager() -> InjuryManager:
    global _manager
    if _manager is None:
        _manager = InjuryManager()
    return _manager


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    mgr = get_injury_manager()
    
    print("="*60)
    print("INJURY MANAGER TEST")
    print("="*60)
    
    # Example: Mark LeBron as questionable
    print("\n1. Marking LeBron as QUESTIONABLE...")
    mgr.mark_injured(
        player_id="2544",
        player_name="LeBron James",
        team="LAL",
        status="QUESTIONABLE",
        injury_desc="Left ankle sprain",
        return_date="2026-01-30"
    )
    
    # Check status
    print("\n2. Checking LeBron's status:")
    status = mgr.get_player_status("2544")
    print(f"   Status: {status['status']}")
    print(f"   Available: {status['is_available']}")
    print(f"   Injury: {status['injury_desc']}")
    
    # Get team injuries
    print("\n3. Lakers injury report:")
    lal_injuries = mgr.get_team_injuries("LAL")
    for inj in lal_injuries:
        print(f"   {inj['player_name']}: {inj['status']} - {inj['injury_desc']}")
    
    # Clear him
    print("\n4. Clearing LeBron's injury...")
    mgr.mark_healthy("2544")
    
    status = mgr.get_player_status("2544")
    print(f"   New status: {status['status']}")
