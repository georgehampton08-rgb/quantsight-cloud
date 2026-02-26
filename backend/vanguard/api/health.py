"""
Vanguard Health Endpoint
=========================
Provides status of all Vanguard subsystems.
"""

from fastapi import APIRouter
from typing import Dict, Any

from ..core.config import get_vanguard_config
from ..bootstrap.redis_client import ping_redis
from ..surgeon.leader_election import get_leader_election
from ..archivist.storage import get_incident_storage
from ..archivist.metadata import MetadataTracker

router = APIRouter(prefix="/vanguard", tags=["vanguard"])


@router.get("/health")
async def vanguard_health() -> Dict[str, Any]:
    """Provide a comprehensive health check of Vanguard subsystems."""
    config = get_vanguard_config()
    redis_healthy = await ping_redis()
    metadata = await MetadataTracker().load()
    leader = get_leader_election()
    storage = get_incident_storage()
    storage_mb = storage.get_storage_size_mb()
    
    return {
        "status": "operational" if config.enabled else "disabled",
        "version": "3.1.2",
        "mode": config.mode.value,
        "storage": {
            "mode": config.storage_mode,
            "path": config.storage_path,
            "size_mb": f"{storage_mb:.2f}",
            "max_mb": config.storage_max_mb
        },
        "bootstrap": {
            "redis_connected": redis_healthy,
        },
        "role": "LEAD_SOVEREIGN" if leader.is_leader else "FOLLOWER",
        "subsystems": {
            "inquisitor": {"enabled": True, "sampling_rate": config.sampling_rate},
            "archivist": {
                "enabled": True,
                "storage_mb": f"{storage_mb:.2f}",
                "storage_cap_mb": config.storage_max_mb,
                "retention_days": config.retention_days
            },
            "profiler": {"enabled": config.llm_enabled, "model": config.llm_model if config.llm_enabled else None},
            "surgeon": {"enabled": config.mode in ["CIRCUIT_BREAKER", "FULL_SOVEREIGN"]},
            "vaccine": {"enabled": config.vaccine_enabled}
        },
        "incidents": {
            "total": metadata.get("total_incidents", 0),
            "active": metadata.get("active_count", 0),
            "resolved": metadata.get("resolved_count", 0),
            "last_purge": metadata.get("last_purge_timestamp")
        }
    }


@router.get("/incidents")
async def list_vanguard_incidents() -> Dict[str, Any]:
    """List all recent incidents tracked by Vanguard."""
    storage = get_incident_storage()
    fingerprints = await storage.list_incidents()

    incidents = []
    for fp in fingerprints:
        incident = await storage.load(fp)
        if incident:
            summary = {
                "fingerprint": fp,
                "service": incident.get("labels", {}).get("service", "unknown"),
                "error_type": incident.get("error_type", "unknown"),
                "endpoint": incident.get("endpoint", "unknown"),
                "occurrence_count": incident.get("occurrence_count", 1),
                "last_seen": incident.get("last_seen"),
                "severity": "high" if "500" in incident.get("error_type", "") else "medium"
            }
            incidents.append(summary)

    incidents.sort(key=lambda x: x.get("last_seen", ""), reverse=True)

    return {"count": len(incidents), "incidents": incidents}



@router.get("/incidents/{fingerprint}")
async def get_incident_detail(fingerprint: str) -> Dict[str, Any]:
    """Get full details for a specific incident."""
    storage = get_incident_storage()
    incident = await storage.load(fingerprint)

    if not incident:
        return {"error": "Incident not found", "fingerprint": fingerprint}

    return incident
