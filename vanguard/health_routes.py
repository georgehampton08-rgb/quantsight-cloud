"""
Enhanced Vanguard health endpoints with score-based tracking.
"""

from fastapi import APIRouter
from vanguard.health_monitor import get_health_monitor
from vanguard.health_scoring import get_score_calculator, EndpointHealth
from vanguard.archivist import get_vanguard
from datetime import datetime

from datetime import datetime
import logging
from fastapi import HTTPException

# Remove prefix - will be added by main.py
router = APIRouter(tags=["vanguard"])

@router.get("/vanguard")
async def vanguard_root():
    """Vanguard service root endpoint"""
    return {
        "service": "vanguard",
        "version": "4.4.5",
        "description": "Operational health monitoring and self-healing system",
        "endpoints": [
            "/vanguard/health/score",
            "/vanguard/health/history",
            "/vanguard/incidents",
            "/vanguard/dashboard"
        ],
        "status": "operational"
    }

@router.get("/vanguard/dashboard")
async def vanguard_dashboard():
    """Dashboard data endpoint (distinct from frontend #/vanguard route)"""
    from vanguard.archivist import get_vanguard
    
    try:
        archivist = get_vanguard()
        
        # Get recent incidents
        recent_incidents = archivist.get_recent_incidents(hours=24, limit=20)
        
        return {
            "incidents_24h": len(recent_incidents),
            "recent_incidents": [
                {
                    "endpoint": inc.get("endpoint", "unknown"),
                    "error_type": inc.get("error_type", "unknown"),
                    "count": inc.get("count", 0),
                    "last_occurred": inc.get("last_occurred", datetime.utcnow()).isoformat() + "Z"
                }
                for inc in recent_incidents[:10]
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(500, f"Dashboard unavailable: {str(e)}")


@router.get("/vanguard/health/score")
async def get_health_score():
    """
    Get comprehensive health score (0-100) with full breakdown.
    
    Returns:
        - overall_score: 0-100 weighted score
        - status: 'healthy', 'warning', 'critical'
        - components: System component health
        - endpoints: Endpoint health statuses
        - details: Score breakdown
    """
    try:
        monitor = get_health_monitor()
        calculator = get_score_calculator()
        
        # Run all component health checks
        health_results = await monitor.run_all_checks()
        
        # Get endpoint health from Vanguard incidents
        archivist = get_vanguard()
        incidents = archivist.get_recent_incidents(hours=24)
        
        # Build endpoint health list
        endpoint_health_map = {}
        for inc in incidents:
            ep = inc.get('endpoint', 'unknown')
            if ep not in endpoint_health_map or inc.get('severity') == 'high':
                # Determine status from severity
                severity = inc.get('severity', 'medium')
                if severity == 'low':
                    status = 'warning'
                elif severity in ['high', 'critical']:
                    status = 'critical'
                else:
                    status = 'warning'
                
                # Determine criticality
                criticality = 'critical' if ep in calculator.CRITICAL_ENDPOINTS else 'standard'
                
                endpoint_health_map[ep] = EndpointHealth(
                    endpoint=ep,
                    status=status,
                    last_check=inc.get('first_seen'),
                    error=inc.get('error_type'),
                    criticality=criticality,
                    uptime_percent=calculator.calculate_uptime(ep)
                )
        
        # Add healthy endpoints (from health check)
        for check_name in ['nba_api', 'gemini_ai', 'firestore']:
            # These are already in components, skip
            pass
        
        endpoints = list(endpoint_health_map.values())
        
        # Calculate overall score
        score_result = calculator.calculate_overall_score(health_results, endpoints)
        
        # Track endpoints for uptime calculation
        for ep in endpoints:
            calculator.track_endpoint_health(ep)
        
        return {
            "overall_score": score_result.overall_score,
            "status": score_result.status,
            "components": {
                name: {
                    "status": comp.status,
                    "latency_ms": comp.latency_ms,
                    "error": comp.error,
                    "criticality": comp.criticality
                }
                for name, comp in score_result.components.items()
            },
            "endpoints": [
                {
                    "endpoint": ep.endpoint,
                    "status": ep.status,
                    "uptime_percent": round(ep.uptime_percent, 2),
                    "criticality": ep.criticality,
                    "error": ep.error
                }
                for ep in score_result.endpoints
            ],
            "details": score_result.details,
            "timestamp": score_result.timestamp
        }
        
    except Exception as e:
        return {
            "overall_score": 0,
            "status": "critical",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/vanguard/health/history")
async def get_health_history(hours: int = 24):
    """
    Get historical health scores and trends.
    
    Args:
        hours: Number of hours of history to return
        
    Returns:
        Array of health scores over time
    """
    # TODO: Implement health score history storage
    return {
        "message": "Health history tracking coming soon",
        "hours_requested": hours
    }
