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

logger = logging.getLogger(__name__)
router = APIRouter(tags=["vanguard-admin"])



class ResolveRequest(BaseModel):
    approved: bool = False  # Manual approval required
    resolution_notes: Optional[str] = None


class BulkResolveRequest(BaseModel):
    fingerprints: List[str]
    resolution_notes: Optional[str] = None


class ResolveAllRequest(BaseModel):
    confirm: bool
    resolution_notes: Optional[str] = "Batch resolution"


class ModeRequest(BaseModel):
    mode: str  # "SILENT_OBSERVER", "CIRCUIT_BREAKER", "FULL_SOVEREIGN"


@router.post("/vanguard/admin/mode")
async def toggle_vanguard_mode(request: ModeRequest):
    """Manually toggle Vanguard operational mode."""
    from vanguard.core.config import get_vanguard_config, VanguardMode
    config = get_vanguard_config()
    
    try:
        new_mode = VanguardMode(request.mode.upper())
        old_mode = config.mode
        config.mode = new_mode
        
        logger.warning(f"Vanguard mode manually changed: {old_mode} -> {new_mode}")
        return {
            "success": True, 
            "old_mode": old_mode,
            "new_mode": new_mode,
            "message": f"Vanguard switched to {new_mode}"
        }
    except ValueError:
        raise HTTPException(400, f"Invalid mode: {request.mode}. Use SILENT_OBSERVER, CIRCUIT_BREAKER, or FULL_SOVEREIGN.")


@router.get("/vanguard/admin/incidents")
async def list_all_incidents(status: Optional[str] = None, limit: int = 100):
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


@router.post("/vanguard/admin/incidents/{fingerprint}/resolve")
async def resolve_incident(fingerprint: str, request: ResolveRequest):
    """Mark a single incident as resolved."""
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
        
        # Resolve the incident
        success = await storage.resolve(fingerprint)
        
        if success:
            logger.info(f"Incident resolved: {fingerprint}")
            return {
                "success": True,
                "message": "Incident resolved",
                "fingerprint": fingerprint,
                "resolution_notes": request.resolution_notes,
                "resolved_at": datetime.utcnow().isoformat() + "Z"
            }
        else:
            raise HTTPException(500, "Failed to resolve incident")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve incident {fingerprint}: {e}")
        raise HTTPException(500, str(e))


@router.post("/vanguard/admin/incidents/bulk-resolve")
async def bulk_resolve_incidents(request: BulkResolveRequest):
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
async def resolve_all_incidents(request: ResolveAllRequest):
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
        training_data = learner.generate_training_data()
        
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
        await storage.resolve_incident(fingerprint)
        
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
