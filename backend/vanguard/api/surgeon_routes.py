"""
Vanguard Surgeon Admin API Endpoints
=====================================
API endpoints for managing and monitoring Surgeon actions.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime

from ..surgeon.learning import get_learning_system
from ..archivist.storage import get_incident_storage
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/vanguard/surgeon/actions")
async def get_surgeon_actions(limit: int = 100) -> Dict[str, Any]:
    """
    Get recent Surgeon actions with outcomes.
    
    Query params:
        limit: Max number of actions to return (default 100)
    """
    try:
        storage = get_incident_storage()
        actions = await storage.query_collection(
            collection="vanguard_surgeon_actions",
            limit=limit,
            order_by=[("logged_at", "desc")]
        )
        
        return {
            "actions": actions,
            "total": len(actions)
        }
    except Exception as e:
        logger.error("get_surgeon_actions_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch actions")


@router.get("/vanguard/surgeon/stats")
async def get_surgeon_stats() -> Dict[str, Any]:
    """
    Get Surgeon statistics and success rates.
    
    Returns:
        Success rates per action type and action counts
    """
    try:
        storage = get_incident_storage()
        learning = get_learning_system()
        
        # Get success rates
        success_rates = await learning.get_all_success_rates(storage)
        
        # Get total action counts
        actions = await storage.query_collection(
            collection="vanguard_surgeon_actions"
        )
        
        action_counts = {
            "MONITOR": sum(1 for a in actions if a.get("action") == "MONITOR"),
            "RATE_LIMIT": sum(1 for a in actions if a.get("action") == "RATE_LIMIT"),
            "QUARANTINE": sum(1 for a in actions if a.get("action") == "QUARANTINE"),
            "LOG_ONLY": sum(1 for a in actions if a.get("action") == "LOG_ONLY"),
        }
        
        return {
            "success_rates": success_rates,
            "action_counts": action_counts,
            "total_actions": len(actions),
            "period": "all_time"
        }
    except Exception as e:
        logger.error("get_surgeon_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch stats")


@router.get("/vanguard/surgeon/quarantines")
async def get_active_quarantines() -> Dict[str, Any]:
    """Get all currently active quarantines."""
    try:
        storage = get_incident_storage()
        quarantines = await storage.query_collection(
            collection="vanguard_quarantine",
            filters=[("active", "==", True)]
        )
        
        return {
            "quarantines": quarantines,
            "count": len(quarantines)
        }
    except Exception as e:
        logger.error("get_quarantines_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch quarantines")


@router.post("/vanguard/surgeon/quarantine/{endpoint_id}/release")
async def release_quarantine(endpoint_id: str) -> Dict[str, str]:
    """
    Manually release an endpoint from quarantine.
    
    Args:
        endpoint_id: Document ID (endpoint with / replaced by _)
    """
    try:
        storage = get_incident_storage()
        
        # Update quarantine to inactive
        await storage.update_document(
            collection="vanguard_quarantine",
            document_id=endpoint_id,
            updates={
                "active": False,
                "released_by": "manual",
                "released_at": datetime.utcnow().isoformat()
            }
        )
        
        logger.info("quarantine_released", endpoint_id=endpoint_id)
        
        return {
            "status": "released",
            "endpoint_id": endpoint_id,
            "message": "Endpoint released from quarantine"
        }
    except Exception as e:
        logger.error("release_quarantine_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to release quarantine")


@router.post("/vanguard/surgeon/rate_limit/{endpoint_id}/remove")
async def remove_rate_limit(endpoint_id: str) -> Dict[str, str]:
    """
    Remove rate limit from an endpoint.
    
    Args:
        endpoint_id: Document ID (endpoint with / replaced by _)
    """
    try:
        storage = get_incident_storage()
        
        # Update rate limit to inactive
        await storage.update_document(
            collection="vanguard_rate_limits",
            document_id=endpoint_id,
            updates={
                "active": False,
                "removed_by": "manual",
                "removed_at": datetime.utcnow().isoformat()
            }
        )
        
        logger.info("rate_limit_removed", endpoint_id=endpoint_id)
        
        return {
            "status": "removed",
            "endpoint_id": endpoint_id,
            "message": "Rate limit removed from endpoint"
        }
    except Exception as e:
        logger.error("remove_rate_limit_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to remove rate limit")
