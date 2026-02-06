"""
Nexus Hub API Routes
====================
Exposes Nexus Hub functionality via REST API.

Provides endpoints for:
- System overview and health monitoring
- Route recommendations
- Cooldown management
- Performance metrics
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nexus", tags=["nexus"])

# Try to import NexusHub with graceful fallback
try:
    from aegis.nexus_hub import get_nexus_hub, NexusHub
    NEXUS_AVAILABLE = True
    logger.info("Nexus Hub module loaded successfully")
except ImportError as e:
    logger.warning(f"Nexus Hub not available: {e}")
    NEXUS_AVAILABLE = False


@router.get("/overview")
async def get_nexus_overview():
    """
    Get complete Nexus Hub system overview.
    
    Returns detailed information about:
    - System status and uptime
    - Registered endpoints
    - Health status
    - Routing statistics
    - Queue metrics
    - Error statistics
    """
    if not NEXUS_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "Nexus Hub module not loaded",
            "reason": "Desktop-only feature or missing dependencies"
        }
    
    try:
        hub = get_nexus_hub()
        overview = hub.get_system_overview()
        return overview.to_dict()
    except Exception as e:
        logger.error(f"Nexus overview error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get overview: {str(e)}")


@router.get("/health")
async def get_nexus_health():
    """
    Get unified health status for all services.
    
    Returns health status for:
    - NBA API
    - Database
    - Aegis components
    - System resources
    """
    if not NEXUS_AVAILABLE:
        return {
            "status": "unavailable",
            "overall": "unknown",
            "services": {}
        }
    
    try:
        hub = get_nexus_hub()
        health = hub.get_health()
        return health.to_dict()
    except Exception as e:
        logger.error(f"Nexus health error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get health: {str(e)}")


@router.get("/cooldowns")
async def get_active_cooldowns():
    """
    Get all active service cooldowns.
    
    Returns dictionary of services currently in cooldown mode
    with their expiration times and reasons.
    """
    if not NEXUS_AVAILABLE:
        return {}
    
    try:
        hub = get_nexus_hub()
        return hub.get_cooldowns()
    except Exception as e:
        logger.error(f"Cooldowns error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get cooldowns: {str(e)}")


@router.get("/route-matrix")
async def get_route_matrix():
    """
    Get routing matrix showing recommended strategies for all endpoints.
    
    Returns list of endpoints with their:
    - Path
    - Recommended strategy (cache, direct, race)
    - Cache availability
    - Expected latency
    """
    if not NEXUS_AVAILABLE:
        return []
    
    try:
        hub = get_nexus_hub()
        return hub.get_route_matrix()
    except Exception as e:
        logger.error(f"Route matrix error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get route matrix: {str(e)}")


@router.get("/recommend/{path:path}")
async def get_route_recommendation(
    path: str,
    priority: Optional[str] = Query(None, description="Request priority: critical, high, medium, low"),
    force_fresh: Optional[bool] = Query(False, description="Force fresh data, bypass cache")
):
    """
    Get routing recommendation for a specific path.
    
    Args:
        path: API path to get recommendation for
        priority: Request priority level
        force_fresh: Whether to bypass cache
        
    Returns:
        RouteDecision with recommended strategy and metadata
    """
    if not NEXUS_AVAILABLE:
        return {
            "strategy": "direct",
            "cache_available": False,
            "reason": "Nexus Hub not available"
        }
    
    try:
        hub = get_nexus_hub()
        context = {}
        if priority:
            context["priority"] = priority
        if force_fresh:
            context["force_fresh"] = force_fresh
            
        decision = hub.recommend_route(f"/{path}", context if context else None)
        return decision.to_dict()
    except Exception as e:
        logger.error(f"Route recommendation error for {path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recommendation: {str(e)}")


@router.post("/cooldown/{service}")
async def enter_cooldown(
    service: str,
    duration: int = Query(60, description="Cooldown duration in seconds", ge=1, le=3600)
):
    """
    Manually put a service in cooldown mode.
    
    Args:
        service: Service name (e.g., 'nba_api', 'database')
        duration: Cooldown duration in seconds (1-3600)
        
    Returns:
        Confirmation with service name and duration
    """
    if not NEXUS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Nexus Hub not available - cooldown management disabled"
        )
    
    try:
        hub = get_nexus_hub()
        hub.enter_cooldown(service, duration)
        logger.info(f"Service {service} entered cooldown for {duration}s")
        return {
            "status": "success",
            "service": service,
            "duration": duration,
            "message": f"Service {service} is now in cooldown for {duration} seconds"
        }
    except Exception as e:
        logger.error(f"Enter cooldown error for {service}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to enter cooldown: {str(e)}")


@router.delete("/cooldown/{service}")
async def exit_cooldown(service: str):
    """
    Manually exit a service from cooldown mode.
    
    Args:
        service: Service name to exit from cooldown
        
    Returns:
        Confirmation of cooldown exit
    """
    if not NEXUS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Nexus Hub not available - cooldown management disabled"
        )
    
    try:
        hub = get_nexus_hub()
        hub.exit_cooldown(service)
        logger.info(f"Service {service} exited cooldown")
        return {
            "status": "success",
            "service": service,
            "message": f"Service {service} is no longer in cooldown"
        }
    except Exception as e:
        logger.error(f"Exit cooldown error for {service}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to exit cooldown: {str(e)}")
