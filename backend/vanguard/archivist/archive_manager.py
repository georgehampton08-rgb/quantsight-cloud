"""
Vanguard Archive System
=======================
Weekly compression of resolved incidents into archives.
"""
import gzip
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ArchiveManager:
    """Manages compression and retrieval of resolved incidents."""
    
    def __init__(self, archive_path: Path = None):
        self.archive_path = archive_path or Path("vanguard_archives")
        self.archive_path.mkdir(exist_ok=True)
    
    async def create_weekly_archive(
        self, 
        incidents: List[Dict[str, Any]], 
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Optional[Path]:
        """
        Compress resolved incidents into a weekly archive.
        
        Args:
            incidents: List of resolved incident dictionaries
            start_date: Start of the date range
            end_date: End of the date range
            
        Returns:
            Path to created archive file, or None if no incidents
        """
        if not incidents:
            logger.info("No incidents to archive")
            return None
        
        # Default to last 7 days if not specified
        end_date = end_date or datetime.now(timezone.utc)
        start_date = start_date or (end_date - timedelta(days=7))
        
        # Create archive filename
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        filename = f"{start_str}_to_{end_str}_incidents_{len(incidents)}.json.gz"
        archive_file = self.archive_path / filename
        
        # Build archive structure
        archive_data = {
            "date_range": {
                "start": start_str,
                "end": end_str
            },
            "incident_count": len(incidents),
            "incidents": incidents,
            "created_at": datetime.now(timezone.utc).isoformat() + "Z"
        }
        
        # Compress and write
        try:
            with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
                json.dump(archive_data, f, indent=2, default=str)
            
            logger.info(f"Created archive: {archive_file} ({len(incidents)} incidents)")
            return archive_file
            
        except Exception as e:
            logger.error(f"Failed to create archive: {e}")
            return None
    
    def list_archives(self) -> List[Dict[str, Any]]:
        """List all available archives with metadata."""
        archives = []
        
        for archive_file in sorted(self.archive_path.glob("*.json.gz"), reverse=True):
            try:
                # Parse filename for metadata
                name = archive_file.stem.replace(".json", "")
                parts = name.split("_")
                
                archives.append({
                    "filename": archive_file.name,
                    "path": str(archive_file),
                    "size_bytes": archive_file.stat().st_size,
                    "start_date": parts[0] if len(parts) > 0 else None,
                    "end_date": parts[2] if len(parts) > 2 else None,
                    "incident_count": int(parts[-1]) if parts[-1].isdigit() else None
                })
            except Exception as e:
                logger.warning(f"Failed to parse archive {archive_file}: {e}")
                
        return archives
    
    async def load_archive(self, filename: str) -> Optional[Dict[str, Any]]:
        """Load and decompress an archive file."""
        archive_file = self.archive_path / filename
        
        if not archive_file.exists():
            logger.warning(f"Archive not found: {filename}")
            return None
        
        try:
            with gzip.open(archive_file, 'rt', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load archive {filename}: {e}")
            return None
    
    async def archive_resolved_incidents(self, storage) -> Dict[str, Any]:
        """
        Archive all resolved incidents older than 7 days.
        
        Args:
            storage: IncidentStorage instance
            
        Returns:
            Summary of archive operation
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        fingerprints = storage.list_incidents(limit=1000)
        
        to_archive = []
        for fp in fingerprints:
            try:
                incident = await storage.load(fp)
                if not incident:
                    continue
                
                # Only archive resolved incidents older than cutoff
                if incident.get("status") != "resolved":
                    continue
                    
                resolved_at = incident.get("resolved_at")
                if resolved_at:
                    resolved_dt = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
                    if resolved_dt < cutoff:
                        to_archive.append(incident)
            except Exception as e:
                logger.warning(f"Error checking incident {fp}: {e}")
        
        if not to_archive:
            return {"archived": 0, "message": "No resolved incidents ready for archiving"}
        
        # Create archive
        archive_path = await self.create_weekly_archive(to_archive)
        
        if archive_path:
            # Delete archived incidents from active storage
            deleted = 0
            for incident in to_archive:
                fp = incident.get("fingerprint")
                if fp:
                    try:
                        await storage.delete(fp)
                        deleted += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete archived incident {fp}: {e}")
            
            return {
                "archived": len(to_archive),
                "deleted": deleted,
                "archive_file": str(archive_path),
                "message": f"Archived {len(to_archive)} incidents"
            }
        
        return {"archived": 0, "error": "Failed to create archive"}


def get_archive_manager() -> ArchiveManager:
    """Get the singleton archive manager instance."""
    return ArchiveManager()
