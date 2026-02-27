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


# ============================================================================
# AUDIT LOG ENDPOINT (Phase 7)
# ============================================================================

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

