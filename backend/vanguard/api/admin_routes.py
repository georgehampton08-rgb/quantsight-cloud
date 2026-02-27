"""
Vanguard Admin Routes
====================
Admin endpoints for incident management and learning data verification.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging
import os

from vanguard.archivist.storage import get_incident_storage
from vanguard.resolution_learner import VanguardResolutionLearner
from vanguard.ai.ai_analyzer import VanguardAIAnalyzer
from vanguard.audit.audit_logger import get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter(tags=["vanguard-admin"])
audit = get_audit_logger()



class ResolveRequest(BaseModel):
    approved: bool = False  # Manual approval required
    resolution_notes: Optional[str] = None


class BulkResolveRequest(BaseModel):
    fingerprints: List[str]
    resolution_notes: Optional[str] = None


class ResolveAllRequest(BaseModel):
    confirm: bool
    resolution_notes: Optional[str] = "Batch resolution"


class CIIncidentRequest(BaseModel):
    fingerprint: str
    severity: str = "AMBER"
    error_type: str
    error_message: str
    metadata: Optional[dict] = None


class ModeRequest(BaseModel):
    mode: str  # "SILENT_OBSERVER", "CIRCUIT_BREAKER", "FULL_SOVEREIGN"


@router.post("/vanguard/admin/mode")
async def toggle_vanguard_mode(http_request: Request, request: ModeRequest):
    """Manually toggle Vanguard operational mode."""
    from vanguard.core.config import get_vanguard_config, VanguardMode
    config = get_vanguard_config()
    
    try:
        new_mode = VanguardMode(request.mode.upper())
        old_mode = config.mode
        config.mode = new_mode
        
        logger.warning(f"Vanguard mode manually changed: {old_mode} -> {new_mode}")
        await audit.log(
            action="TOGGLE_MODE",
            request_id=http_request.headers.get("X-Request-ID", "unknown"),
            affected_ids=[str(old_mode), str(new_mode)],
            metadata={"old_mode": str(old_mode), "new_mode": str(new_mode)},
            result="SUCCESS",
            ip_address=http_request.client.host if http_request.client else None,
        )
        return {
            "success": True, 
            "old_mode": old_mode,
            "new_mode": new_mode,
            "message": f"Vanguard switched to {new_mode}"
        }
    except ValueError:
        raise HTTPException(400, f"Invalid mode: {request.mode}. Use SILENT_OBSERVER, CIRCUIT_BREAKER, or FULL_SOVEREIGN.")


@router.post("/vanguard/admin/incidents/ingest")
async def ingest_ci_incident(request: CIIncidentRequest):
    """Ingest an incident from CI/CD pipelines (drift oracle, perf monitor, dep audit)."""
    from vanguard.core.types import Incident
    storage = get_incident_storage()

    incident: Incident = {
        "fingerprint": request.fingerprint,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "severity": request.severity.upper(),
        "status": "ACTIVE",
        "error_type": request.error_type,
        "error_message": request.error_message,
        "endpoint": "CI/CD Pipeline",
        "request_id": f"ci-{request.error_type.lower()}",
        "context_vector": {
            "source": "github_actions",
            "incident_type": request.error_type,
            "metadata": request.metadata or {},
        },
        "remediation_log": [],
        "resolved_at": None,
    }

    stored = await storage.store(incident)
    if stored:
        logger.info(f"CI incident ingested: {request.fingerprint} ({request.severity})")
        return {"success": True, "fingerprint": request.fingerprint}
    return {"success": False, "message": "Incident already exists or storage failed"}


@router.get("/vanguard/admin/incidents")
async def list_all_incidents(status: Optional[str] = None, limit: int = 2000):
    """
    List all incidents with optional status filter.
    
    Args:
        status: Filter by 'active' or 'resolved'
        limit: Maximum incidents to return
    """
    try:
        storage = get_incident_storage()
        fingerprints = await storage.list_incidents(limit=limit)
        
        incidents = []
        active_count = 0
        resolved_count = 0
        
        for fp in fingerprints:
            incident = await storage.load(fp)
            if incident:
                inc_status = incident.get("status", "active")
                
                if inc_status == "active":
                    active_count += 1
                else:
                    resolved_count += 1
                
                # Apply status filter
                if status and inc_status != status:
                    continue
                
                incidents.append({
                    "fingerprint": fp,
                    "endpoint": incident.get("endpoint", "unknown"),
                    "error_type": incident.get("error_type", "unknown"),
                    "status": inc_status,
                    "occurrence_count": incident.get("occurrence_count", 1),
                    "first_seen": incident.get("first_seen"),
                    "last_seen": incident.get("last_seen"),
                    "severity": incident.get("severity", "medium"),
                    "labels": incident.get("labels", {}),
                })
        
        return {
            "total": len(fingerprints),
            "active": active_count,
            "resolved": resolved_count,
            "incidents": incidents,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Failed to list incidents: {e}")
        raise HTTPException(500, f"Failed to list incidents: {str(e)}")


@router.get("/vanguard/admin/stats")
async def get_vanguard_stats():
    """
    Composite health score for the Vanguard Control Room.

    Score = (Incident × 0.40) + (Subsystem × 0.35) + (Endpoint × 0.25)
    """
    try:
        from vanguard.core.config import get_vanguard_config
        from vanguard.bootstrap.redis_client import ping_redis
        import math

        config = get_vanguard_config()
        storage = get_incident_storage()
        fingerprints = await storage.list_incidents(limit=2000)

        # ── Count incidents + collect endpoint stats ─────────────────────
        active = 0
        resolved = 0
        endpoint_hits: dict[str, int] = {}  # endpoint → active occurrence count

        for fp in fingerprints:
            inc = await storage.load(fp)
            if not inc:
                continue
            if inc.get("status") == "active":
                active += 1
                ep = inc.get("endpoint", "unknown")
                endpoint_hits[ep] = endpoint_hits.get(ep, 0) + inc.get("occurrence_count", 1)
            else:
                resolved += 1

        total = active + resolved

        # ═══════════════════════════════════════════════════════════════════
        # Component 1 — Incident Score (40%)
        # Log decay: 0→100, 5→84, 10→75, 25→62, 50→52, 100→43
        # ═══════════════════════════════════════════════════════════════════
        if active == 0:
            incident_score = 100.0
        else:
            incident_score = max(20.0, 100.0 - (math.log10(active + 1) * 40.0))
        # Resolution ratio bonus (up to +10)
        if total > 0:
            incident_score = min(100.0, incident_score + (resolved / total) * 10.0)

        # ═══════════════════════════════════════════════════════════════════
        # Component 2 — Subsystem Score (35%)
        # Weighted check of each Vanguard subsystem
        # ═══════════════════════════════════════════════════════════════════
        storage_mb = storage.get_storage_size_mb()
        storage_cap = config.storage_max_mb
        redis_ok = False
        try:
            redis_ok = await ping_redis()
        except Exception:
            pass

        # Surgeon: use env var directly because pydantic-settings validation_alias
        # does not resolve VanguardMode enum from VANGUARD_MODE env var.
        effective_mode = os.getenv("VANGUARD_MODE", config.mode.value)

        subsystem_health = {
            "inquisitor": config.enabled,
            "archivist": storage_mb < (storage_cap * 0.90),
            "profiler": config.llm_enabled,
            "vaccine": config.vaccine_enabled,
            "surgeon": effective_mode in ("CIRCUIT_BREAKER", "FULL_SOVEREIGN"),
            "redis": redis_ok,
        }

        # ── Debug logging for subsystem health diagnostics ──────────────
        logger.info(
            "SUBSYSTEM_HEALTH_DEBUG | "
            f"enabled={config.enabled} | "
            f"llm_enabled={config.llm_enabled} | "
            f"vaccine_enabled={config.vaccine_enabled} | "
            f"mode={config.mode.value} | "
            f"effective_mode={effective_mode} | "
            f"redis_ok={redis_ok} | "
            f"storage_mb={storage_mb:.2f}/{storage_cap} | "
            f"health={subsystem_health}"
        )

        # Weighted scoring: required subsystems matter more
        weights = {
            "inquisitor": 30,
            "archivist": 25,
            "profiler": 20,
            "vaccine": 15,
            "redis": 5,
            "surgeon": 5,
        }
        total_weight = sum(weights.values())
        healthy_weight = sum(w for k, w in weights.items() if subsystem_health.get(k, False))
        subsystem_score = (healthy_weight / total_weight) * 100.0

        # ═══════════════════════════════════════════════════════════════════
        # Component 3 — Endpoint Error Rate (25%)
        # Ratio of unique erroring endpoints to total known endpoints
        # ═══════════════════════════════════════════════════════════════════
        erroring_endpoints = len(endpoint_hits)
        if erroring_endpoints == 0:
            endpoint_score = 100.0
        else:
            # Scale: 1 endpoint erroring = ~90, 5 = ~70, 10 = ~55
            endpoint_score = max(20.0, 100.0 - (math.log10(erroring_endpoints + 1) * 45.0))

        # ═══════════════════════════════════════════════════════════════════
        # Composite Score
        # ═══════════════════════════════════════════════════════════════════
        health_score = (
            incident_score * 0.40 +
            subsystem_score * 0.35 +
            endpoint_score * 0.25
        )

        # Hot endpoints — top 5 most problematic
        hot_endpoints = sorted(
            [{"endpoint": ep, "active_count": c} for ep, c in endpoint_hits.items()],
            key=lambda x: x["active_count"],
            reverse=True,
        )[:5]

        return {
            "active_incidents": active,
            "resolved_incidents": resolved,
            "health_score": round(health_score, 1),
            "health_breakdown": {
                "incident_score": round(incident_score, 1),
                "subsystem_score": round(subsystem_score, 1),
                "endpoint_score": round(endpoint_score, 1),
            },
            "subsystem_health": subsystem_health,
            "hot_endpoints": hot_endpoints,
            "storage_mb": round(storage_mb, 2),
            "storage_cap_mb": storage_cap,
            "vanguard_mode": effective_mode,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error(f"Stats fetch failed: {e}")
        return {
            "active_incidents": 0,
            "resolved_incidents": 0,
            "health_score": 100.0,
            "health_breakdown": {"incident_score": 100.0, "subsystem_score": 100.0, "endpoint_score": 100.0},
            "subsystem_health": {},
            "hot_endpoints": [],
            "vanguard_mode": "UNKNOWN",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }



@router.post("/vanguard/admin/incidents/{fingerprint}/resolve")
async def resolve_incident(http_request: Request, fingerprint: str, request: ResolveRequest):
    """Mark a single incident as resolved with pre/post resolution analysis."""
    try:
        storage = get_incident_storage()
        
        # Load incident first to verify it exists
        incident = await storage.load(fingerprint)
        if not incident:
            raise HTTPException(404, f"Incident {fingerprint} not found")
        
        if incident.get("status") == "resolved":
            return {
                "success": True,
                "message": "Incident already resolved",
                "fingerprint": fingerprint
            }
        
        # Require explicit approval to resolve (prevents accidental resolution)
        if not request.approved:
            raise HTTPException(
                400, 
                "Resolution requires explicit approval. Send {'approved': true} in request body."
            )
        
        # ── Snapshot pre-resolution data ──────────────────────────────────
        pre_resolution_analysis = incident.get("ai_analysis")
        
        # ── Resolve the incident ─────────────────────────────────────────
        success = await storage.resolve(fingerprint)
        
        if success:
            # ── Save enriched resolution metadata ────────────────────────
            resolution_data = {
                "resolution_notes": request.resolution_notes or "",
                "resolved_by": "admin",
                "resolution_timestamp": datetime.utcnow().isoformat() + "Z",
            }
            
            # Preserve pre-resolution AI analysis snapshot
            if pre_resolution_analysis:
                resolution_data["pre_resolution_analysis"] = pre_resolution_analysis
            
            # Generate post-resolution AI summary (fire-and-forget, non-blocking)
            try:
                resolution_summary = {
                    "error_type": incident.get("error_type", "Unknown"),
                    "endpoint": incident.get("endpoint", "Unknown"),
                    "occurrence_count": incident.get("occurrence_count", 1),
                    "first_seen": incident.get("first_seen"),
                    "last_seen": incident.get("last_seen"),
                    "resolution_notes": request.resolution_notes or "No notes provided",
                    "duration_active": None,
                }
                # Calculate how long the incident was active
                if incident.get("first_seen") and incident.get("last_seen"):
                    try:
                        first = datetime.fromisoformat(incident["first_seen"].replace("Z", "+00:00"))
                        last = datetime.fromisoformat(incident["last_seen"].replace("Z", "+00:00"))
                        delta = last - first
                        resolution_summary["duration_active"] = str(delta)
                    except Exception:
                        pass
                
                resolution_data["resolution_summary"] = resolution_summary
            except Exception as e:
                logger.warning(f"Resolution summary generation failed: {e}")
            
            # Save all resolution data to the incident document
            await storage.update_incident(fingerprint, resolution_data)
            
            logger.info(f"Incident resolved with analysis: {fingerprint}")
            await audit.log(
                action="RESOLVE_INCIDENT",
                request_id=http_request.headers.get("X-Request-ID", "unknown"),
                affected_ids=[fingerprint],
                metadata={"resolution_notes": request.resolution_notes, "approved": request.approved},
                result="SUCCESS",
                ip_address=http_request.client.host if http_request.client else None,
            )
            return {
                "success": True,
                "message": "Incident resolved",
                "fingerprint": fingerprint,
                "resolution_notes": request.resolution_notes,
                "resolved_at": datetime.utcnow().isoformat() + "Z",
                "has_pre_analysis": pre_resolution_analysis is not None,
            }
        else:
            raise HTTPException(500, "Failed to resolve incident")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve incident {fingerprint}: {e}")
        raise HTTPException(500, str(e))


@router.post("/vanguard/admin/incidents/{fingerprint}/unresolve")
async def unresolve_incident(http_request: Request, fingerprint: str, request: ResolveRequest):
    """Revert a resolved incident back to active status."""
    try:
        storage = get_incident_storage()
        
        incident = await storage.load(fingerprint)
        if not incident:
            raise HTTPException(404, f"Incident {fingerprint} not found")
        
        if incident.get("status") == "active":
            return {
                "success": True,
                "message": "Incident is already active",
                "fingerprint": fingerprint
            }
        
        if not request.approved:
            raise HTTPException(
                400,
                "Unresolve requires explicit approval. Send {'approved': true} in request body."
            )
        
        # Revert status to active
        unresolve_data = {
            "status": "active",
            "unresolved_at": datetime.utcnow().isoformat() + "Z",
            "unresolved_by": "admin",
            "unresolve_reason": request.resolution_notes or "Undo resolve via Control Room",
        }
        
        success = await storage.update_incident(fingerprint, unresolve_data)
        
        if success:
            # Update metadata counts (reverse the resolve)
            await storage._update_metadata(is_new=False, is_resolved=False)
            # Manually adjust: increment active, decrement resolved
            try:
                if storage.config.storage_mode == "FIRESTORE":
                    import firebase_admin
                    from firebase_admin import firestore
                    db = firestore.client()
                    meta_ref = db.collection('vanguard_metadata').document('global')
                    snapshot = meta_ref.get()
                    if snapshot.exists:
                        data = snapshot.to_dict()
                        data["active_count"] = data.get("active_count", 0) + 1
                        data["resolved_count"] = max(0, data.get("resolved_count", 0) - 1)
                        meta_ref.set(data)
            except Exception as e:
                logger.warning(f"Metadata unresolve adjustment failed: {e}")
            
            logger.info(f"Incident unresolved: {fingerprint}")
            await audit.log(
                action="UNRESOLVE_INCIDENT",
                request_id=http_request.headers.get("X-Request-ID", "unknown"),
                affected_ids=[fingerprint],
                metadata={"reason": request.resolution_notes, "approved": request.approved},
                result="SUCCESS",
                ip_address=http_request.client.host if http_request.client else None,
            )
            return {
                "success": True,
                "message": "Incident reverted to active",
                "fingerprint": fingerprint,
                "unresolved_at": unresolve_data["unresolved_at"],
            }
        else:
            raise HTTPException(500, "Failed to unresolve incident")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unresolve incident {fingerprint}: {e}")
        raise HTTPException(500, str(e))

@router.post("/vanguard/admin/incidents/bulk-resolve")
async def bulk_resolve_incidents(request: BulkResolveRequest, http_request: Request = None):
    """Resolve multiple incidents by fingerprint with learning tracking."""
    storage = get_incident_storage()
    learner = VanguardResolutionLearner()
    
    resolved = []
    failed = []
    learned = 0
    
    for fp in request.fingerprints:
        try:
            # Load incident for learning
            incident = await storage.load(fp)
            if incident:
                # Record to learning corpus using record_fix
                incident_pattern = f"{incident.get('endpoint', 'unknown')} {incident.get('http_status', 0)} {incident.get('error_type', 'unknown')}"
                learner.record_fix(
                    incident_pattern=incident_pattern,
                    fix_description=request.resolution_notes or "Bulk resolution",
                    fix_files=["bulk_operation"],
                    deployed_revision="bulk_resolve",
                    incidents_before=incident.get('occurrence_count', 1),
                    fix_commit=None
                )
                learned += 1
            
            success = await storage.resolve(fp)
            if success:
                resolved.append(fp)
            else:
                failed.append({"fingerprint": fp, "reason": "resolve_failed"})
        except Exception as e:
            failed.append({"fingerprint": fp, "reason": str(e)})
    
    logger.info(f"Bulk resolve: {len(resolved)} resolved, {learned} learned, {len(failed)} failed")
    req_id = http_request.headers.get("X-Request-ID", "unknown") if http_request else "unknown"
    await audit.log(
        action="BULK_RESOLVE",
        request_id=req_id,
        affected_ids=resolved,
        metadata={"resolution_notes": request.resolution_notes, "failed_count": len(failed)},
        result="SUCCESS" if not failed else "PARTIAL",
        ip_address=http_request.client.host if http_request and http_request.client else None,
    )
    
    return {
        "resolved_count": len(resolved),
        "learned_count": learned,
        "failed_count": len(failed),
        "failed": failed
    }


@router.get("/vanguard/admin/incidents/{fingerprint}")
async def get_incident_detail_admin(fingerprint: str):
    """Get full details for a specific incident (Admin version)."""
    storage = get_incident_storage()
    incident = await storage.load(fingerprint)
    
    if not incident:
        raise HTTPException(404, f"Incident {fingerprint} not found")
        
    return incident


@router.post("/vanguard/admin/incidents/analyze-all")
async def batch_analyze_incidents(request: Request, force: bool = False):
    """Batch analyze all active incidents."""
    try:
        from vanguard.ai.ai_analyzer import get_ai_analyzer
        from vanguard.core.config import get_vanguard_config
        
        storage = get_incident_storage()
        analyzer = get_ai_analyzer()
        config = get_vanguard_config()
        
        # Collect system context once for the batch
        routes = []
        for route in request.app.routes:
            if hasattr(route, "path"):
                routes.append(f"{list(route.methods) if hasattr(route, 'methods') else 'GET'} {route.path}")

        system_context = {
            "mode": config.mode.value,
            "revision": os.getenv("K_REVISION", "local"),
            "routes": routes[:50]
        }
        
        fingerprints = await storage.list_incidents(limit=2000)
        to_analyze = []
        
        for fp in fingerprints:
            incident = await storage.load(fp)
            if not incident or incident.get('status') != 'active':
                continue
            # If not forcing, skip if it already has analysis
            if not force and ('ai_analysis' in incident or 'ai_analyses' in incident):
                continue
            to_analyze.append((fp, incident))
        
        if not to_analyze:
            return {"success": True, "message": "All incidents already analyzed", "analyzed": 0}
        
        analyzed, failed = 0, 0
        # Increased limit for "all" coverage
        limit = min(100, len(to_analyze))
        
        for fp, incident in to_analyze[:limit]:
            try:
                analysis = await analyzer.analyze_incident(
                    incident=incident,
                    storage=storage,
                    force_regenerate=force,
                    system_context=system_context
                )
                if analysis:
                    analyzed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Failed to analyze {fp}: {e}")
                failed += 1
        
        return {
            "success": True,
            "analyzed": analyzed,
            "failed": failed,
            "remaining": max(0, len(to_analyze) - limit),
            "message": f"Analyzed {analyzed}/{limit} incidents"
        }
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")
        raise HTTPException(500, str(e))


@router.post("/vanguard/admin/incidents/resolve-all")
async def resolve_all_incidents(http_request: Request, request: ResolveAllRequest):
    """
    Resolve ALL active incidents.
    
    WARNING: This resolves every active incident. Requires confirm=true.
    """
    if not request.confirm:
        raise HTTPException(400, "Must set confirm=true to resolve all incidents")
    
    storage = get_incident_storage()
    fingerprints = await storage.list_incidents(limit=1000)
    
    resolved = []
    already_resolved = []
    failed = []
    
    for fp in fingerprints:
        try:
            incident = await storage.load(fp)
            if not incident:
                continue
            
            if incident.get("status") == "resolved":
                already_resolved.append(fp)
                continue
            
            success = await storage.resolve(fp)
            if success:
                resolved.append(fp)
            else:
                failed.append(fp)
        except Exception as e:
            failed.append({"fingerprint": fp, "reason": str(e)})
    
    logger.info(f"Resolve-all: {len(resolved)} resolved, {len(already_resolved)} already resolved, {len(failed)} failed")
    await audit.log(
        action="RESOLVE_ALL",
        request_id=http_request.headers.get("X-Request-ID", "unknown"),
        affected_ids=resolved,
        metadata={"resolution_notes": request.resolution_notes, "already_resolved": len(already_resolved)},
        result="SUCCESS" if not failed else "PARTIAL",
        ip_address=http_request.client.host if http_request.client else None,
    )
    
    return {
        "resolved_count": len(resolved),
        "already_resolved_count": len(already_resolved),
        "failed_count": len(failed),
        "resolution_notes": request.resolution_notes,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/vanguard/admin/learning/status")
async def get_learning_status():
    """Get status of resolution learning data."""
    try:
        learner = VanguardResolutionLearner()
        stats = learner.get_stats()
        
        return {
            "total_resolutions": stats["total_resolutions"],
            "verified_resolutions": stats["verified"],
            "pending_verification": stats["pending_verification"],
            "successful_patterns": stats["effective_fixes"],
            "patterns": [],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to get learning status: {e}")
        return {
            "error": str(e),
            "total_resolutions": 0,
            "verified_resolutions": 0,
            "pending_verification": 0,
            "successful_patterns": 0,
            "patterns": []
        }


@router.post("/vanguard/admin/learning/export")
async def export_learning_data():
    """Export all learning data for Vanguard Sovereign training."""
    try:
        learner = VanguardResolutionLearner()
        
        # Generate training data
        training_data = learner.export_for_sovereign_ai()
        
        return {
            "success": True,
            "training_data": training_data,
            "exported_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to export learning data: {e}")
        raise HTTPException(500, f"Export failed: {str(e)}")


# ========================
# Phase 2: Archive Endpoints
# ========================

@router.get("/vanguard/admin/archives")
async def list_archives():
    """List all incident archives with metadata."""
    try:
        from vanguard.archivist.archive_manager import get_archive_manager
        manager = get_archive_manager()
        archives = manager.list_archives()
        
        return {
            "total": len(archives),
            "archives": archives,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to list archives: {e}")
        return {"total": 0, "archives": [], "error": str(e)}


@router.get("/vanguard/admin/archives/{filename}")
async def get_archive(filename: str):
    """Load and return contents of a specific archive."""
    try:
        from vanguard.archivist.archive_manager import get_archive_manager
        manager = get_archive_manager()
        archive = await manager.load_archive(filename)
        
        if not archive:
            raise HTTPException(404, f"Archive not found: {filename}")
        
        return archive
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load archive {filename}: {e}")
        raise HTTPException(500, str(e))


@router.post("/vanguard/admin/archives/create")
async def create_archive():
    """Manually trigger archiving of resolved incidents."""
    try:
        from vanguard.archivist.archive_manager import get_archive_manager
        storage = get_incident_storage()
        manager = get_archive_manager()
        
        result = await manager.archive_resolved_incidents(storage)
        
        return {
            "success": True,
            **result,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to create archive: {e}")
        raise HTTPException(500, f"Archive creation failed: {str(e)}")


# ============================================================================
# AI ANALYSIS ENDPOINTS
# ============================================================================

# Initialize AI analyzer (uses lazy loading)
ai_analyzer = VanguardAIAnalyzer()


@router.get("/vanguard/admin/incidents/{fingerprint}/analysis")
async def get_incident_analysis(request: Request, fingerprint: str, regenerate: bool = False):
    """
    Get AI-generated analysis for an incident.
    """
    try:
        storage = get_incident_storage()
        incident = await storage.load(fingerprint)
        
        if not incident:
            raise HTTPException(404, f"Incident {fingerprint} not found")
        
        # Collect system context for AI confidence
        from vanguard.core.config import get_vanguard_config
        config = get_vanguard_config()
        
        # Get all registered routes
        routes = []
        for route in request.app.routes:
            if hasattr(route, "path"):
                routes.append(f"{list(route.methods) if hasattr(route, 'methods') else 'GET'} {route.path}")

        system_context = {
            "mode": config.mode.value,
            "revision": os.getenv("K_REVISION", "local"),
            "routes": routes[:50] # Limit to top 50 routes
        }
        
        # Generate or retrieve analysis
        from vanguard.ai.ai_analyzer import get_ai_analyzer
        analyzer = get_ai_analyzer()
        
        analysis = await analyzer.analyze_incident(
            incident=incident,
            storage=storage,
            force_regenerate=regenerate,
            system_context=system_context
        )
        
        return analysis.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI analysis failed for {fingerprint}: {e}")
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.post("/vanguard/admin/resolve/{fingerprint}")
async def resolve_incident_with_approval(fingerprint: str, body: ResolveRequest):
    """
    Resolve incident with manual approval.
    
    IMPORTANT: This now requires explicit approval via the 'approved' field.
    The AI will suggest readiness, but human approval is mandatory.
    
    Args:
        fingerprint: Incident to resolve
        body: Must include approved=true
    
    Returns:
        Resolution status
    """
    try:
        # Require explicit approval
        if not body.approved:
            raise HTTPException(
                400,
                "Manual approval required. Set 'approved': true to resolve."
            )
        
        storage = get_incident_storage()
        incident = await storage.load(fingerprint)
        
        if not incident:
            raise HTTPException(404, f"Incident {fingerprint} not found")
        
        # Get AI analysis for record keeping
        try:
            analysis = await ai_analyzer.analyze_incident(incident, storage)
            ai_confidence = analysis.confidence
            ai_recommendation = analysis.ready_to_resolve
        except Exception as e:
            logger.warning(f"Could not get AI analysis during resolution: {e}")
            ai_confidence = 0
            ai_recommendation = False
        
        # Record resolution with learning
        learner = VanguardResolutionLearner()
        await learner.record_resolution(
            incident=incident,
            resolution_notes=body.resolution_notes or "Manually approved from Control Room",
            metadata={
                "ai_confidence": ai_confidence,
                "ai_recommended": ai_recommendation,
                "approved_by": "admin_ui"
            }
        )
        
        # Mark as resolved
        await storage.resolve(fingerprint)

        logger.info(f"Incident {fingerprint} resolved (approval confirmed)")
        
        return {
            "success": True,
            "message": "Incident resolved and added to learning corpus",
            "fingerprint": fingerprint,
            "ai_confidence": ai_confidence,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve {fingerprint}: {e}")
        raise HTTPException(500, f"Resolution failed: {str(e)}")


@router.post("/vanguard/admin/incidents/{fingerprint}/analyze")
async def regenerate_incident_analysis(request: Request, fingerprint: str):
    """
    Force-regenerate AI analysis for an incident, bypassing the 24h cache.
    Equivalent to GET /analysis?regenerate=True but callable via POST
    (used by the Regenerate button in VanguardControlRoom).
    """
    return await get_incident_analysis(request, fingerprint, regenerate=True)


@router.post("/vanguard/admin/resolve/bulk")
async def bulk_resolve_incidents_compat(request: BulkResolveRequest):
    """
    Path alias for deployed-bundle compatibility.
    The deployed bundle POSTs to /vanguard/admin/resolve/bulk;
    the canonical endpoint is /vanguard/admin/incidents/bulk-resolve.
    Both call the same handler.
    """
    return await bulk_resolve_incidents(request)


@router.get("/vanguard/admin/incidents/{fingerprint}/verification")
async def get_verification_status(fingerprint: str):
    """
    Get verification status for a resolved incident.
    
    Returns:
        - verified: bool - Whether the fix has been confirmed
        - status: 'success' | 'failed' | 'pending'
        - reasoning: Explanation of current status
        - code_changed: Whether referenced files were modified
        - new_occurrences: Count of new errors since resolution
    """
    try:
        storage = get_incident_storage()
        incident = await storage.load(fingerprint)
        
        if not incident:
            raise HTTPException(404, f"Incident {fingerprint} not found")
        
        # Check if resolved
        if incident.get("status") != "resolved":
            return {
                "verified": False,
                "status": "pending",
                "reasoning": "Incident not yet marked as resolved",
                "code_changed": False,
                "new_occurrences": 0
            }
        
        resolved_at = incident.get("resolved_at") or incident.get("last_seen")
        
        # Try to use ResolutionVerifier if available
        try:
            from vanguard.services.resolution_verifier import ResolutionVerifier
            from vanguard.services.github_context import GitHubContextFetcher
            
            github_fetcher = GitHubContextFetcher()
            verifier = ResolutionVerifier(github_fetcher, storage)
            
            # Get the analysis for code references
            try:
                analysis = await ai_analyzer.analyze_incident(incident, storage)
                analysis_dict = {"code_references": analysis.code_references or []}
            except Exception:
                analysis_dict = {"code_references": []}
            
            result = await verifier.verify_resolution(incident, analysis_dict)
            return result
            
        except ImportError:
            return {
                "verified": False,
                "status": "pending",
                "reasoning": "Verification service not available - monitoring manually",
                "code_changed": False,
                "new_occurrences": 0
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification check failed for {fingerprint}: {e}")
        raise HTTPException(500, f"Verification failed: {str(e)}")


# ============================================================================
# VACCINE ENDPOINTS — AI-Powered Code Fix Generation
# ============================================================================

@router.get("/vanguard/admin/incidents/{fingerprint}/vaccine-plan")
async def get_vaccine_plan(fingerprint: str):
    """
    Generate a structured remediation plan for an incident using Vaccine PlanEngine.

    Returns root-cause classification, fix candidates (files/functions),
    risk score, verification steps, and rollback plan.
    Does NOT write any code — purely analytical.
    """
    try:
        from vanguard.vaccine.plan_engine import get_plan_engine

        storage = get_incident_storage()
        incident = await storage.load(fingerprint)

        if not incident:
            raise HTTPException(404, f"Incident {fingerprint} not found")

        plan_engine = get_plan_engine()
        plan = plan_engine.generate_plan(incident)

        return {
            "fingerprint": fingerprint,
            "plan": plan.to_dict(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vaccine plan generation failed for {fingerprint}: {e}")
        raise HTTPException(500, f"Plan generation failed: {str(e)}")


@router.post("/vanguard/admin/incidents/{fingerprint}/vaccine-generate")
async def generate_vaccine_fix(fingerprint: str):
    """
    Use VaccineGenerator to produce a concrete code patch for an incident.

    Requires:
      - AI analysis cached on the incident (run /analysis first)
      - confidence >= 85 in the analysis
      - At least one code_reference pointing to a patchable file

    Returns:
      - The generated CodePatch (file_path, original_code, fixed_code, explanation)
      - Or a structured explanation of why it was skipped/not feasible
    """
    try:
        from vanguard.vaccine.generator import get_vaccine

        storage = get_incident_storage()
        incident = await storage.load(fingerprint)

        if not incident:
            raise HTTPException(404, f"Incident {fingerprint} not found")

        # Pull cached AI analysis off the incident
        ai_analysis = incident.get("ai_analysis")
        if not ai_analysis:
            raise HTTPException(
                400,
                "No AI analysis found for this incident. "
                "Run GET /vanguard/admin/incidents/{fingerprint}/analysis first.",
            )

        # Merge incident context into analysis dict for generator
        analysis_dict = {
            **ai_analysis,
            "fingerprint": fingerprint,
            "error_type": incident.get("error_type", ""),
            "error_message": incident.get("error_message", ""),
            "endpoint": incident.get("endpoint", ""),
        }

        vaccine = get_vaccine()
        can_gen, reason = await vaccine.can_generate_fix(analysis_dict)

        if not can_gen:
            return {
                "fingerprint": fingerprint,
                "generated": False,
                "skip_reason": reason,
                "vaccine_status": vaccine.get_status(),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        patch = await vaccine.generate_fix(analysis_dict)

        if not patch:
            return {
                "fingerprint": fingerprint,
                "generated": False,
                "skip_reason": "Vaccine generated no patch (low confidence or no code refs)",
                "vaccine_status": vaccine.get_status(),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        return {
            "fingerprint": fingerprint,
            "generated": True,
            "patch": {
                "file_path": patch.file_path,
                "line_start": patch.line_start,
                "line_end": patch.line_end,
                "explanation": patch.explanation,
                "confidence": patch.confidence,
                "original_code": patch.original_code[:2000],   # truncate for transport
                "fixed_code": patch.fixed_code[:2000],
            },
            "vaccine_status": vaccine.get_status(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vaccine generate failed for {fingerprint}: {e}")
        raise HTTPException(500, f"Vaccine generation failed: {str(e)}")


@router.post("/vanguard/admin/vaccine/run-now")
async def trigger_vaccine_run():
    """
    Manually trigger an immediate full vaccine cycle.

    Scans ALL active incidents, runs AI analysis on any missing it,
    then attempts to generate and store a code patch for each one.
    Also fires all pending chaos scenarios immediately.

    Returns a full run report showing what was analyzed, patched, and skipped.
    """
    import asyncio
    from vanguard.vaccine.generator import get_vaccine
    from vanguard.ai.ai_analyzer import VanguardAIAnalyzer

    run_start = datetime.utcnow()
    report = {
        "triggered_at": run_start.isoformat() + "Z",
        "incidents_scanned": 0,
        "analyzed": [],
        "patched": [],
        "skipped": [],
        "chaos_scenarios_fired": [],
        "errors": [],
    }

    try:
        storage = get_incident_storage()
        vaccine = get_vaccine()
        analyzer = VanguardAIAnalyzer()

        # ── Step 1: Load all active incidents ─────────────────────────────────
        fingerprints = await storage.list_incidents(limit=200)
        active_incidents = []
        for fp in fingerprints:
            inc = await storage.load(fp)
            if inc and inc.get("status") == "active":
                active_incidents.append(inc)

        report["incidents_scanned"] = len(active_incidents)
        logger.info(f"[VACCINE-RUN] Scanning {len(active_incidents)} active incidents")

        # ── Step 2: For each incident — ensure AI analysis, then generate fix ─
        for incident in active_incidents:
            fp = incident.get("fingerprint", "unknown")
            try:
                # Run AI analysis if not already cached
                ai_analysis = incident.get("ai_analysis")
                if not ai_analysis or not isinstance(ai_analysis, dict) or not ai_analysis.get("root_cause"):
                    try:
                        ai_result = await analyzer.analyze(incident)
                        if ai_result:
                            ai_analysis = {
                                "summary": ai_result.summary,
                                "root_cause": ai_result.root_cause,
                                "recommendation": ai_result.recommendation,
                                "confidence": ai_result.confidence,
                                "code_references": [r.__dict__ if hasattr(r, '__dict__') else r
                                                    for r in (ai_result.code_references or [])],
                                "vaccine_recommendation": ai_result.vaccine_recommendation,
                            }
                            await storage.update_incident(fp, {"ai_analysis": ai_analysis})
                            report["analyzed"].append(fp)
                    except Exception as ae:
                        report["errors"].append({"fingerprint": fp, "stage": "analysis", "error": str(ae)})
                        continue

                if not ai_analysis:
                    report["skipped"].append({"fingerprint": fp, "reason": "No AI analysis available"})
                    continue

                # Build analysis dict for vaccine
                analysis_dict = {
                    **ai_analysis,
                    "fingerprint": fp,
                    "error_type": incident.get("error_type", ""),
                    "error_message": incident.get("error_message", ""),
                    "endpoint": incident.get("endpoint", ""),
                }

                # Check eligibility
                can_gen, reason = await vaccine.can_generate_fix(analysis_dict)
                if not can_gen:
                    report["skipped"].append({"fingerprint": fp, "reason": reason})
                    continue

                # Generate patch
                patch = await vaccine.generate_fix(analysis_dict)
                if patch:
                    # Store patch on the incident for visibility in UI
                    await storage.update_incident(fp, {
                        "vaccine_patch": {
                            "file_path": patch.file_path,
                            "line_start": patch.line_start,
                            "line_end": patch.line_end,
                            "explanation": patch.explanation,
                            "confidence": patch.confidence,
                            "generated_at": datetime.utcnow().isoformat() + "Z",
                            "original_code": patch.original_code[:500],
                            "fixed_code": patch.fixed_code[:500],
                        }
                    })
                    report["patched"].append({
                        "fingerprint": fp,
                        "file": patch.file_path,
                        "confidence": patch.confidence,
                    })
                    logger.info(f"[VACCINE-RUN] Patched {fp} → {patch.file_path} ({patch.confidence:.0f}%)")
                else:
                    report["skipped"].append({"fingerprint": fp, "reason": "Patch generation returned None"})

            except Exception as e:
                report["errors"].append({"fingerprint": fp, "stage": "vaccine", "error": str(e)})
                logger.warning(f"[VACCINE-RUN] Error on {fp}: {e}")

        # ── Step 3: Fire chaos scenarios immediately ───────────────────────────
        try:
            from vanguard.vaccine.chaos_scheduler import ChaosScheduler
            scheduler = ChaosScheduler()
            scenarios = scheduler.scenarios
            for scenario in scenarios:
                asyncio.create_task(scheduler._run_scenario(scenario))
                report["chaos_scenarios_fired"].append(scenario)
            logger.info(f"[VACCINE-RUN] Fired {len(scenarios)} chaos scenarios")
        except Exception as ce:
            report["errors"].append({"stage": "chaos", "error": str(ce)})

        report["duration_ms"] = int((datetime.utcnow() - run_start).total_seconds() * 1000)
        report["vaccine_status"] = vaccine.get_status()

        logger.info(
            f"[VACCINE-RUN] Complete — "
            f"scanned={report['incidents_scanned']}, "
            f"analyzed={len(report['analyzed'])}, "
            f"patched={len(report['patched'])}, "
            f"skipped={len(report['skipped'])}, "
            f"errors={len(report['errors'])}"
        )
        return report

    except Exception as e:
        logger.error(f"[VACCINE-RUN] Fatal: {e}")
        report["fatal_error"] = str(e)
        report["duration_ms"] = int((datetime.utcnow() - run_start).total_seconds() * 1000)
        return report




@router.get("/vanguard/admin/audit")
async def get_audit_log(limit: int = 100, action: Optional[str] = None):
    """
    Query the audit log. Returns recent admin actions.

    Query params:
        limit: Maximum entries to return (default 100)
        action: Filter by action type (e.g., RESOLVE_INCIDENT, TOGGLE_MODE)
    """
    try:
        storage = get_incident_storage()

        filters = []
        if action:
            filters.append(("action", "==", action.upper()))

        entries = await storage.query_collection(
            collection="audit_log",
            limit=limit,
            filters=filters if filters else None,
            order_by=[("timestamp_utc", "desc")],
        )

        return {
            "entries": entries,
            "total": len(entries),
            "filter": {"action": action} if action else None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.error(f"Audit log query failed: {e}")
        return {"entries": [], "total": 0, "error": str(e)}


# ── Vaccine Definitions ────────────────────────────────────────────────────────

@router.get("/vanguard/admin/vaccines")
async def list_vaccine_definitions():
    """
    Return all active vaccine definitions generated by the VaccineGenerator / Surgeon.
    VaccinePanel.tsx calls this to display deployed remediations.
    """
    try:
        from vanguard.vaccine.generator import get_vaccine
        vaccine = get_vaccine()

        # Pull the vaccine's internal pending / applied fix history as "definitions"
        definitions = []
        history = getattr(vaccine, 'fix_history', [])
        for i, fix in enumerate(history[-20:]):  # Last 20
            definitions.append({
                "id": fix.get("fix_id", f"VACCINE-{i+100:03d}"),
                "name": fix.get("description", "Auto-generated fix"),
                "description": fix.get("reasoning", "Surgeon-generated remediation applied via AOT patching."),
                "status": "ACTIVE" if fix.get("applied") else "DRAFT",
                "deployment_date": fix.get("applied_at", fix.get("created_at", "")),
                "target_pattern": fix.get("target_file", "unknown"),
                "hit_count": fix.get("hit_count", 1),
            })

        return {"vaccines": definitions, "total": len(definitions)}

    except Exception as e:
        logger.warning(f"Vaccine definitions unavailable: {e}")
        # Return empty list — VaccinePanel shows a static VACCINE-001 card regardless
        return {"vaccines": [], "total": 0, "message": str(e)}


# ── Learning Export History ────────────────────────────────────────────────────

@router.get("/vanguard/admin/learning/export-history")
async def get_learning_export_history():
    """
    Return history of knowledge base exports.
    VanguardLearningExport.tsx polls this for the 'Recent Exports' table.
    """
    try:
        from vanguard.resolution_learner import VanguardResolutionLearner
        storage = get_incident_storage()
        learner = VanguardResolutionLearner(storage)

        # Check if learner tracks export history
        exports = []
        if hasattr(learner, 'export_history'):
            exports = learner.export_history or []
        else:
            # Try querying Firestore/file export log directly
            try:
                docs = await storage.query_collection(
                    collection="vanguard_export_log",
                    order_by=[("timestamp", "desc")],
                    limit=20,
                )
                exports = [
                    {
                        "timestamp": d.get("timestamp", ""),
                        "file_name": d.get("file_name", f"export_{d.get('timestamp', 'unknown')}.jsonl"),
                        "size_mb": round(d.get("size_bytes", 0) / 1_048_576, 3),
                        "record_count": d.get("record_count", 0),
                    }
                    for d in docs
                ]
            except Exception:
                exports = []

        return {"exports": exports, "total": len(exports)}

    except Exception as e:
        logger.warning(f"Export history unavailable: {e}")
        return {"exports": [], "total": 0, "message": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# VACCINE LIVE STREAM + AUDIT
# ═══════════════════════════════════════════════════════════════════════════════

import json
import asyncio
import aiofiles
from pathlib import Path
from fastapi.responses import StreamingResponse


# Where audit files are stored on the server's filesystem
def _vaccine_run_dir() -> Path:
    """Resolve the directory for vaccine run audit files."""
    candidates = [
        Path("/app/data/vaccine_runs"),               # Cloud Run
        Path(__file__).resolve().parents[3] / "data" / "vaccine_runs",  # local dev
    ]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    fallback = Path("/tmp/vaccine_runs")
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _emit(event_type: str, payload: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


@router.get("/vanguard/admin/vaccine/run-stream")
async def vaccine_run_stream(request: Request):
    """
    SSE endpoint: triggers a full vaccine cycle and streams live JSON events.

    Event types emitted:
      log     — { level, msg, detail?, fingerprint?, file?, confidence?, progress }
      summary — { incidents_scanned, analyzed, patched, skipped, errors, chaos_fired, duration_ms }
      done    — {} (stream teardown signal)

    On completion, a rich audit file is saved to /data/vaccine_runs/{run_id}.json
    capturing who triggered it, all incident actions, and every patch generated.
    Fetch via GET /vanguard/admin/vaccine/run-history/{run_id}.
    """
    from vanguard.vaccine.generator import get_vaccine
    from vanguard.ai.ai_analyzer import VanguardAIAnalyzer
    import socket

    run_id = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
    run_start = datetime.utcnow()

    # ── Capture full request context for audit trail ───────────────────────────
    headers = dict(request.headers)
    client_ip = (
        headers.get("x-forwarded-for", "").split(",")[0].strip()
        or headers.get("x-real-ip", "")
        or (request.client.host if request.client else "unknown")
    )
    triggered_by = {
        "ip":               client_ip,
        "forwarded_for":   headers.get("x-forwarded-for", None),
        "user_agent":      headers.get("user-agent", "unknown"),
        "referer":         headers.get("referer", headers.get("referrer", None)),
        "host":            headers.get("host", None),
        "accept_language": headers.get("accept-language", None),
        "origin":          headers.get("origin", None),
        "method":          request.method,
        "url":             str(request.url),
        "timestamp_utc":   run_start.isoformat() + "Z",
        "server_hostname": socket.gethostname(),
        "server_env":      os.getenv("K_SERVICE", os.getenv("ENVIRONMENT", "local")),
    }

    # Accumulated audit log (stored to file on completion)
    audit_log: list[dict] = []
    patches_saved: list[dict] = []
    incident_snapshots: list[dict] = []  # per-incident audit records

    # Counters
    stats = {"scanned": 0, "analyzed": 0, "patched": 0, "skipped": 0, "errors": 0, "chaos": 0}

    async def stream():
        nonlocal audit_log, patches_saved, stats

        def make_event(level: str, msg: str, **extra) -> dict:
            # Use full ISO timestamp in the stored log, short HH:MM:SS for display
            now = datetime.utcnow()
            entry = {
                "level": level,
                "msg": msg,
                "ts": now.strftime("%H:%M:%S"),          # display
                "ts_iso": now.isoformat() + "Z",         # audit precision
                **{k: v for k, v in extra.items() if v is not None},
            }
            audit_log.append(entry)
            return entry

        try:
            # ── Phase 0: Init ──────────────────────────────────────────────────
            ev = make_event("info", f"Vaccine cycle {run_id} starting...",
                            progress=2, detail=f"run_id={run_id}")
            yield _emit("log", ev)

            storage = get_incident_storage()
            vaccine = get_vaccine()
            analyzer = VanguardAIAnalyzer()

            vac_status = vaccine.get_status()
            ev = make_event("info",
                            f"Vaccine v{vac_status['version']} loaded — "
                            f"daily fixes used {vac_status['daily_fixes']}/{vac_status['daily_limit']}, "
                            f"min confidence {vac_status['min_confidence']}%",
                            progress=5)
            yield _emit("log", ev)

            if not vac_status["enabled"]:
                ev = make_event("warn",
                                "VANGUARD_VACCINE_ENABLED=false — patches will be DRY-RUN only.",
                                progress=5)
                yield _emit("log", ev)

            # ── Phase 1: Scan active incidents ────────────────────────────────
            ev = make_event("scan", "Fetching all active incidents from storage...", progress=8)
            yield _emit("log", ev)

            fingerprints = await storage.list_incidents(limit=200)
            active = []
            for fp in fingerprints:
                if await request.is_disconnected():
                    return
                inc = await storage.load(fp)
                if inc and inc.get("status") == "active":
                    active.append(inc)

            stats["scanned"] = len(active)
            ev = make_event("scan",
                            f"Found {len(active)} active incident(s) to process.",
                            progress=12)
            yield _emit("log", ev)

            if not active:
                ev = make_event("done", "No active incidents — vaccine cycle complete.", progress=100)
                yield _emit("log", ev)
                yield _emit("summary", {**stats, "duration_ms": 0})
                yield _emit("done", {})
                return

            # ── Phase 2: Per-incident loop ────────────────────────────────────
            total = len(active)
            for idx, incident in enumerate(active):
                if await request.is_disconnected():
                    return

                fp = incident.get("fingerprint", "unknown")
                title = incident.get("title", incident.get("error_type", "Unknown Error"))
                base_progress = 15 + int((idx / total) * 70)

                # Build this incident's audit snapshot — enriched step by step below
                inc_snapshot = {
                    "index":            idx + 1,
                    "fingerprint":      fp,
                    "title":            title,
                    "error_type":       incident.get("error_type", ""),
                    "error_message":    incident.get("error_message", ""),
                    "endpoint":         incident.get("endpoint", ""),
                    "occurrence_count": incident.get("occurrence_count", 1),
                    "severity":         incident.get("severity", "unknown"),
                    "first_seen":       incident.get("first_seen", ""),
                    "last_seen":        incident.get("last_seen", ""),
                    "stacktrace_lines": len((incident.get("stacktrace") or "").splitlines()),
                    "action_taken":     "pending",
                    "ai_confidence":    None,
                    "ai_root_cause":    None,
                    "patch_file":       None,
                    "patch_confidence": None,
                    "skip_reason":      None,
                    "error_detail":     None,
                    "processed_at":     datetime.utcnow().isoformat() + "Z",
                }

                ev = make_event(
                    "incident",
                    f"[{idx+1}/{total}] Incident: {title}",
                    fingerprint=fp,
                    progress=base_progress,
                    detail=(
                        f"type={incident.get('error_type','?')} "
                        f"count={incident.get('occurrence_count',1)} "
                        f"endpoint={incident.get('endpoint','?')} "
                        f"severity={incident.get('severity','?')}"
                    )
                )
                yield _emit("log", ev)

                # ── 2a: AI analysis ──────────────────────────────────────────
                ai_analysis = incident.get("ai_analysis")
                has_analysis = (
                    isinstance(ai_analysis, dict)
                    and ai_analysis.get("root_cause")
                    and ai_analysis.get("confidence", 0) > 0
                )

                if not has_analysis:
                    ev = make_event("analysis",
                                   f"Running Gemini analysis on '{title}'...",
                                   fingerprint=fp, progress=base_progress + 2)
                    yield _emit("log", ev)
                    try:
                        ai_result = await analyzer.analyze(incident)
                        if ai_result:
                            ai_analysis = {
                                "summary":                ai_result.summary,
                                "root_cause":             ai_result.root_cause,
                                "recommendation":         ai_result.recommendation,
                                "confidence":             ai_result.confidence,
                                "code_references":        [
                                    r.__dict__ if hasattr(r, "__dict__") else r
                                    for r in (ai_result.code_references or [])
                                ],
                                "vaccine_recommendation": ai_result.vaccine_recommendation,
                                "error_type":             incident.get("error_type", ""),
                                "error_message":          incident.get("error_message", ""),
                            }
                            await storage.update_incident(fp, {"ai_analysis": ai_analysis})
                            stats["analyzed"] += 1
                            inc_snapshot["ai_confidence"] = ai_result.confidence
                            inc_snapshot["ai_root_cause"] = ai_result.root_cause
                            ev = make_event(
                                "analysis",
                                f"AI analysis complete — confidence {ai_result.confidence}% — "
                                f"root cause: {ai_result.root_cause[:120]}",
                                fingerprint=fp,
                                confidence=ai_result.confidence,
                                progress=base_progress + 5,
                                detail=f"recommendation: {ai_result.recommendation[:200]}"
                            )
                            yield _emit("log", ev)
                        else:
                            ev = make_event("warn", "Gemini returned no analysis.",
                                           fingerprint=fp, progress=base_progress + 5)
                            yield _emit("log", ev)
                    except Exception as ae:
                        stats["errors"] += 1
                        ev = make_event("error", f"Analysis failed: {ae}",
                                       fingerprint=fp, progress=base_progress + 5)
                        yield _emit("log", ev)
                        continue
                else:
                    ev = make_event("analysis",
                                   f"Using cached AI analysis — confidence {ai_analysis.get('confidence',0)}%",
                                   fingerprint=fp,
                                   confidence=ai_analysis.get("confidence", 0),
                                   progress=base_progress + 3)
                    yield _emit("log", ev)
                    inc_snapshot["ai_confidence"] = ai_analysis.get("confidence", 0)
                    inc_snapshot["ai_root_cause"] = ai_analysis.get("root_cause", "")

                if not ai_analysis:
                    stats["skipped"] += 1
                    ev = make_event("skip", "No AI analysis available — skipping.",
                                   fingerprint=fp, progress=base_progress + 6)
                    yield _emit("log", ev)
                    continue

                # ── 2b: Vaccine eligibility gate ─────────────────────────────
                analysis_dict = {
                    **ai_analysis,
                    "fingerprint":   fp,
                    "error_type":    incident.get("error_type", ""),
                    "error_message": incident.get("error_message", ""),
                    "endpoint":      incident.get("endpoint", ""),
                    "stacktrace":    incident.get("stacktrace", ""),
                }
                can_gen, reason = await vaccine.can_generate_fix(analysis_dict)
                ev = make_event(
                    "info" if can_gen else "skip",
                    f"Gate check: {'✅ ELIGIBLE' if can_gen else f'⛔ SKIP — {reason}'}",
                    fingerprint=fp,
                    progress=base_progress + 8,
                    detail=reason if not can_gen else None,
                )
                yield _emit("log", ev)

                if not can_gen:
                    stats["skipped"] += 1
                    inc_snapshot["action_taken"] = "skipped"
                    inc_snapshot["skip_reason"] = reason
                    incident_snapshots.append(inc_snapshot)
                    continue

                # ── 2c: Generate patch ───────────────────────────────────────
                code_refs = ai_analysis.get("code_references", [])
                primary_file = (code_refs[0].get("file") if isinstance(code_refs[0], dict) else str(code_refs[0])) if code_refs else "unknown"
                ev = make_event("patch",
                               f"Calling Gemini to generate surgical fix for {primary_file}...",
                               fingerprint=fp, file=primary_file, progress=base_progress + 12)
                yield _emit("log", ev)

                try:
                    patch = await vaccine.generate_fix(analysis_dict)
                    if patch:
                        # Save patch to incident
                        patch_record = {
                            "file_path":     patch.file_path,
                            "line_start":    patch.line_start,
                            "line_end":      patch.line_end,
                            "explanation":   patch.explanation,
                            "confidence":    patch.confidence,
                            "generated_at":  datetime.utcnow().isoformat() + "Z",
                            "original_code": patch.original_code[:500],
                            "fixed_code":    patch.fixed_code[:500],
                        }
                        await storage.update_incident(fp, {"vaccine_patch": patch_record})

                        # Save full patch to audit log
                        patches_saved.append({
                            "fingerprint": fp,
                            "title":       title,
                            **patch_record,
                            # Full code for audit (not truncated)
                            "original_code_full": patch.original_code,
                            "fixed_code_full":    patch.fixed_code,
                        })

                        stats["patched"] += 1
                        inc_snapshot["action_taken"] = "patched"
                        inc_snapshot["patch_file"] = patch.file_path
                        inc_snapshot["patch_confidence"] = patch.confidence
                        inc_snapshot["patch_lines"] = f"{patch.line_start}-{patch.line_end}"
                        ev = make_event(
                            "patch",
                            f"✅ Patch generated — {patch.file_path}:{patch.line_start}-{patch.line_end} "
                            f"({patch.confidence:.0f}% confidence)",
                            fingerprint=fp,
                            file=patch.file_path,
                            confidence=patch.confidence,
                            progress=base_progress + 18,
                            detail=patch.explanation[:200],
                        )
                        yield _emit("log", ev)
                    else:
                        stats["skipped"] += 1
                        inc_snapshot["action_taken"] = "skipped"
                        inc_snapshot["skip_reason"] = "Patch generation returned None"
                        ev = make_event("skip",
                                       "Vaccine returned no patch (confidence or references insufficient).",
                                       fingerprint=fp, progress=base_progress + 18)
                        yield _emit("log", ev)
                except Exception as pe:
                    stats["errors"] += 1
                    inc_snapshot["action_taken"] = "error"
                    inc_snapshot["error_detail"] = str(pe)
                    ev = make_event("error", f"Patch generation failed: {pe}",
                                   fingerprint=fp, progress=base_progress + 18)
                    yield _emit("log", ev)

                incident_snapshots.append(inc_snapshot)

            # ── Phase 3: Chaos scenarios ──────────────────────────────────────
            ev = make_event("chaos", "Firing chaos validation scenarios...", progress=88)
            yield _emit("log", ev)
            try:
                from vanguard.vaccine.chaos_scheduler import ChaosScheduler
                scheduler = ChaosScheduler()
                for scenario in scheduler.scenarios:
                    asyncio.create_task(scheduler._run_scenario(scenario))
                    stats["chaos"] += 1
                    ev = make_event("chaos", f"⚡ Scenario fired: {scenario}", progress=90)
                    yield _emit("log", ev)
            except Exception as ce:
                ev = make_event("warn", f"Chaos scheduler unavailable: {ce}", progress=90)
                yield _emit("log", ev)

            # ── Phase 4: Save audit file ──────────────────────────────────────
            duration_ms = int((datetime.utcnow() - run_start).total_seconds() * 1000)
            ev = make_event("info", f"Saving audit file {run_id}.json...", progress=95)
            yield _emit("log", ev)

            try:
                audit_file = _vaccine_run_dir() / f"{run_id}.json"
                audit_doc = {
                    # ── Identity ──────────────────────────────────────────────
                    "run_id":         run_id,
                    "schema_version": "2.0",

                    # ── Who triggered it ──────────────────────────────────────
                    "triggered_by": triggered_by,

                    # ── Timeline ──────────────────────────────────────────────
                    "triggered_at":  run_start.isoformat() + "Z",
                    "completed_at":  datetime.utcnow().isoformat() + "Z",
                    "duration_ms":   duration_ms,

                    # ── Summary counts ────────────────────────────────────────
                    "summary": {
                        "incidents_scanned": stats["scanned"],
                        "analyzed":          stats["analyzed"],
                        "patched":           stats["patched"],
                        "skipped":           stats["skipped"],
                        "errors":            stats["errors"],
                        "chaos_fired":       stats["chaos"],
                    },

                    # ── Per-incident audit records ────────────────────────────
                    "incidents": incident_snapshots,

                    # ── Full patch code for auditing ──────────────────────────
                    "patches": patches_saved,

                    # ── Chronological event log ───────────────────────────────
                    "log": audit_log,

                    # ── System state at time of run ───────────────────────────
                    "vaccine_status": vaccine.get_status(),
                    "environment": {
                        "service":    os.getenv("K_SERVICE", "local"),
                        "revision":   os.getenv("K_REVISION", "local"),
                        "region":     os.getenv("K_REGION",   "unknown"),
                        "project":    os.getenv("GOOGLE_CLOUD_PROJECT", "unknown"),
                        "python_ver": __import__('sys').version.split()[0],
                    },
                }
                async with aiofiles.open(audit_file, "w") as f:
                    await f.write(json.dumps(audit_doc, indent=2, default=str))

                ev = make_event(
                    "info",
                    f"Audit saved → {audit_file.name} "
                    f"({audit_file.stat().st_size / 1024:.1f} KB)",
                    progress=98,
                    detail=str(audit_file),
                )
                yield _emit("log", ev)
            except Exception as se:
                ev = make_event("warn", f"Audit save failed: {se}", progress=98)
                yield _emit("log", ev)

            # ── Phase 5: Summary ──────────────────────────────────────────────
            ev = make_event(
                "done",
                f"Vaccine cycle complete — "
                f"{stats['patched']} patch(es) generated, "
                f"{stats['analyzed']} analyzed, "
                f"{stats['skipped']} skipped, "
                f"{stats['errors']} error(s) — "
                f"{duration_ms / 1000:.1f}s total",
                progress=100,
            )
            yield _emit("log", ev)

            yield _emit("summary", {
                "run_id":            run_id,
                "incidents_scanned": stats["scanned"],
                "analyzed":          stats["analyzed"],
                "patched":           stats["patched"],
                "skipped":           stats["skipped"],
                "errors":            stats["errors"],
                "chaos_fired":       stats["chaos"],
                "duration_ms":       duration_ms,
            })
            yield _emit("done", {"run_id": run_id})

        except Exception as fatal:
            logger.error(f"[VACCINE-STREAM] Fatal: {fatal}")
            ev = {"level": "error", "msg": f"Fatal: {fatal}", "ts": datetime.utcnow().strftime("%H:%M:%S")}
            yield _emit("log", ev)
            yield _emit("done", {"error": str(fatal)})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",
            "Connection":         "keep-alive",
        },
    )


# ── Audit File History ─────────────────────────────────────────────────────────

@router.get("/vanguard/admin/vaccine/run-history")
async def get_vaccine_run_history():
    """
    List all saved vaccine run audit files, newest first.
    Each entry: { run_id, triggered_at, duration_ms, summary, size_bytes }.
    """
    try:
        run_dir = _vaccine_run_dir()
        files = sorted(run_dir.glob("run_*.json"), reverse=True)
        history = []
        for f in files[:50]:  # cap at 50 entries
            try:
                raw = f.read_text(encoding="utf-8")
                doc = json.loads(raw)
                history.append({
                    "run_id":       doc.get("run_id", f.stem),
                    "triggered_at": doc.get("triggered_at", ""),
                    "completed_at": doc.get("completed_at", ""),
                    "duration_ms":  doc.get("duration_ms", 0),
                    "summary":      doc.get("summary", {}),
                    "size_bytes":   f.stat().st_size,
                    "patch_count":  len(doc.get("patches", [])),
                })
            except Exception:
                history.append({"run_id": f.stem, "error": "unreadable"})
        return {"runs": history, "total": len(history)}
    except Exception as e:
        logger.error(f"Run history failed: {e}")
        return {"runs": [], "total": 0, "error": str(e)}


@router.get("/vanguard/admin/vaccine/run-history/{run_id}")
async def get_vaccine_run_detail(run_id: str):
    """
    Fetch a specific vaccine run audit file by run_id.
    Returns full log, summary, and patches for frontend auditing.
    """
    try:
        # Sanitize to prevent path traversal
        safe_id = run_id.replace("/", "").replace("..", "")
        run_dir = _vaccine_run_dir()
        audit_file = run_dir / f"{safe_id}.json"

        if not audit_file.exists():
            raise HTTPException(404, f"Run {run_id} not found")

        async with aiofiles.open(audit_file, "r") as f:
            content = await f.read()
        return json.loads(content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Run detail failed: {e}")
        raise HTTPException(500, str(e))


# ── Codebase Knowledge Base Status & Control ──────────────────────────────────

@router.get("/vanguard/admin/vaccine/kb-status")
async def get_kb_status():
    """
    Return the state of the Codebase Knowledge Base used to ground Gemini prompts.
    VaccinePanel reads this to show KB health and allow manual rebuilds.
    """
    try:
        from vanguard.vaccine import codebase_kb as _kb_mod
        from vanguard.vaccine.codebase_kb import get_codebase_context

        if _kb_mod._KB_CACHE is None:
            await get_codebase_context()

        now   = datetime.utcnow()
        built = _kb_mod._KB_BUILT_AT.replace(tzinfo=None) if _kb_mod._KB_BUILT_AT else None
        age_s = int((now - built).total_seconds()) if built else None
        stale = age_s is None or age_s > _kb_mod._KB_TTL_SECONDS

        kb = _kb_mod._KB_CACHE or {}
        return {
            "built":          kb.get("built_at"),
            "age_seconds":    age_s,
            "stale":          stale,
            "ttl_seconds":    _kb_mod._KB_TTL_SECONDS,
            "module_count":   kb.get("module_count", 0),
            "route_count":    kb.get("route_count", 0),
            "collection_count": kb.get("collection_count", len(kb.get("firestore_collections", []))),
            "router_mount_count": len(kb.get("router_mounts", [])),
            "dep_count":      len(kb.get("dependencies", [])),
            "root":           kb.get("root", "unknown"),
            "schema_version": kb.get("schema_version", "unknown"),
            "markdown_preview": (kb.get("markdown", ""))[:600],
        }
    except Exception as e:
        logger.error(f"KB status failed: {e}")
        return {"error": str(e), "built": None, "stale": True}


@router.post("/vanguard/admin/vaccine/kb-rebuild")
async def rebuild_kb():
    """
    Force an immediate rebuild of the codebase KB.
    Crawls all backend modules, re-reads routes and patterns, refreshes the
    context injected into every Gemini vaccine/analysis prompt.
    """
    try:
        from vanguard.vaccine.codebase_kb import build_kb, invalidate_kb
        await invalidate_kb()
        kb = await build_kb()
        return {
            "status":       "rebuilt",
            "built_at":     kb.get("built_at"),
            "module_count": kb.get("module_count", 0),
            "route_count":  kb.get("route_count", 0),
            "collection_count": kb.get("collection_count", 0),
            "router_mount_count": len(kb.get("router_mounts", [])),
            "dep_count":    len(kb.get("dependencies", [])),
        }
    except Exception as e:
        logger.error(f"KB rebuild failed: {e}")
        raise HTTPException(500, f"KB rebuild failed: {e}")
