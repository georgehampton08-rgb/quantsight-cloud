"""
Freshness Tracker
Tracks data staleness and determines when to trigger re-fetches.
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# Default TTLs in hours
DEFAULT_TTLS = {
    'h2h': 24,           # Head-to-head data refreshed daily
    'season': 12,        # Season stats refreshed twice daily
    'archetype': 48,     # Archetypes updated every 2 days
    'game_log': 6,       # Game logs refreshed every 6 hours
}


class FreshnessTracker:
    """
    Tracks when data was last fetched and determines staleness.
    Uses SQLite for persistence, designed for easy PostgreSQL migration.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._ensure_table()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def _ensure_table(self):
        """Create freshness tracking table if not exists"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_freshness (
                player_id TEXT NOT NULL,
                data_type TEXT NOT NULL,
                opponent TEXT DEFAULT '',
                last_updated TIMESTAMP,
                ttl_hours INTEGER DEFAULT 24,
                fetch_count INTEGER DEFAULT 0,
                last_fetch_duration_ms INTEGER,
                PRIMARY KEY (player_id, data_type, opponent)
            )
        """)
        conn.commit()
        conn.close()
    
    def is_stale(self, player_id: str, data_type: str, opponent: str = '') -> bool:
        """
        Check if data needs refreshing.
        Returns True if data is stale or doesn't exist.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT last_updated, ttl_hours
            FROM data_freshness
            WHERE player_id = ? AND data_type = ? AND opponent = ?
        """, (str(player_id), data_type, opponent))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row['last_updated']:
            return True  # No data, definitely stale
        
        last_updated = datetime.fromisoformat(row['last_updated'])
        ttl = timedelta(hours=row['ttl_hours'] or DEFAULT_TTLS.get(data_type, 24))
        
        return datetime.now() > last_updated + ttl
    
    def mark_fresh(self, player_id: str, data_type: str, opponent: str = '',
                   fetch_duration_ms: Optional[int] = None):
        """Mark data as freshly fetched"""
        conn = self._get_connection()
        
        ttl = DEFAULT_TTLS.get(data_type, 24)
        
        conn.execute("""
            INSERT INTO data_freshness (player_id, data_type, opponent, last_updated, 
                                        ttl_hours, fetch_count, last_fetch_duration_ms)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(player_id, data_type, opponent) DO UPDATE SET
                last_updated = excluded.last_updated,
                fetch_count = fetch_count + 1,
                last_fetch_duration_ms = excluded.last_fetch_duration_ms
        """, (str(player_id), data_type, opponent, datetime.now().isoformat(),
              ttl, fetch_duration_ms))
        
        conn.commit()
        conn.close()
    
    def get_freshness_info(self, player_id: str, data_type: str, 
                           opponent: str = '') -> Optional[Dict]:
        """Get detailed freshness info for debugging/UI"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT last_updated, ttl_hours, fetch_count, last_fetch_duration_ms
            FROM data_freshness
            WHERE player_id = ? AND data_type = ? AND opponent = ?
        """, (str(player_id), data_type, opponent))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        last_updated = datetime.fromisoformat(row['last_updated']) if row['last_updated'] else None
        ttl = row['ttl_hours'] or DEFAULT_TTLS.get(data_type, 24)
        
        if last_updated:
            expires_at = last_updated + timedelta(hours=ttl)
            time_remaining = expires_at - datetime.now()
            is_stale = time_remaining.total_seconds() < 0
        else:
            expires_at = None
            time_remaining = None
            is_stale = True
        
        return {
            'player_id': player_id,
            'data_type': data_type,
            'opponent': opponent,
            'last_updated': last_updated.isoformat() if last_updated else None,
            'ttl_hours': ttl,
            'expires_at': expires_at.isoformat() if expires_at else None,
            'is_stale': is_stale,
            'time_remaining_hours': time_remaining.total_seconds() / 3600 if time_remaining else None,
            'fetch_count': row['fetch_count'],
            'last_fetch_ms': row['last_fetch_duration_ms'],
        }
    
    def get_stale_players(self, data_type: str, limit: int = 50) -> list:
        """Get list of players with stale data for batch refresh"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Find entries that are past their TTL
        cursor.execute("""
            SELECT player_id, opponent, last_updated, ttl_hours
            FROM data_freshness
            WHERE data_type = ?
            AND datetime(last_updated, '+' || ttl_hours || ' hours') < datetime('now')
            ORDER BY last_updated ASC
            LIMIT ?
        """, (data_type, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{'player_id': r['player_id'], 'opponent': r['opponent']} for r in rows]
    
    def set_ttl(self, player_id: str, data_type: str, ttl_hours: int, opponent: str = ''):
        """Override TTL for specific player/data type"""
        conn = self._get_connection()
        
        conn.execute("""
            UPDATE data_freshness
            SET ttl_hours = ?
            WHERE player_id = ? AND data_type = ? AND opponent = ?
        """, (ttl_hours, str(player_id), data_type, opponent))
        
        conn.commit()
        conn.close()


# Singleton instance
_tracker = None

def get_freshness_tracker() -> FreshnessTracker:
    global _tracker
    if _tracker is None:
        _tracker = FreshnessTracker()
    return _tracker


if __name__ == "__main__":
    # Test the tracker
    tracker = get_freshness_tracker()
    
    print("Testing Freshness Tracker")
    print("=" * 40)
    
    # Test staleness check
    is_stale = tracker.is_stale("2544", "h2h", "GSW")
    print(f"LeBron H2H vs GSW stale: {is_stale}")
    
    # Mark as fresh
    tracker.mark_fresh("2544", "h2h", "GSW", fetch_duration_ms=1500)
    
    # Check again
    is_stale = tracker.is_stale("2544", "h2h", "GSW")
    print(f"After marking fresh: {is_stale}")
    
    # Get info
    info = tracker.get_freshness_info("2544", "h2h", "GSW")
    print(f"Freshness info: {info}")
