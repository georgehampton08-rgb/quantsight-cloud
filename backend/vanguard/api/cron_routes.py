"""
Vanguard Cron Routes
====================
Protected endpoints for scheduled tasks (Cloud Scheduler).
"""
from fastapi import APIRouter, HTTPException, Header
from datetime import datetime
import logging
import os

from vanguard.archivist.archive_manager import ArchiveManager
from vanguard.archivist.storage import get_incident_storage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["vanguard-cron"])

# Cloud Scheduler auth token (set via environment variable)
CRON_AUTH_TOKEN = os.getenv("VANGUARD_CRON_AUTH_TOKEN", "")


@router.post("/vanguard/admin/cron/archive")
async def create_weekly_archive(authorization: str = Header(None)):
    """
    Weekly archive creation endpoint (called by Cloud Scheduler).
    
    Requires authorization header with VANGUARD_CRON_AUTH_TOKEN.
    """
    # Verify authorization
    if not CRON_AUTH_TOKEN:
        raise HTTPException(403, "Cron auth not configured")
    
    if not authorization or authorization != f"Bearer {CRON_AUTH_TOKEN}":
        raise HTTPException(403, "Invalid cron authorization")
    
    try:
        storage = get_incident_storage()
        archive_manager = ArchiveManager(storage)
        
        # Archive resolved incidents
        result = await archive_manager.archive_resolved_incidents()
        
        logger.info(f"✅ Weekly archive created: {result['filename']}")
        
        return {
            "success": True,
            "archived_count": result["archived_count"],
            "filename": result["filename"],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to create weekly archive: {e}")
        raise HTTPException(500, f"Archive creation failed: {str(e)}")
