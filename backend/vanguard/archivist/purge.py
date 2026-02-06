"""
Purge Scheduler
===============
Scheduled task to delete resolved incidents >7 days old.
"""

import asyncio
from datetime import datetime, timedelta

from ..core.types import IncidentStatus
from ..core.config import get_vanguard_config
from ..utils.logger import get_logger
from .storage import get_incident_storage
from .metadata import MetadataTracker

logger = get_logger(__name__)


class PurgeScheduler:
    """Scheduled purge of old resolved incidents."""
    
    def __init__(self):
        self.config = get_vanguard_config()
        self.running = False
        self.task: asyncio.Task | None = None
    
    async def start(self) -> None:
        """Start the purge scheduler (runs daily)."""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._purge_loop())
        logger.info("purge_scheduler_started")
    
    async def stop(self) -> None:
        """Stop the purge scheduler."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("purge_scheduler_stopped")
    
    async def _purge_loop(self) -> None:
        """Run purge daily at 3 AM."""
        while self.running:
            try:
                # Wait until next 3 AM (simplified - runs every 24 hours)
                await asyncio.sleep(86400)  # 24 hours
                
                await self.purge_old_incidents()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("purge_loop_error", error=str(e))
    
    async def purge_old_incidents(self) -> None:
        """Delete resolved incidents older than retention period."""
        storage = get_incident_storage()
        retention_days = self.config.retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        logger.info("purge_starting", retention_days=retention_days, cutoff_date=cutoff_date.isoformat())
        
        # Get all incidents
        fingerprints = storage.list_incidents()
        purged_count = 0
        freed_mb = 0.0
        
        for fp in fingerprints:
            incident = await storage.load(fp)
            
            if not incident:
                continue
            
            # Only purge RESOLVED incidents
            if incident["status"] != IncidentStatus.RESOLVED:
                logger.debug("skipping_active_incident", fingerprint=fp)
                continue
            
            # Check if older than retention period
            incident_date = datetime.fromisoformat(incident["timestamp"])
            if incident_date < cutoff_date:
                # Calculate size before deletion
                file_size_kb = storage._get_incident_path(fp).stat().st_size / 1024
                
                # Delete incident
                if await storage.delete(fp):
                    purged_count += 1
                    freed_mb += file_size_kb / 1024
                    logger.info("incident_purged", fingerprint=fp, age_days=(datetime.utcnow() - incident_date).days)
        
        # Update metadata
        metadata_tracker = MetadataTracker()
        metadata = await metadata_tracker.load()
        metadata["last_purge_timestamp"] = datetime.utcnow().isoformat()
        await metadata_tracker.save(metadata)
        
        logger.info("purge_complete", purged=purged_count, freed_mb=f"{freed_mb:.2f}")
