"""
Feature Flags — Vanguard / QuantSight
=======================================
Single source of truth for all runtime feature flags.

Flags are read from environment variables at call time (not at import time),
so Cloud Run environment overrides take effect without redeployment.

Usage:
    from vanguard.core.feature_flags import flag, disabled_response, deprecated_response
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flag Registry — defaults reflect Cloud Run production behaviour
# ---------------------------------------------------------------------------
_FLAG_DEFAULTS: dict = {
    "FEATURE_NEXUS_ENABLED":          False,   # NexusHub — desktop only
    "FEATURE_AEGIS_SIM_ENABLED":       False,   # Monte Carlo sim — stub until Phase 6
    "FEATURE_LEGACY_CRUCIBLE":         False,   # /crucible/simulate — superseded
    "FEATURE_USAGE_VACUUM":            False,   # /admin/usage-vacuum — no callers
    "FEATURE_SEED_ADMIN":              False,   # /admin/seed/* — dev only
    "FEATURE_INCIDENT_SCHEMA_V1":      False,   # Upgraded incident schema
    "FEATURE_MIDDLEWARE_V2":           False,   # Upgraded middleware event schema
    "FEATURE_NBA_HARDENED_CLIENT":     False,   # Hardened NBA API connector
    "VANGUARD_VACCINE_ENABLED":        False,   # Vaccine patch application (existing)
    # ── Phase 4: Circuit Breaker Activation ─────────────────────────────────
    # Each flag is AND-gated with VANGUARD_MODE (must be CIRCUIT_BREAKER or
    # FULL_SOVEREIGN).  Flags allow independent per-subsystem rollback without
    # demoting the entire Vanguard mode.
    "FEATURE_SURGEON_MIDDLEWARE":      False,   # SurgeonMiddleware in-memory circuit checks
    "FEATURE_LOAD_SHEDDER":            False,   # LoadSheddingMiddleware (psutil memory guard)
    "FEATURE_INDEX_DOCTOR":            False,   # Auto-PR for missing Firestore indexes
    # ── Phase 5: FULL_SOVEREIGN + Scale ──────────────────────────────────
    "PULSE_SERVICE_ENABLED":            True,    # Live pulse producer + SSE stream
    "FEATURE_HEURISTIC_TRIAGE":         True,    # Deterministic fallback triage engine
    # ── Phase 6: gRPC Extraction + Bigtable ──────────────────────────────
    "FEATURE_GRPC_SERVER":              False,   # Embedded Vanguard gRPC server (port 50051)
    "FEATURE_BIGTABLE_WRITES":          False,   # Bigtable write path for pulse data
    "FEATURE_WEBSOCKET_ENABLED":        True,    # WebSocket full-duplex (Phase 8 ACTIVE)
}

_TRUTHY = {"1", "true", "yes", "on"}


def flag(name: str, default: Optional[bool] = None) -> bool:
    """
    Read a feature flag from the environment.

    Args:
        name:    Environment variable name (e.g. "FEATURE_NEXUS_ENABLED")
        default: Override the registry default (rarely needed externally)

    Returns:
        True if flag is enabled, False otherwise.
    """
    resolved_default = default if default is not None else _FLAG_DEFAULTS.get(name, False)
    raw = os.environ.get(name)
    if raw is None:
        result = resolved_default
    else:
        result = raw.strip().lower() in _TRUTHY

    logger.debug("[feature_flags] %s=%s (raw=%r, default=%s)", name, result, raw, resolved_default)
    return result


def flag_defaults() -> dict:
    """Return the current resolved state of all registered flags (for health endpoints)."""
    return {name: flag(name) for name in _FLAG_DEFAULTS}


# ---------------------------------------------------------------------------
# Standard response helpers
# ---------------------------------------------------------------------------

def disabled_response(
    feature_flag: str,
    feature_name: str = "",
    request_id: str = None
) -> dict:
    """
    Standard 503-compatible body for a soft-disabled feature.

    Usage:
        raise HTTPException(503, detail=disabled_response("FEATURE_NEXUS_ENABLED"))
    """
    logger.info(
        "[soft-disable] feature=%s flag=%s → 503 unavailable",
        feature_name or feature_flag,
        feature_flag,
    )
    body = {
        "status": "unavailable",
        "code": "FEATURE_DISABLED",
        "feature": feature_flag,
        "message": (
            "This feature is not available in the current deployment mode. "
            f"Set {feature_flag}=true to enable."
        ),
        "mode": "cloud" if os.getenv("K_SERVICE") else "local",
    }
    if request_id:
        body["request_id"] = request_id
    return body


def deprecated_response(
    endpoint: str,
    replacement: str,
    feature_flag: str = "FEATURE_LEGACY",
    sunset_date: str = "2026-06-01",
    request_id: str = None
) -> dict:
    """
    Standard 503-compatible body for a legacy endpoint with no known callers.

    NOTE: Using 503 FEATURE_DISABLED during Phase 1 (not 410 yet).
    Phase 8 will upgrade confirmed-dead endpoints to 410 DEPRECATED after
    proven zero callers over 14 days.

    Usage:
        raise HTTPException(503, detail=deprecated_response("/old", "/new"))
    """
    logger.info("[legacy-endpoint] endpoint=%s → disabled, will route to %s", endpoint, replacement)
    body = {
        "status": "unavailable",
        "code": "FEATURE_DISABLED",
        "feature": feature_flag,
        "endpoint": endpoint,
        "replacement": replacement,
        "sunset_date": sunset_date,
        "message": (
            f"This endpoint has no active callers and is soft-disabled. "
            f"Use {replacement} instead."
        ),
        "mode": "cloud" if os.getenv("K_SERVICE") else "local",
    }
    if request_id:
        body["request_id"] = request_id
    return body


def forbidden_response(
    message: str = "Access denied.",
    feature_flag: str = "",
    request_id: str = None
) -> dict:
    """
    Standard 403-compatible body for a guarded endpoint.

    Usage:
        raise HTTPException(403, detail=forbidden_response("Seed disabled.", "FEATURE_SEED_ADMIN"))
    """
    logger.info("[forbidden] flag=%s", feature_flag)
    body = {
        "status": "forbidden",
        "code": "FEATURE_DISABLED",
        "feature": feature_flag,
        "message": message,
        "mode": "cloud" if os.getenv("K_SERVICE") else "local",
    }
    if request_id:
        body["request_id"] = request_id
    return body
