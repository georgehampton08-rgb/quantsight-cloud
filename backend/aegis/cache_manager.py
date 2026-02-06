"""
Cache Manager - Interface for local data storage
Provides uniform interface to SQLite database for caching
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages local cache storage using SQLite.
    Provides async-compatible interface for the Aegis router.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize cache manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_cache_table()
        logger.info(f"CacheManager initialized with {db_path}")
    
    def _ensure_cache_table(self):
        """Create cache table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aegis_cache (
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                data JSON NOT NULL,
                last_sync TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (entity_type, entity_id)
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_sync 
            ON aegis_cache(last_sync)
        """)
        
        conn.commit()
        conn.close()
    
    async def get(self, entity_type: str, entity_id: int) -> Optional[dict]:
        """
        Retrieve cached data.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            dict with 'data' and 'last_sync', or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT data, last_sync
            FROM aegis_cache
            WHERE entity_type = ? AND entity_id = ?
        """, (entity_type, entity_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        data_json, last_sync = result
        
        return {
            'data': json.loads(data_json) if isinstance(data_json, str) else data_json,
            'last_sync': last_sync
        }
    
    async def set(self, entity_type: str, entity_id: int, 
                  data: dict, timestamp: datetime = None):
        """
        Store data in cache.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            data: Data to cache
            timestamp: Optional timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO aegis_cache 
            (entity_type, entity_id, data, last_sync)
            VALUES (?, ?, ?, ?)
        """, (
            entity_type,
            entity_id,
            json.dumps(data),
            timestamp.isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Cached {entity_type}:{entity_id}")
    
    def delete(self, entity_type: str, entity_id: int):
        """Delete cached entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM aegis_cache
            WHERE entity_type = ? AND entity_id = ?
        """, (entity_type, entity_id))
        
        conn.commit()
        conn.close()
    
    def clear_stale(self, max_age_days: int = 30):
        """
        Clear cache entries older than specified days.
        
        Args:
            max_age_days: Maximum age in days to keep
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM aegis_cache
            WHERE last_sync < ?
        """, (cutoff.isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleared {deleted} stale cache entries")
        return deleted
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM aegis_cache")
        total_entries = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT entity_type, COUNT(*) as count
            FROM aegis_cache
            GROUP BY entity_type
        """)
        
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_entries': total_entries,
            'by_type': by_type
        }
