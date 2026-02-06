"""
Circular Buffer
===============
LRU eviction to maintain 500MB storage cap.
"""

from datetime import datetime
from typing import List

from ..core.types import Incident, IncidentStatus
from ..core.config import get_vanguard_config
from ..utils.logger import get_logger
from .storage import get_incident_storage

logger = get_logger(__name__)


async def evict_old_incidents() -> None:
    """
    Evict oldest RESOLVED incidents if storage exceeds 90% of cap.
    Never evict ACTIVE incidents.
    """
    config = get_vanguard_config()
    storage = get_incident_storage()
    
    # Check current storage usage
    current_size_mb = storage.get_storage_size_mb()
    cap_mb = config.storage_max_mb
    threshold_mb = cap_mb * 0.9  # 90% threshold
    
    if current_size_mb < threshold_mb:
        logger.debug("storage_under_threshold", current=current_size_mb, threshold=threshold_mb)
        return
    
    logger.warning("storage_threshold_exceeded", current=current_size_mb, threshold=threshold_mb)
    
    # Load all incidents and sort by timestamp (oldest first)
    fingerprints = storage.list_incidents()
    incidents: List[tuple[Incident, str]] = []
    
    for fp in fingerprints:
        incident = await storage.load(fp)
        if incident and incident["status"] == IncidentStatus.RESOLVED:
            incidents.append((incident, fp))
    
    # Sort by timestamp (oldest first)
    incidents.sort(key=lambda x: x[0]["timestamp"])
    
    # Evict oldest resolved incidents until under threshold
    evicted_count = 0
    for incident, fingerprint in incidents:
        if storage.get_storage_size_mb() < threshold_mb:
            break
        
        await storage.delete(fingerprint)
        evicted_count += 1
        logger.info("incident_evicted", fingerprint=fingerprint, timestamp=incident["timestamp"])
    
    final_size = storage.get_storage_size_mb()
    logger.info("eviction_complete", evicted=evicted_count, final_size_mb=final_size)


class CircularBuffer:
    """Circular buffer manager for incident storage."""
    
    async def check_and_evict(self) -> None:
        """Check storage and trigger eviction if needed."""
        await evict_old_incidents()
