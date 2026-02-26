"""
Surgeon Middleware — Phase 4 Step 4.4
======================================
Wires the CircuitBreakerV2 and FailureTracker into the request path.

Behavior:
  - On every incoming request: check circuit_breaker.get_state(path)
  - If OPEN:      return 503 immediately, do not forward to route handler
  - If HALF_OPEN: allow one probe per 30s, return 503 for all others
  - If CLOSED:    pass through normally
  - After response: feed result into failure_tracker.record(path, status)
                    then evaluate_endpoint for state transitions

Feature flag gate:
  - Only activates when VANGUARD_MODE is CIRCUIT_BREAKER or FULL_SOVEREIGN
    AND FEATURE_SURGEON_MIDDLEWARE=true
  - In SILENT_OBSERVER mode (or flag disabled): runs in DRY_RUN
    (logs what it would do, never blocks requests)

Position in middleware stack:
  Before InquisitorMiddleware so Inquisitor still records 503s as events.
"""

import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.logger import get_logger
from ..core.config import get_vanguard_config, VanguardMode
from .circuit_breaker_v2 import get_circuit_breaker_v2, CircuitState
from .failure_tracker import get_failure_tracker
from .load_shedder import get_load_shedder

logger = get_logger(__name__)


def _is_active_mode() -> bool:
    """Check if Surgeon should actively block requests (not DRY_RUN)."""
    try:
        config = get_vanguard_config()
        mode_ok = config.mode in (VanguardMode.CIRCUIT_BREAKER, VanguardMode.FULL_SOVEREIGN)
    except Exception:
        mode_ok = False

    try:
        from ..core.feature_flags import flag
        flag_ok = flag("FEATURE_SURGEON_MIDDLEWARE")
    except ImportError:
        flag_ok = False

    return mode_ok and flag_ok


class SurgeonMiddleware(BaseHTTPMiddleware):
    """
    Circuit breaker middleware for endpoint quarantine.

    Hot-path checks are O(1) dict lookups — no Firestore, no network I/O.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        active = _is_active_mode()
        cb = get_circuit_breaker_v2()
        tracker = get_failure_tracker()

        # ── Pre-request: circuit check ───────────────────────────────────
        state = await cb.get_state(path)

        if state == CircuitState.OPEN:
            if active:
                logger.warning(
                    "surgeon_circuit_OPEN_block",
                    endpoint=path,
                    method=request.method,
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "circuit_open",
                        "endpoint": path,
                        "retry_after": 60,
                    },
                    headers={"Retry-After": "60"},
                )
            else:
                # DRY_RUN: log but allow through
                logger.info(
                    "surgeon_dry_run_would_block",
                    endpoint=path,
                    method=request.method,
                    state="OPEN",
                )

        elif state == CircuitState.HALF_OPEN:
            allowed = await cb.should_allow_probe(path)
            if not allowed:
                if active:
                    logger.info(
                        "surgeon_half_open_reject",
                        endpoint=path,
                        method=request.method,
                    )
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": "circuit_open",
                            "endpoint": path,
                            "retry_after": 30,
                        },
                        headers={"Retry-After": "30"},
                    )
                else:
                    logger.info(
                        "surgeon_dry_run_would_reject_probe",
                        endpoint=path,
                        state="HALF_OPEN",
                    )
        # ── Pre-request: load shedding check ──────────────────────────────
        if active:
            try:
                from ..core.feature_flags import flag as _flag
                load_shed_flag = _flag("FEATURE_LOAD_SHEDDER")
            except ImportError:
                load_shed_flag = False

            if load_shed_flag:
                shedder = get_load_shedder()
                if shedder.should_shed(path, request.method):
                    logger.warning(
                        "surgeon_load_shed_reject",
                        endpoint=path,
                        method=request.method,
                        memory_pct=round(shedder.memory_pct, 1),
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "load_shedding",
                            "endpoint": path,
                            "retry_after": 30,
                        },
                        headers={"Retry-After": "30"},
                    )

        # ── Forward to next middleware / route handler ────────────────────
        exception_occurred = False
        try:
            response = await call_next(request)
        except Exception:
            exception_occurred = True
            # Record exception as failure
            await tracker.record_exception(path)
            await cb.evaluate_endpoint(path)
            raise

        # ── Post-response: record outcome and evaluate ───────────────────
        status_code = response.status_code

        await tracker.record(path, status_code)
        await cb.evaluate_endpoint(path)

        # Handle probe result in HALF_OPEN state
        if state == CircuitState.HALF_OPEN:
            probe_success = 200 <= status_code < 300
            await cb.record_probe_result(path, success=probe_success)

        return response
