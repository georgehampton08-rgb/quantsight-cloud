"""
FULL_SOVEREIGN Promotion Gate — Phase 5 Step 5.6
===================================================
Pre-promotion readiness checks that MUST pass before flipping
VANGUARD_MODE=FULL_SOVEREIGN in production.

This module provides:
  1. A dry-run verification function (check_promotion_readiness)
  2. An admin endpoint (/vanguard/admin/promotion-readiness)
  3. A promotion execution plan

Usage:
  GET /vanguard/admin/promotion-readiness
  → Returns a checklist of all gates with pass/fail status.
  → Promotion MUST NOT proceed unless all gates pass.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vanguard/admin", tags=["Vanguard Admin"])


async def check_promotion_readiness() -> Dict[str, Any]:
    """
    Run all pre-promotion gates. Returns a structured report.
    Every gate must pass before FULL_SOVEREIGN promotion.
    """
    gates: List[Dict[str, Any]] = []
    all_passed = True

    # ── Gate 1: Routing Table exists and has default routes ──────────────
    try:
        from vanguard.surgeon.routing_table import get_routing_table
        rt = get_routing_table()
        route = rt.get_route("gemini_triage_path")
        gate_passed = route is not None and route.fallback_handler is not None
        gates.append({
            "gate": "routing_table_initialized",
            "description": "RoutingTable has gemini_triage_path with fallback handler",
            "passed": gate_passed,
            "detail": {
                "primary": route.primary_handler if route else None,
                "fallback": route.fallback_handler if route else None,
            },
        })
        if not gate_passed:
            all_passed = False
    except Exception as e:
        gates.append({
            "gate": "routing_table_initialized",
            "description": "RoutingTable import check",
            "passed": False,
            "detail": {"error": str(e)},
        })
        all_passed = False

    # ── Gate 2: Heuristic triage engine functional ───────────────────────
    try:
        from vanguard.ai.heuristic_triage import generate_heuristic_triage
        test_incident = {
            "fingerprint": "promotion-gate-test",
            "error_type": "KeyError",
            "error_message": "test key",
            "endpoint": "/test",
            "severity": "YELLOW",
            "occurrence_count": 1,
        }
        analysis = generate_heuristic_triage(test_incident)
        gate_passed = (
            analysis is not None
            and analysis.confidence > 0
            and analysis.model_id == "heuristic-engine"
        )
        gates.append({
            "gate": "heuristic_triage_functional",
            "description": "Heuristic triage produces valid IncidentAnalysis output",
            "passed": gate_passed,
            "detail": {
                "confidence": analysis.confidence if analysis else 0,
                "model_id": analysis.model_id if analysis else None,
            },
        })
        if not gate_passed:
            all_passed = False
    except Exception as e:
        gates.append({
            "gate": "heuristic_triage_functional",
            "description": "Heuristic triage import and execution",
            "passed": False,
            "detail": {"error": str(e)},
        })
        all_passed = False

    # ── Gate 3: Snapshot hysteresis counters exist ────────────────────────
    try:
        import vanguard.snapshot as snap
        has_counters = (
            hasattr(snap, "_gemini_consecutive_failures")
            and hasattr(snap, "_gemini_consecutive_successes")
            and hasattr(snap, "_evaluate_gemini_routing")
        )
        gates.append({
            "gate": "snapshot_hysteresis_available",
            "description": "SYSTEM_SNAPSHOT has gemini hysteresis counters and routing evaluator",
            "passed": has_counters,
            "detail": {
                "consecutive_failures": getattr(snap, "_gemini_consecutive_failures", "MISSING"),
                "consecutive_successes": getattr(snap, "_gemini_consecutive_successes", "MISSING"),
            },
        })
        if not has_counters:
            all_passed = False
    except Exception as e:
        gates.append({
            "gate": "snapshot_hysteresis_available",
            "description": "Snapshot module check",
            "passed": False,
            "detail": {"error": str(e)},
        })
        all_passed = False

    # ── Gate 4: Inquisitor middleware wired for routing ───────────────────
    try:
        from vanguard.inquisitor.middleware import _execute_ai_triage
        import inspect
        source = inspect.getsource(_execute_ai_triage)
        has_routing_check = "gemini_triage_path" in source and "triage_source" in source
        gates.append({
            "gate": "inquisitor_routing_wired",
            "description": "_execute_ai_triage checks routing table before calling Gemini",
            "passed": has_routing_check,
            "detail": {"routing_check_in_source": has_routing_check},
        })
        if not has_routing_check:
            all_passed = False
    except Exception as e:
        gates.append({
            "gate": "inquisitor_routing_wired",
            "description": "Inquisitor middleware routing check",
            "passed": False,
            "detail": {"error": str(e)},
        })
        all_passed = False

    # ── Gate 5: Current mode is CIRCUIT_BREAKER (not jumping from SILENT) ─
    try:
        from vanguard.core.config import get_vanguard_config, VanguardMode
        config = get_vanguard_config()
        is_circuit_breaker = config.mode == VanguardMode.CIRCUIT_BREAKER
        gates.append({
            "gate": "current_mode_circuit_breaker",
            "description": "Cannot promote to FULL_SOVEREIGN directly from SILENT_OBSERVER",
            "passed": is_circuit_breaker,
            "detail": {"current_mode": config.mode.value},
        })
        if not is_circuit_breaker:
            all_passed = False
    except Exception as e:
        gates.append({
            "gate": "current_mode_circuit_breaker",
            "description": "Mode check",
            "passed": False,
            "detail": {"error": str(e)},
        })
        all_passed = False

    # ── Gate 6: Redis connectivity ───────────────────────────────────────
    try:
        from vanguard.bootstrap.redis_client import ping_redis
        redis_ok = await ping_redis()
        gates.append({
            "gate": "redis_connectivity",
            "description": "Redis connection healthy (FAIL OPEN ok, but should be connected)",
            "passed": redis_ok,
            "detail": {"redis_ping": redis_ok},
        })
        # Redis is FAIL OPEN — don't block promotion on this
        # But flag it as a warning
        if not redis_ok:
            gates[-1]["warning"] = "Redis is down — rate limiter and idempotency will use fallbacks"
    except Exception as e:
        gates.append({
            "gate": "redis_connectivity",
            "description": "Redis ping check",
            "passed": False,
            "detail": {"error": str(e)},
            "warning": "Redis unavailable — non-blocking but degraded",
        })

    # ── Gate 7: Firestore connectivity ───────────────────────────────────
    try:
        from vanguard.snapshot import SYSTEM_SNAPSHOT
        firestore_ok = SYSTEM_SNAPSHOT.get("firestore_ok", False)
        gates.append({
            "gate": "firestore_connectivity",
            "description": "Firestore connection healthy (required for incident storage)",
            "passed": firestore_ok,
            "detail": {"firestore_ok": firestore_ok},
        })
        if not firestore_ok:
            all_passed = False
    except Exception as e:
        gates.append({
            "gate": "firestore_connectivity",
            "description": "Firestore check",
            "passed": False,
            "detail": {"error": str(e)},
        })
        all_passed = False

    # ── Gate 8: Live stream routes available ──────────────────────────────
    try:
        from api.live_stream_routes import router as live_router
        route_count = len(live_router.routes)
        gates.append({
            "gate": "live_stream_routes_available",
            "description": "SSE and REST live stream endpoints registered",
            "passed": route_count >= 4,
            "detail": {"route_count": route_count},
        })
        if route_count < 4:
            all_passed = False
    except Exception as e:
        gates.append({
            "gate": "live_stream_routes_available",
            "description": "Live stream routes import",
            "passed": False,
            "detail": {"error": str(e)},
        })
        all_passed = False

    # ── Compile report ───────────────────────────────────────────────────
    passed_count = sum(1 for g in gates if g["passed"])
    total_count = len(gates)

    return {
        "promotion_ready": all_passed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_mode": "FULL_SOVEREIGN",
        "summary": f"{passed_count}/{total_count} gates passed",
        "gates": gates,
        "next_steps": (
            [
                "Set VANGUARD_MODE=FULL_SOVEREIGN in Cloud Run environment",
                "Deploy with `gcloud run deploy --set-env-vars VANGUARD_MODE=FULL_SOVEREIGN`",
                "Monitor /health/deps for routing_table.active_fallbacks",
                "Verify heuristic triage activates when Gemini is unreachable",
            ]
            if all_passed
            else [
                "Fix failing gates before attempting promotion",
                "Re-run GET /vanguard/admin/promotion-readiness to verify",
            ]
        ),
    }


@router.get("/promotion-readiness")
async def promotion_readiness_endpoint():
    """
    Pre-promotion readiness gate for FULL_SOVEREIGN mode.
    All gates must pass before promotion is safe.
    """
    return await check_promotion_readiness()
