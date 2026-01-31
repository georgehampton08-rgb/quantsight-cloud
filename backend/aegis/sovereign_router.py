"""
Aegis Sovereign Router v3.1
===========================
Centralized data traffic controller with Freshness Gate.

Every request passes through SHA-256 verification and 24hr staleness checks
before routing to appropriate data sources.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class FreshnessStatus(str, Enum):
    """Data freshness classification tiers"""
    FRESH = "fresh"      # < 6 hours old, hash valid
    WARM = "warm"        # 6-12 hours old
    STALE = "stale"      # 12-24 hours old
    EXPIRED = "expired"  # > 24 hours old
    CORRUPTED = "corrupted"  # Hash mismatch or schema failure


@dataclass
class FreshnessResult:
    """Result of freshness gate verification"""
    status: FreshnessStatus
    hours_since_sync: float
    hash_valid: bool
    file_path: Optional[str]
    last_sync: Optional[datetime]
    
    @property
    def needs_sync(self) -> bool:
        return self.status in (FreshnessStatus.STALE, FreshnessStatus.EXPIRED, FreshnessStatus.CORRUPTED)


class FreshnessGate:
    """
    SHA-256 verification + 24hr staleness check.
    All data must pass through this gate before processing.
    """
    
    FRESHNESS_THRESHOLDS = {
        FreshnessStatus.FRESH: 6,     # < 6 hours
        FreshnessStatus.WARM: 12,     # 6-12 hours
        FreshnessStatus.STALE: 24,    # 12-24 hours
        FreshnessStatus.EXPIRED: float('inf')  # > 24 hours
    }
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._hash_cache: Dict[str, str] = {}
        self._sync_times: Dict[str, datetime] = {}
    
    def verify(self, player_id: str) -> FreshnessResult:
        """
        Verify data freshness for a player.
        
        Returns:
            FreshnessResult with status, timing, and hash validity
        """
        file_path = self._get_player_file(player_id)
        
        if not file_path.exists():
            return FreshnessResult(
                status=FreshnessStatus.EXPIRED,
                hours_since_sync=float('inf'),
                hash_valid=False,
                file_path=None,
                last_sync=None
            )
        
        # Check hash integrity
        current_hash = self._compute_hash(file_path)
        cached_hash = self._hash_cache.get(player_id)
        hash_valid = cached_hash is None or current_hash == cached_hash
        
        if not hash_valid:
            logger.warning(f"Hash mismatch for player {player_id}")
            return FreshnessResult(
                status=FreshnessStatus.CORRUPTED,
                hours_since_sync=0,
                hash_valid=False,
                file_path=str(file_path),
                last_sync=self._sync_times.get(player_id)
            )
        
        # Check staleness
        last_sync = self._get_last_sync_time(player_id, file_path)
        hours_since = (datetime.now() - last_sync).total_seconds() / 3600
        
        status = self._classify_freshness(hours_since)
        
        # Update cache
        self._hash_cache[player_id] = current_hash
        
        return FreshnessResult(
            status=status,
            hours_since_sync=round(hours_since, 2),
            hash_valid=True,
            file_path=str(file_path),
            last_sync=last_sync
        )
    
    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file contents"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _classify_freshness(self, hours: float) -> FreshnessStatus:
        """Classify hours into freshness tier"""
        if hours < self.FRESHNESS_THRESHOLDS[FreshnessStatus.FRESH]:
            return FreshnessStatus.FRESH
        elif hours < self.FRESHNESS_THRESHOLDS[FreshnessStatus.WARM]:
            return FreshnessStatus.WARM
        elif hours < self.FRESHNESS_THRESHOLDS[FreshnessStatus.STALE]:
            return FreshnessStatus.STALE
        else:
            return FreshnessStatus.EXPIRED
    
    def _get_player_file(self, player_id: str) -> Path:
        """Get path to player's data file"""
        return self.data_dir / "players" / f"{player_id}_games.csv"
    
    def _get_last_sync_time(self, player_id: str, file_path: Path) -> datetime:
        """Get last sync time from cache or file mtime"""
        if player_id in self._sync_times:
            return self._sync_times[player_id]
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    
    def mark_synced(self, player_id: str, file_path: Path):
        """Mark a file as freshly synced"""
        self._sync_times[player_id] = datetime.now()
        self._hash_cache[player_id] = self._compute_hash(file_path)


