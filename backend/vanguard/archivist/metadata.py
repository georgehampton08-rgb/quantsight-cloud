"""
Metadata Tracker
================
Track incident counts and last purge timestamp.
"""

import json
from pathlib import Path
from typing import TypedDict
import aiofiles

from ..core.config import get_vanguard_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Metadata(TypedDict):
    """Metadata structure."""
    total_incidents: int
    active_count: int
    resolved_count: int
    last_purge_timestamp: str


class MetadataTracker:
    """Tracks archivist metadata."""
    
    def __init__(self):
        config = get_vanguard_config()
        self.metadata_path = Path(config.storage_path) / "metadata.json"
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def load(self) -> Metadata:
        """Load metadata from disk or Firestore."""
        config = get_vanguard_config()
        
        # FIRESTORE TIER
        if config.storage_mode == "FIRESTORE":
            try:
                import firebase_admin
                from firebase_admin import firestore
                db = firestore.client()
                doc = db.collection('vanguard_metadata').document('global').get()
                if doc.exists:
                    return doc.to_dict()
            except Exception as e:
                logger.error("firestore_metadata_load_error", error=str(e))

        # FILE SYSTEM TIER
        try:
            if self.metadata_path.exists():
                async with aiofiles.open(self.metadata_path, "r") as f:
                    data = await f.read()
                    return json.loads(data)
            else:
                return {
                    "total_incidents": 0,
                    "active_count": 0,
                    "resolved_count": 0,
                    "last_purge_timestamp": None
                }
        except Exception as e:
            logger.error("metadata_load_error", error=str(e))
            return {
                "total_incidents": 0,
                "active_count": 0,
                "resolved_count": 0,
                "last_purge_timestamp": None
            }
    
    async def save(self, metadata: Metadata) -> None:
        """Save metadata to disk."""
        try:
            async with aiofiles.open(self.metadata_path, "w") as f:
                await f.write(json.dumps(metadata, indent=2))
            logger.debug("metadata_saved")
        except Exception as e:
            logger.error("metadata_save_error", error=str(e))
