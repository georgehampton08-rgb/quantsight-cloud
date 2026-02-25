"""
Incident Schema v1 — Structured Incident Upgrade
===================================================
Phase 3: Adds schema_version, structured labels, remediation blocks,
ai_analysis, and resolution blocks to incidents.

Feature flag: FEATURE_INCIDENT_SCHEMA_V1
  When False: module is a no-op, incidents remain v0.
  When True:  new incidents are created with v1 schema,
              and old v0 incidents are migrated on-the-fly when read.

Design rules:
  - No Firestore bulk rewrite (on-the-fly migration only)
  - v0 incidents load without crashing whether flag is on or off
  - v1 fields are always Optional to preserve backwards compatibility
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "v1"

# ---------------------------------------------------------------------------
# v1 field templates
# ---------------------------------------------------------------------------

def _empty_labels() -> dict:
    """Default labels block for a v1 incident."""
    return {
        "service": "",
        "revision": "",
        "region": "",
        "component": "",
        "team": "",
        "player_id": "",
    }


def _empty_remediation() -> dict:
    """Default remediation block for a v1 incident."""
    return {
        "plan": None,           # str — generated remediation steps
        "references": [],       # list[str] — stacktrace-first refs or ENDPOINT_MAP fallback
        "confidence": 0.0,      # float 0-1 — how confident the plan is
        "auto_generated": False, # bool — was this auto-generated?
        "generated_at": None,   # ISO str
    }


def _empty_ai_analysis() -> dict:
    """Default ai_analysis block for a v1 incident."""
    return {
        "summary": None,         # str — AI-generated one-liner
        "root_cause": None,      # str — AI-identified root cause
        "suggested_fix": None,   # str — suggested code fix or action
        "confidence": 0.0,       # float 0-1
        "model": None,           # str — which model produced this
        "analyzed_at": None,     # ISO str
    }


def _empty_resolution() -> dict:
    """Default resolution block for a v1 incident."""
    return {
        "resolved_by": None,     # str — "auto" | "surgeon" | "manual" | username
        "resolution_type": None, # str — "vaccine_patch" | "quarantine" | "rate_limit" | "manual"
        "notes": None,           # str — free text
        "resolved_at": None,     # ISO str
        "verified": False,       # bool — was the resolution verified?
    }


# ---------------------------------------------------------------------------
# On-the-fly v0 → v1 migration
# ---------------------------------------------------------------------------

def migrate_incident_v0_to_v1(incident: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate a v0 incident dict to v1 schema in-memory.

    This is called on-the-fly when reading v0 incidents with
    FEATURE_INCIDENT_SCHEMA_V1=true. It does NOT write back to Firestore
    (that would be a bulk migration — out of scope for Phase 3).

    Safe to call on incidents that are already v1 (idempotent).
    """
    if incident.get("schema_version") == SCHEMA_VERSION:
        return incident  # already v1

    migrated = dict(incident)  # shallow copy
    migrated["schema_version"] = SCHEMA_VERSION

    # Ensure structured labels
    if "labels" not in migrated or not isinstance(migrated.get("labels"), dict):
        migrated["labels"] = _empty_labels()
        # Backfill from context_vector if available
        ctx = migrated.get("context_vector", {})
        if isinstance(ctx, dict):
            if "method" in ctx:
                migrated["labels"]["component"] = f"{ctx.get('method', '')} handler"

    # Ensure remediation block
    if "remediation" not in migrated or not isinstance(migrated.get("remediation"), dict):
        migrated["remediation"] = _empty_remediation()
        # Backfill from old remediation_log list
        old_log = migrated.get("remediation_log", [])
        if old_log and isinstance(old_log, list):
            migrated["remediation"]["references"] = old_log

    # Ensure ai_analysis block
    if "ai_analysis" not in migrated or not isinstance(migrated.get("ai_analysis"), dict):
        # check if legacy ai_analysis was stored as a flat dict
        existing = migrated.get("ai_analysis")
        if existing and isinstance(existing, dict):
            pass  # keep it
        else:
            migrated["ai_analysis"] = _empty_ai_analysis()

    # Ensure resolution block
    if "resolution" not in migrated or not isinstance(migrated.get("resolution"), dict):
        migrated["resolution"] = _empty_resolution()
        # Backfill from resolved_at
        if migrated.get("resolved_at"):
            migrated["resolution"]["resolved_at"] = migrated["resolved_at"]
            migrated["resolution"]["resolved_by"] = "unknown_legacy"
            migrated["resolution"]["resolution_type"] = "manual"

    # Ensure duration_ms exists
    if "duration_ms" not in migrated:
        migrated["duration_ms"] = None

    logger.debug(
        "[schema_v1] migrated incident %s from v0 → v1",
        migrated.get("fingerprint", "unknown"),
    )
    return migrated


def stamp_new_incident_v1(incident: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stamp a new incident with v1 schema fields.

    Called when creating new incidents with FEATURE_INCIDENT_SCHEMA_V1=true.
    Ensures all v1 blocks are present from creation.
    """
    incident["schema_version"] = SCHEMA_VERSION

    if "labels" not in incident or not isinstance(incident.get("labels"), dict):
        incident["labels"] = _empty_labels()

    if "remediation" not in incident:
        incident["remediation"] = _empty_remediation()

    if "ai_analysis" not in incident:
        incident["ai_analysis"] = _empty_ai_analysis()

    if "resolution" not in incident:
        incident["resolution"] = _empty_resolution()

    if "duration_ms" not in incident:
        incident["duration_ms"] = None

    return incident
