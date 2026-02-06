"""
Aegis Healer Protocol v3.1
==========================
Self-healing pipeline for corrupted data files.

When a file fails schema validation or hash check, the Healer:
1. Isolates the corrupted file (moves to quarantine)
2. Triggers background re-sync from remote source
3. Returns last-known-good data to prevent session crash
"""

import asyncio
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)


@dataclass
class HealingRecord:
    """Record of a healing operation"""
    player_id: str
    quarantine_path: str
    triggered_at: datetime
    status: str  # 'healing', 'healed', 'failed'
    error: Optional[str] = None


class HealerProtocol:
    """
    Self-healing pipeline for data integrity.
    
    NEVER crashes user session - always returns usable data
    while healing happens in background.
    """
    
    def __init__(
        self,
        data_dir: Path,
        quarantine_dir: Optional[Path] = None,
        nba_api_connector: Optional[Any] = None
    ):
        self.data_dir = data_dir
        self.quarantine_dir = quarantine_dir or data_dir / "quarantine"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        self.nba_api = nba_api_connector
        
        # Track healing operations
        self._healing_records: Dict[str, HealingRecord] = {}
        self._last_known_good: Dict[str, List[Dict]] = {}
    
    async def isolate_and_resync(self, player_id: str) -> Dict[str, Any]:
        """
        Isolate corrupted file and trigger background re-sync.
        
        Args:
            player_id: NBA player ID with corrupted data
            
        Returns:
            Status of healing operation
        """
        logger.info(f"[HEALER] Initiating healing for player {player_id}")
        
        # Record healing operation
        record = HealingRecord(
            player_id=player_id,
            quarantine_path="",
            triggered_at=datetime.now(),
            status="healing"
        )
        self._healing_records[player_id] = record
        
        try:
            # Step 1: Quarantine the corrupted file
            quarantine_path = await self._quarantine(player_id)
            record.quarantine_path = str(quarantine_path) if quarantine_path else ""
            
            # Step 2: Trigger background re-sync
            asyncio.create_task(self._resync_from_remote(player_id))
            
            return {
                'status': 'healing',
                'player_id': player_id,
                'quarantine_path': record.quarantine_path,
                'message': 'Corrupted file isolated, re-sync in progress'
            }
            
        except Exception as e:
            logger.error(f"[HEALER] Failed to heal {player_id}: {e}")
            record.status = "failed"
            record.error = str(e)
            return {
                'status': 'failed',
                'player_id': player_id,
                'error': str(e)
            }
    
    async def _quarantine(self, player_id: str) -> Optional[Path]:
        """Move corrupted file to quarantine directory"""
        source = self.data_dir / "players" / f"{player_id}_games.csv"
        
        if not source.exists():
            logger.warning(f"[HEALER] No file to quarantine for {player_id}")
            return None
        
        # Cache the data before quarantine (last known good)
        try:
            import pandas as pd
            df = pd.read_csv(source)
            self._last_known_good[player_id] = df.to_dict('records')
        except Exception:
            pass  # File may be too corrupted to read
        
        # Move to quarantine with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self.quarantine_dir / f"{player_id}_{timestamp}.csv"
        
        shutil.move(str(source), str(dest))
        logger.info(f"[HEALER] Quarantined {source} -> {dest}")
        
        return dest
    
    async def _resync_from_remote(self, player_id: str):
        """Re-sync player data from NBA API"""
        logger.info(f"[HEALER] Starting remote re-sync for {player_id}")
        
        record = self._healing_records.get(player_id)
        
        try:
            if self.nba_api:
                # Fetch fresh data from NBA API
                await self.nba_api.fetch_player_games(player_id, season=CURRENT_SEASON)
            
            if record:
                record.status = "healed"
            
            logger.info(f"[HEALER] Successfully healed data for {player_id}")
            
        except Exception as e:
            logger.error(f"[HEALER] Re-sync failed for {player_id}: {e}")
            if record:
                record.status = "failed"
                record.error = str(e)
            
            # Attempt to restore from quarantine
            await self._restore_from_quarantine(player_id)
    
    async def _restore_from_quarantine(self, player_id: str):
        """Restore file from quarantine if re-sync fails"""
        # Find most recent quarantined file
        pattern = f"{player_id}_*.csv"
        quarantined = list(self.quarantine_dir.glob(pattern))
        
        if not quarantined:
            logger.warning(f"[HEALER] No quarantine backup for {player_id}")
            return
        
        # Get most recent
        latest = max(quarantined, key=lambda p: p.stat().st_mtime)
        dest = self.data_dir / "players" / f"{player_id}_games.csv"
        
        shutil.copy(str(latest), str(dest))
        logger.info(f"[HEALER] Restored {player_id} from quarantine")
    
    def get_last_known_good(self, player_id: str) -> List[Dict]:
        """Get cached last-known-good data for a player"""
        return self._last_known_good.get(player_id, [])
    
    def is_healing(self, player_id: str) -> bool:
        """Check if a player is currently being healed"""
        record = self._healing_records.get(player_id)
        return record is not None and record.status == "healing"
    
    def get_healing_status(self) -> Dict[str, Any]:
        """Get status of all healing operations"""
        return {
            'active': [
                {
                    'player_id': r.player_id,
                    'triggered_at': r.triggered_at.isoformat(),
                    'status': r.status
                }
                for r in self._healing_records.values()
                if r.status == "healing"
            ],
            'completed': sum(1 for r in self._healing_records.values() if r.status == "healed"),
            'failed': sum(1 for r in self._healing_records.values() if r.status == "failed")
        }
    
    def cleanup_quarantine(self, max_age_days: int = 7):
        """Remove old quarantined files"""
        cutoff = datetime.now().timestamp() - (max_age_days * 86400)
        
        removed = 0
        for file in self.quarantine_dir.glob("*.csv"):
            if file.stat().st_mtime < cutoff:
                file.unlink()
                removed += 1
        
        logger.info(f"[HEALER] Cleaned up {removed} old quarantine files")
        return removed