class SovereignRouter:
    """
    Centralized data traffic controller.
    
    All requests pass through Freshness Gate before routing.
    Automatically triggers Delta-Sync or Healer based on status.
    """
    
    def __init__(
        self,
        data_dir: Path,
        delta_sync: Optional[Any] = None,
        healer: Optional[Any] = None
    ):
        self.data_dir = data_dir
        self.freshness_gate = FreshnessGate(data_dir)
        self.delta_sync = delta_sync
        self.healer = healer
        
        # Request metrics
        self._metrics = {
            'requests': 0,
            'cache_hits': 0,
            'syncs_triggered': 0,
            'heals_triggered': 0
        }
    
    async def route_request(self, player_id: str, force_fresh: bool = False) -> Dict[str, Any]:
        """
        Route a data request through the Freshness Gate.
        
        Args:
            player_id: NBA player ID
            force_fresh: Force re-sync even if data is fresh
            
        Returns:
            Dict with data, freshness info, and source
        """
        self._metrics['requests'] += 1
        
        # Pass through Freshness Gate
        freshness = self.freshness_gate.verify(player_id)
        
        # Handle based on status
        if freshness.status == FreshnessStatus.CORRUPTED:
            logger.warning(f"Corrupted data for {player_id}, triggering healer")
            self._metrics['heals_triggered'] += 1
            if self.healer:
                asyncio.create_task(self.healer.isolate_and_resync(player_id))
            # Return last known good data while healing
            return await self._fetch_fallback(player_id, freshness)
        
        if freshness.needs_sync or force_fresh:
            logger.info(f"Data stale for {player_id}, triggering delta-sync")
            self._metrics['syncs_triggered'] += 1
            if self.delta_sync:
                # IF force_fresh OR first time (expired/no file), we MUST await
                # otherwise we return empty data
                should_await = force_fresh or freshness.status == FreshnessStatus.EXPIRED
                
                if should_await:
                    await self.delta_sync.sync_player(player_id)
                else:
                    # Non-blocking sync for merely stale data (warm->stale transition)
                    asyncio.create_task(self.delta_sync.sync_player(player_id))
        
        if freshness.status in (FreshnessStatus.FRESH, FreshnessStatus.WARM):
            self._metrics['cache_hits'] += 1
        
        # Fetch and return data
        data = await self._fetch_data(player_id)
        
        return {
            'data': data,
            'freshness': {
                'status': freshness.status.value,
                'hours_since_sync': freshness.hours_since_sync,
                'last_sync': freshness.last_sync.isoformat() if freshness.last_sync else None
            },
            'source': 'cache' if freshness.status == FreshnessStatus.FRESH else 'stale_cache'
        }
    
    async def _fetch_data(self, player_id: str) -> Dict:
        """
        Fetch player data from database (player_game_logs table).
        
        HYBRID MODE:
        - Cloud Run (K_SERVICE set): Uses SQLAlchemy + pg8000 for Cloud SQL
        - Local/Electron: Uses sqlite3 for local development
        """
        import os
        
        # Cloud Run detection - K_SERVICE is auto-set by Cloud Run
        if os.getenv('K_SERVICE'):
            return await self._fetch_data_cloudsql(player_id)
        else:
            return await self._fetch_data_sqlite(player_id)
    
    async def _fetch_data_cloudsql(self, player_id: str) -> Dict:
        """Fetch from Cloud SQL via SQLAlchemy + pg8000"""
        import os
        from sqlalchemy import create_engine, text
        
        # Cloud SQL connection string format:
        # postgresql+pg8000://user:pass@/dbname?unix_sock=/cloudsql/PROJECT:REGION:INSTANCE/.s.PGSQL.5432
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            logger.error("DATABASE_URL not set in Cloud Run environment")
            return []
        
        try:
            engine = create_engine(database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT 
                        player_id, game_id, game_date, opponent,
                        points as pts, rebounds as reb, assists as ast,
                        steals as stl, blocks as blk, turnovers as tov,
                        fg_made as fgm, fg_attempted as fga,
                        fg3_made as fg3m, fg3_attempted as fg3a,
                        ft_made as ftm, ft_attempted as fta,
                        minutes as min, plus_minus
                    FROM player_game_logs 
                    WHERE player_id = :player_id
                    ORDER BY game_date DESC
                    LIMIT 15
                """), {"player_id": player_id})
                
                rows = result.fetchall()
                if rows:
                    return [dict(row._mapping) for row in rows]
                return []
        except Exception as e:
            logger.error(f"Cloud SQL error: {e}")
            return []
    
    async def _fetch_data_sqlite(self, player_id: str) -> Dict:
        """Fetch from local SQLite database (original logic)"""
        import sqlite3
        
        db_path = self.data_dir / "nba_data.db"
        if not db_path.exists():
            logger.warning(f"Database not found at {db_path}")
            return {}
        
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query last 15 games from player_game_logs table
            cursor.execute("""
                SELECT 
                    player_id, game_id, game_date, opponent,
                    points as pts, rebounds as reb, assists as ast,
                    steals as stl, blocks as blk, turnovers as tov,
                    fg_made as fgm, fg_attempted as fga,
                    fg3_made as fg3m, fg3_attempted as fg3a,
                    ft_made as ftm, ft_attempted as fta,
                    minutes as min, plus_minus
                FROM player_game_logs 
                WHERE player_id = ?
                ORDER BY game_date DESC
                LIMIT 15
            """, (player_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                return [dict(row) for row in rows]
            return []
        except Exception as e:
            logger.error(f"Error reading player data from DB: {e}")
            return []

    
    async def _fetch_fallback(self, player_id: str, freshness: FreshnessResult) -> Dict:
        """Fetch fallback data while healing in progress"""
        data = await self._fetch_data(player_id)
        return {
            'data': data,
            'freshness': {
                'status': 'healing',
                'hours_since_sync': freshness.hours_since_sync,
                'warning': 'Data may be corrupted, re-sync in progress'
            },
            'source': 'fallback'
        }
    
    def get_metrics(self) -> Dict:
        """Return router performance metrics"""
        total = self._metrics['requests']
        return {
            **self._metrics,
            'cache_hit_rate': self._metrics['cache_hits'] / total if total > 0 else 0
        }
