"""
Circuit Breaker — Phase 4 Step 4.3
====================================
Production circuit breaker with correct CLOSED → OPEN → HALF_OPEN → CLOSED
state machine, backed by the FailureTracker sliding window.

State semantics (industry standard):
    CLOSED    = normal operation, requests pass through
    OPEN      = endpoint quarantined, all requests return 503
    HALF_OPEN = one probe request allowed every 30s to test recovery

Transitions:
    CLOSED → OPEN:      failure rate > 50% over 60s window (min 10 requests)
    OPEN → HALF_OPEN:   automatically after 60s quarantine period
    HALF_OPEN → CLOSED: probe request succeeds (2xx)
    HALF_OPEN → OPEN:   probe request fails → reset 60s quarantine timer

Blast radius constraints (HARDCODED — cannot be overridden by config):
    /healthz, /readyz, /health, /health/deps, /vanguard/*, /admin/*

Vanguard incidents posted on:
    CLOSED → OPEN:  type=CIRCUIT_OPENED, severity=RED
    OPEN → CLOSED:  type=CIRCUIT_RECOVERED, severity=GREEN

Replaces the 1st-gen circuit_breaker.py which had OPEN/CLOSED semantics inverted.
"""

import asyncio
import time
from enum import Enum
from typing import Dict, Optional
from datetime import datetime, timezone

from ..utils.logger import get_logger
from ..core.config import get_vanguard_config, VanguardMode
from .failure_tracker import get_failure_tracker, _is_excluded

logger = get_logger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
FAILURE_RATE_THRESHOLD = 0.50     # 50% failure rate triggers OPEN
MIN_REQUESTS_IN_WINDOW = 10      # minimum requests before threshold applies
QUARANTINE_DURATION_S = 60       # seconds before OPEN → HALF_OPEN
PROBE_INTERVAL_S = 30            # seconds between probe requests in HALF_OPEN


class CircuitState(str, Enum):
    """Circuit breaker states (industry standard semantics)."""
    CLOSED = "CLOSED"        # Normal operation, traffic passes
    OPEN = "OPEN"            # Quarantined, traffic blocked (503)
    HALF_OPEN = "HALF_OPEN"  # Probe state, one request per interval


class _CircuitEntry:
    """State for a single endpoint's circuit breaker."""

    __slots__ = (
        "state", "opened_at", "last_probe_at",
        "failure_rate_at_open", "lock",
    )

    def __init__(self):
        self.state: CircuitState = CircuitState.CLOSED
        self.opened_at: Optional[float] = None       # monotonic timestamp when circuit opened
        self.last_probe_at: Optional[float] = None    # monotonic timestamp of last probe
        self.failure_rate_at_open: float = 0.0        # recorded for incident metadata
        self.lock: asyncio.Lock = asyncio.Lock()


