import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SYSTEM_SNAPSHOT = {
    "firestore_ok": True,
    "gemini_ok": True,
    "vanguard_ok": True,
    "redis_ok": False,
    # Phase 9: ML health indicators
    "ml_classifier_ok": False,
    "ml_classifier_version": None,
    "ml_fallback_rate_1h": 0.0,
    "updated_at": datetime.now(timezone.utc).isoformat()
}

_snapshot_task = None

# ── Consecutive failure/success counters for routing table hysteresis ────────
# Activation:   3 consecutive gemini_ok=False  (~90s at 30s intervals)
# Deactivation: 2 consecutive gemini_ok=True   (~60s at 30s intervals)
_GEMINI_FAIL_THRESHOLD = 3
_GEMINI_RECOVER_THRESHOLD = 2
_gemini_consecutive_failures = 0
_gemini_consecutive_successes = 0


async def _evaluate_gemini_routing(gemini_ok: bool) -> None:
    """
    Evaluate Gemini health and activate/deactivate heuristic triage
    via the Surgeon routing table.

    Uses hysteresis to avoid flapping:
      - 3 consecutive failures → activate fallback
      - 2 consecutive successes → deactivate fallback
    """
    global _gemini_consecutive_failures, _gemini_consecutive_successes

    try:
        from vanguard.surgeon.routing_table import get_routing_table
        from vanguard.core.config import get_vanguard_config, VanguardMode

        config = get_vanguard_config()

        # Only manage routing table when in FULL_SOVEREIGN mode
        if config.mode != VanguardMode.FULL_SOVEREIGN:
            return

        rt = get_routing_table()
        route_key = "gemini_triage_path"

        if not gemini_ok:
            _gemini_consecutive_failures += 1
            _gemini_consecutive_successes = 0
            SYSTEM_SNAPSHOT["gemini_consecutive_failures"] = _gemini_consecutive_failures

            if (_gemini_consecutive_failures >= _GEMINI_FAIL_THRESHOLD
                    and not rt.is_fallback_active(route_key)):
                activated = await rt.activate_fallback(
                    route_key,
                    reason=f"Gemini unavailable for {_gemini_consecutive_failures} consecutive checks (~{_gemini_consecutive_failures * 30}s)",
                )
                if activated:
                    logger.warning(
                        "gemini_heuristic_fallback_ACTIVATED",
                        consecutive_failures=_gemini_consecutive_failures,
                    )
                    # Post incident for fallback activation
                    await _post_routing_incident(
                        "HEURISTIC_FALLBACK_ACTIVATED",
                        "RED",
                        {"consecutive_failures": _gemini_consecutive_failures},
                    )
        else:
            _gemini_consecutive_successes += 1
            _gemini_consecutive_failures = 0
            SYSTEM_SNAPSHOT["gemini_consecutive_failures"] = 0

            if (_gemini_consecutive_successes >= _GEMINI_RECOVER_THRESHOLD
                    and rt.is_fallback_active(route_key)):
                recovery_time_s = await rt.deactivate_fallback(route_key)
                if recovery_time_s is not None:
                    logger.info(
                        "gemini_heuristic_fallback_DEACTIVATED",
                        consecutive_successes=_gemini_consecutive_successes,
                        recovery_time_s=round(recovery_time_s, 2),
                    )
                    await _post_routing_incident(
                        "HEURISTIC_FALLBACK_RECOVERED",
                        "GREEN",
                        {
                            "consecutive_successes": _gemini_consecutive_successes,
                            "recovery_time_s": round(recovery_time_s, 2),
                        },
                    )
    except Exception as e:
        # Routing table evaluation NEVER crashes the snapshot loop
        logger.error(f"Gemini routing evaluation failed: {e}")


async def _post_routing_incident(incident_type: str, severity: str, metadata: dict) -> None:
    """Post a Vanguard incident for routing table state transitions."""
    try:
        from vanguard.archivist.storage import get_incident_storage
        from vanguard.inquisitor.fingerprint import generate_error_fingerprint

        storage = get_incident_storage()
        fingerprint = generate_error_fingerprint(
            exception_type=incident_type,
            traceback_lines=[incident_type],
            endpoint="system/routing_table",
        )

        incident = {
            "fingerprint": fingerprint,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity,
            "status": "ACTIVE" if severity == "RED" else "resolved",
            "error_type": incident_type,
            "error_message": f"{incident_type}: gemini_triage_path",
            "endpoint": "system/routing_table",
            "request_id": "surgeon-routing-table",
            "traceback": None,
            "context_vector": metadata,
            "remediation_log": [],
            "resolved_at": (
                datetime.now(timezone.utc).isoformat()
                if severity == "GREEN"
                else None
            ),
        }
        await storage.store(incident)
    except Exception as e:
        logger.error(f"Routing incident post failed: {e}")


async def update_snapshot_loop():
    """Background loop to periodically verify dependencies and update the global snapshot."""
    while True:
        try:
            # Check Firestore, Gemini
            from vanguard.health_monitor import get_health_monitor
            monitor = get_health_monitor()
            # Use bounded timeout internally
            try:
                results = await asyncio.wait_for(monitor.run_all_checks(), timeout=5.0)
                SYSTEM_SNAPSHOT["firestore_ok"] = results.get("firestore", {}).get("status") != "critical"
                SYSTEM_SNAPSHOT["gemini_ok"] = results.get("gemini_ai", {}).get("status") == "healthy"
            except asyncio.TimeoutError:
                SYSTEM_SNAPSHOT["firestore_ok"] = False
                SYSTEM_SNAPSHOT["gemini_ok"] = False

            # ── Evaluate Gemini routing table (Phase 5) ──────────────────
            await _evaluate_gemini_routing(SYSTEM_SNAPSHOT["gemini_ok"])

            # Check Redis
            try:
                from vanguard.bootstrap.redis_client import ping_redis
                SYSTEM_SNAPSHOT["redis_ok"] = await ping_redis()
            except Exception:
                SYSTEM_SNAPSHOT["redis_ok"] = False

            # Check Vanguard subsystems via Oracle
            try:
                from vanguard.ai.subsystem_oracle import get_oracle
                # Pass a dummy string for storage to avoid cyclic imports if archivist fails, 
                # but Oracle gracefully handles it
                oracle = get_oracle()
                # Run with timeout
                oracle_snap = await asyncio.wait_for(oracle.collect("health_ping", None), timeout=5.0)
                SYSTEM_SNAPSHOT["vanguard_ok"] = oracle_snap.critical_count == 0
            except Exception as e:
                SYSTEM_SNAPSHOT["vanguard_ok"] = False

            # ── Expose routing table state in snapshot (Phase 5) ─────────
            try:
                from vanguard.surgeon.routing_table import get_routing_table
                rt = get_routing_table()
                SYSTEM_SNAPSHOT["routing_table"] = {
                    "active_fallbacks": rt.get_active_fallbacks(),
                }
            except Exception:
                pass

            SYSTEM_SNAPSHOT["updated_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.error(f"Snapshot loop encountered an error: {e}")
            
        await asyncio.sleep(30)

def start_snapshot_loop():
    global _snapshot_task
    if _snapshot_task is None:
        _snapshot_task = asyncio.create_task(update_snapshot_loop())

def stop_snapshot_loop():
    global _snapshot_task
    if _snapshot_task is not None:
        _snapshot_task.cancel()
        _snapshot_task = None
