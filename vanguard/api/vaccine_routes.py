"""
Vanguard Vaccine Admin API Routes
==================================
Endpoints for the Vaccine auto-fix system.

All endpoints are gated by VANGUARD_VACCINE_ENABLED env var.
If disabled, every endpoint returns 403.

Routes:
  GET   /vanguard/admin/vaccine/status
  POST  /vanguard/admin/vaccine/plan/{fingerprint}
  POST  /vanguard/admin/vaccine/patch/{fingerprint}/preview
  POST  /vanguard/admin/vaccine/patch/{fingerprint}/apply
"""

import logging
import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["vanguard-vaccine"])

VACCINE_VERSION = "1.0.0"


# ── Request / Response models ────────────────────────────────────────────────

class PatchApplyRequest(BaseModel):
    confirm: bool = False
    resolution_notes: Optional[str] = ""
    create_commit: bool = False


# ── Feature flag gate ─────────────────────────────────────────────────────────

def _vaccine_enabled() -> bool:
    return os.getenv("VANGUARD_VACCINE_ENABLED", "false").lower() == "true"


def require_vaccine_enabled():
    """FastAPI dependency that blocks all endpoints if vaccine is disabled."""
    if not _vaccine_enabled():
        raise HTTPException(
            status_code=403,
            detail={"error": "Vaccine disabled", "hint": "Set VANGUARD_VACCINE_ENABLED=true"},
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_incident(fingerprint: str) -> Dict[str, Any]:
    """Load incident from Firestore by fingerprint."""
    try:
        from vanguard.archivist.storage import get_incident_storage
        storage = get_incident_storage()
        # Try direct document access first
        if hasattr(storage, "firestore_client") and storage.firestore_client:
            doc_ref = storage.firestore_client.collection("vanguard_incidents").document(fingerprint)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                data["fingerprint"] = fingerprint
                return data
        # Fallback: query
        if hasattr(storage, "get_document"):
            return storage.get_document("vanguard_incidents", fingerprint) or {}
    except Exception as e:
        logger.error(f"Failed to load incident {fingerprint}: {e}")
    raise HTTPException(status_code=404, detail=f"Incident {fingerprint} not found")


def _save_vaccine_data(fingerprint: str, field: str, data: Any):
    """Save vaccine plan/patch/history on the incident document."""
    try:
        from vanguard.archivist.storage import get_incident_storage
        storage = get_incident_storage()
        if hasattr(storage, "firestore_client") and storage.firestore_client:
            doc_ref = storage.firestore_client.collection("vanguard_incidents").document(fingerprint)
            doc_ref.update({field: data})
    except Exception as e:
        logger.warning(f"Failed to save vaccine data for {fingerprint}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/vanguard/admin/vaccine/status")
async def vaccine_status():
    """
    Vaccine system status.
    Works even when disabled — shows flag state + version.
    """
    enabled = _vaccine_enabled()

    result = {
        "vaccine_version": VACCINE_VERSION,
        "enabled": enabled,
        "flag": "VANGUARD_VACCINE_ENABLED",
    }

    if enabled:
        try:
            from vanguard.vaccine.generator import get_vaccine
            generator = get_vaccine()
            result["generator"] = generator.get_status()
        except Exception as e:
            result["generator_error"] = str(e)

        try:
            from vanguard.vaccine.plan_engine import get_plan_engine
            engine = get_plan_engine()
            result["plan_engine_version"] = engine.VERSION
        except Exception as e:
            result["plan_engine_error"] = str(e)

        try:
            from vanguard.vaccine.patch_applier import get_patch_applier
            applier = get_patch_applier()
            result["patch_applier_version"] = applier.VERSION
            result["repo_root"] = str(applier.repo_root)
        except Exception as e:
            result["patch_applier_error"] = str(e)

    return result


@router.post(
    "/vanguard/admin/vaccine/plan/{fingerprint}",
    dependencies=[Depends(require_vaccine_enabled)],
)
async def generate_plan(fingerprint: str):
    """
    Generate a structured remediation plan for an incident.

    Uses stacktrace → file mapping, ENDPOINT_MAP fallback,
    and optional cached AI analysis.
    """
    incident = _get_incident(fingerprint)

    from vanguard.vaccine.plan_engine import get_plan_engine
    engine = get_plan_engine()

    try:
        plan = engine.generate_plan(incident)
        plan_dict = plan.to_dict()

        # Cache plan on incident document
        _save_vaccine_data(fingerprint, "vaccine_plan", plan_dict)

        return {
            "status": "plan_generated",
            "plan": plan_dict,
        }
    except Exception as e:
        logger.error(f"Plan generation failed for {fingerprint}: {e}")
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {e}")


@router.post(
    "/vanguard/admin/vaccine/patch/{fingerprint}/preview",
    dependencies=[Depends(require_vaccine_enabled)],
)
async def preview_patch(fingerprint: str):
    """
    Generate a patch preview (diff) for an incident fix.

    Uses VaccineGenerator (Gemini) to create the patch,
    then returns it without applying.
    """
    incident = _get_incident(fingerprint)

    # Get or generate plan first
    plan_data = incident.get("vaccine_plan")
    if not plan_data:
        from vanguard.vaccine.plan_engine import get_plan_engine
        engine = get_plan_engine()
        plan = engine.generate_plan(incident)
        plan_data = plan.to_dict()

    # Try to generate fix via VaccineGenerator
    from vanguard.vaccine.generator import get_vaccine
    generator = get_vaccine()

    # Build analysis dict from incident + plan
    analysis = {
        "fingerprint": fingerprint,
        "error_message": incident.get("error_message", ""),
        "root_cause": plan_data.get("root_cause_bucket", ""),
        "confidence": 90,  # default for preview
        "recommended_fix": plan_data.get("proposed_changes_summary", ""),
        "code_references": [
            {"file": c.get("file", ""), "line": 1, "snippet": "",
             "function": c.get("symbol", "")}
            for c in plan_data.get("fix_candidates", [])
        ],
    }

    # Check if generator can produce a fix
    can_gen, reason = await generator.can_generate_fix(analysis)
    if not can_gen:
        # Return plan-only without AI-generated patch
        from vanguard.vaccine.patch_applier import get_patch_applier
        applier = get_patch_applier()

        return {
            "status": "preview_plan_only",
            "reason": reason,
            "plan": plan_data,
            "patch": None,
            "message": "AI fix generation skipped — plan available for manual implementation",
        }

    try:
        patch = await generator.generate_fix(analysis)
        if not patch:
            return {
                "status": "preview_no_fix",
                "plan": plan_data,
                "patch": None,
                "message": "Generator could not produce a fix for this incident",
            }

        # Build PatchSpec preview
        from vanguard.vaccine.patch_applier import get_patch_applier
        applier = get_patch_applier()
        patch_spec = applier.preview(
            fingerprint=fingerprint,
            file_patches=[{
                "path": patch.file_path,
                "original": patch.original_code,
                "patched": patch.fixed_code,
            }],
            notes=patch.explanation,
        )

        result = {
            "status": "preview_ready",
            "plan": plan_data,
            "patch": patch_spec.to_dict(),
        }

        # Cache patch spec on incident
        _save_vaccine_data(fingerprint, "vaccine_patch", patch_spec.to_dict())

        return result

    except Exception as e:
        logger.error(f"Preview generation failed for {fingerprint}: {e}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {e}")


@router.post(
    "/vanguard/admin/vaccine/patch/{fingerprint}/apply",
    dependencies=[Depends(require_vaccine_enabled)],
)
async def apply_patch(fingerprint: str, request: PatchApplyRequest):
    """
    Apply a previewed patch to the codebase.

    Requires:
      - confirm: true in request body
      - A cached vaccine_patch on the incident (from preview endpoint)

    Will run verification after applying. If verification fails,
    changes are rolled back automatically.
    """
    incident = _get_incident(fingerprint)

    cached_patch = incident.get("vaccine_patch")
    if not cached_patch:
        raise HTTPException(
            status_code=400,
            detail="No patch preview found — call /preview first",
        )

    # Reconstruct PatchSpec from cached data
    from vanguard.vaccine.patch_applier import (
        get_patch_applier, PatchSpec, FileChange,
    )
    applier = get_patch_applier()

    files_changed = []
    for fc_data in cached_patch.get("files_changed", []):
        files_changed.append(FileChange(
            path=fc_data.get("path", ""),
            changes_summary=fc_data.get("changes_summary", ""),
            original_content=fc_data.get("original_content", ""),
            patched_content=fc_data.get("patched_content", ""),
            lines_added=fc_data.get("lines_added", 0),
            lines_removed=fc_data.get("lines_removed", 0),
        ))

    patch_spec = PatchSpec(
        fingerprint=fingerprint,
        files_changed=files_changed,
        unified_diff=cached_patch.get("unified_diff", ""),
        notes=cached_patch.get("notes", ""),
        guardrails_passed=cached_patch.get("guardrails_passed", False),
        guardrails_reason=cached_patch.get("guardrails_reason", ""),
        diff_hash=cached_patch.get("diff_hash", ""),
        created_at=cached_patch.get("created_at", ""),
    )

    # Apply
    result = applier.apply(
        patch=patch_spec,
        confirm=request.confirm,
        create_commit=request.create_commit,
        resolution_notes=request.resolution_notes or "",
    )

    # Record history on incident
    history_entry = {
        "applied_at": result.metadata.get("applied_at", ""),
        "success": result.success,
        "verification_passed": result.verification_passed,
        "diff_hash": result.diff_hash,
        "git_commit": result.git_commit,
        "rollback_performed": result.rollback_performed,
        "message": result.message,
    }

    _save_vaccine_data(fingerprint, "vaccine_history", history_entry)

    # If successful, optionally mark incident resolved
    if result.success and result.verification_passed:
        _save_vaccine_data(fingerprint, "vaccine_applied", True)

    return result.to_dict()