class CircuitBreakerV2:
    """
    Production circuit breaker for endpoint quarantine.

    All public methods are async. The circuit breaker reads failure rates from
    the global FailureTracker and makes state transition decisions.
    """

    def __init__(self):
        self._circuits: Dict[str, _CircuitEntry] = {}
        self._global_lock = asyncio.Lock()

    async def get_state(self, endpoint: str) -> CircuitState:
        """
        Get the current circuit state for an endpoint.

        This is the hot-path method called by SurgeonMiddleware on every request.
        Returns CLOSED for unknown endpoints and blast-radius protected routes.
        """
        # Blast radius protection — hardcoded, no config can override
        if _is_excluded(endpoint):
            return CircuitState.CLOSED

        entry = self._circuits.get(endpoint)
        if entry is None:
            return CircuitState.CLOSED

        async with entry.lock:
            # Check for automatic OPEN → HALF_OPEN transition
            if entry.state == CircuitState.OPEN and entry.opened_at is not None:
                elapsed = time.monotonic() - entry.opened_at
                if elapsed >= QUARANTINE_DURATION_S:
                    await self._transition_to_half_open(endpoint, entry)

            return entry.state

    async def should_allow_probe(self, endpoint: str) -> bool:
        """
        In HALF_OPEN state, allow one probe request per PROBE_INTERVAL_S.
        Returns True if this request should be allowed through as a probe.
        Returns False if another probe was sent recently.
        """
        entry = self._circuits.get(endpoint)
        if entry is None:
            return True

        async with entry.lock:
            if entry.state != CircuitState.HALF_OPEN:
                return entry.state == CircuitState.CLOSED

            now = time.monotonic()
            if entry.last_probe_at is None or (now - entry.last_probe_at) >= PROBE_INTERVAL_S:
                entry.last_probe_at = now
                return True
            return False

    async def evaluate_endpoint(self, endpoint: str) -> None:
        """
        Evaluate whether an endpoint should transition states based on failure rate.
        Called by SurgeonMiddleware after recording a response.

        Transition logic:
            CLOSED → OPEN:  failure_rate > 50% AND total_requests >= 10
        """
        if _is_excluded(endpoint):
            return

        tracker = get_failure_tracker()
        failure_rate = await tracker.get_failure_rate(endpoint)
        request_count = await tracker.get_request_count(endpoint)

        entry = await self._get_or_create_entry(endpoint)

        async with entry.lock:
            if entry.state == CircuitState.CLOSED:
                if (request_count >= MIN_REQUESTS_IN_WINDOW
                        and failure_rate > FAILURE_RATE_THRESHOLD):
                    await self._transition_to_open(endpoint, entry, failure_rate)

    async def record_probe_result(self, endpoint: str, success: bool) -> None:
        """
        Record the result of a probe request in HALF_OPEN state.

        success=True  → HALF_OPEN → CLOSED (recovered)
        success=False → HALF_OPEN → OPEN (reset quarantine timer)
        """
        entry = self._circuits.get(endpoint)
        if entry is None:
            return

        async with entry.lock:
            if entry.state != CircuitState.HALF_OPEN:
                return

            if success:
                recovery_time = 0.0
                if entry.opened_at is not None:
                    recovery_time = time.monotonic() - entry.opened_at
                await self._transition_to_closed(endpoint, entry, recovery_time)
            else:
                # Failed probe → back to OPEN, reset quarantine timer
                await self._transition_to_open_from_half(endpoint, entry)

    async def force_open(self, endpoint: str) -> bool:
        """
        Manually force a circuit OPEN (for testing / admin API).
        Returns False for blast-radius protected routes.
        """
        if _is_excluded(endpoint):
            logger.warning("circuit_force_open_blocked", endpoint=endpoint,
                           reason="blast_radius_protected")
            return False

        entry = await self._get_or_create_entry(endpoint)
        async with entry.lock:
            await self._transition_to_open(endpoint, entry, failure_rate=1.0)
        return True

    async def force_closed(self, endpoint: str) -> None:
        """Manually force a circuit CLOSED (for testing / admin API)."""
        entry = self._circuits.get(endpoint)
        if entry is not None:
            async with entry.lock:
                entry.state = CircuitState.CLOSED
                entry.opened_at = None
                entry.last_probe_at = None
                logger.info("circuit_force_closed", endpoint=endpoint)

    # ── Internal transition methods ──────────────────────────────────────────

    async def _transition_to_open(self, endpoint: str, entry: _CircuitEntry,
                                  failure_rate: float) -> None:
        """CLOSED → OPEN (quarantine)."""
        entry.state = CircuitState.OPEN
        entry.opened_at = time.monotonic()
        entry.last_probe_at = None
        entry.failure_rate_at_open = failure_rate

        logger.error(
            "circuit_breaker_OPEN",
            endpoint=endpoint,
            failure_rate=round(failure_rate, 4),
            quarantine_duration_s=QUARANTINE_DURATION_S,
        )

        # Post Vanguard incident
        await self._post_incident(
            incident_type="CIRCUIT_OPENED",
            severity="RED",
            endpoint=endpoint,
            metadata={"failure_rate": round(failure_rate, 4)},
        )

        # Reset the failure tracker so HALF_OPEN gets a clean window
        tracker = get_failure_tracker()
        await tracker.reset_endpoint(endpoint)

    async def _transition_to_open_from_half(self, endpoint: str,
                                            entry: _CircuitEntry) -> None:
        """HALF_OPEN → OPEN (probe failed, reset quarantine timer)."""
        entry.state = CircuitState.OPEN
        entry.opened_at = time.monotonic()  # reset timer
        entry.last_probe_at = None

        logger.warning(
            "circuit_breaker_probe_failed",
            endpoint=endpoint,
            message="Probe failed, resetting quarantine timer",
        )

    async def _transition_to_half_open(self, endpoint: str,
                                       entry: _CircuitEntry) -> None:
        """OPEN → HALF_OPEN (quarantine expired, allow probing)."""
        entry.state = CircuitState.HALF_OPEN
        entry.last_probe_at = None

        logger.info(
            "circuit_breaker_HALF_OPEN",
            endpoint=endpoint,
            message="Quarantine expired, allowing probe requests",
        )

        # Reset failure tracker for clean probe measurement
        tracker = get_failure_tracker()
        await tracker.reset_endpoint(endpoint)

    async def _transition_to_closed(self, endpoint: str,
                                    entry: _CircuitEntry,
                                    recovery_time_s: float) -> None:
        """HALF_OPEN → CLOSED (probe succeeded, recovered)."""
        entry.state = CircuitState.CLOSED
        entry.opened_at = None
        entry.last_probe_at = None

        logger.info(
            "circuit_breaker_CLOSED",
            endpoint=endpoint,
            recovery_time_s=round(recovery_time_s, 2),
            message="Circuit recovered",
        )

        # Post recovery incident
        await self._post_incident(
            incident_type="CIRCUIT_RECOVERED",
            severity="GREEN",
            endpoint=endpoint,
            metadata={"recovery_time_s": round(recovery_time_s, 2)},
        )

    async def _post_incident(self, incident_type: str, severity: str,
                             endpoint: str, metadata: dict) -> None:
        """Post a Vanguard incident for circuit state transitions."""
        try:
            from ..archivist.storage import get_incident_storage
            storage = get_incident_storage()

            from ..inquisitor.fingerprint import generate_error_fingerprint
            fingerprint = generate_error_fingerprint(
                exception_type=incident_type,
                traceback_lines=[f"{incident_type} {endpoint}"],
                endpoint=endpoint,
            )

            incident = {
                "fingerprint": fingerprint,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": severity,
                "status": "ACTIVE" if severity == "RED" else "resolved",
                "error_type": incident_type,
                "error_message": f"{incident_type}: {endpoint}",
                "endpoint": endpoint,
                "request_id": "surgeon-circuit-breaker",
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
            logger.info("circuit_incident_posted", type=incident_type, endpoint=endpoint)
        except Exception as e:
            # Incident posting failure must NEVER block circuit transitions
            logger.error("circuit_incident_post_failed", error=str(e),
                         type=incident_type, endpoint=endpoint)

    async def _get_or_create_entry(self, endpoint: str) -> _CircuitEntry:
        """Get or create a circuit entry for an endpoint."""
        if endpoint in self._circuits:
            return self._circuits[endpoint]

        async with self._global_lock:
            if endpoint in self._circuits:
                return self._circuits[endpoint]
            entry = _CircuitEntry()
            self._circuits[endpoint] = entry
            return entry

    def get_all_states(self) -> Dict[str, Dict]:
        """Diagnostic snapshot of all circuit states (for admin/health)."""
        now = time.monotonic()
        snapshot = {}
        for endpoint, entry in self._circuits.items():
            data = {
                "state": entry.state.value,
                "failure_rate_at_open": round(entry.failure_rate_at_open, 4),
            }
            if entry.opened_at is not None:
                data["quarantine_elapsed_s"] = round(now - entry.opened_at, 1)
            snapshot[endpoint] = data
        return snapshot


# ── Singleton ────────────────────────────────────────────────────────────────
_circuit_breaker_v2: Optional[CircuitBreakerV2] = None


def get_circuit_breaker_v2() -> CircuitBreakerV2:
    """Get or create the global CircuitBreakerV2 singleton."""
    global _circuit_breaker_v2
    if _circuit_breaker_v2 is None:
        _circuit_breaker_v2 = CircuitBreakerV2()
        logger.info(
            "circuit_breaker_v2_initialized",
            threshold=FAILURE_RATE_THRESHOLD,
            min_requests=MIN_REQUESTS_IN_WINDOW,
            quarantine_s=QUARANTINE_DURATION_S,
        )
    return _circuit_breaker_v2
