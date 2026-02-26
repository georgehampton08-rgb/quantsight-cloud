"""
Tests for CircuitBreakerV2 — Phase 4 Step 4.3 verification
============================================================
Uses asyncio.run() directly — no pytest-asyncio dependency required.

Covers:
  1. State transitions with mocked failure tracker
  2. Blast radius routes cannot be set to OPEN
  3. CIRCUIT_OPENED incident created on OPEN transition
  4. CIRCUIT_RECOVERED incident created on CLOSED recovery
  5. HALF_OPEN → OPEN on failed probe
  6. HALF_OPEN → CLOSED on successful probe
  7. Minimum request threshold prevents false positives
  8. force_open / force_closed admin controls
"""

import asyncio
import time
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from vanguard.surgeon.circuit_breaker_v2 import (
    CircuitBreakerV2,
    CircuitState,
    FAILURE_RATE_THRESHOLD,
    MIN_REQUESTS_IN_WINDOW,
    QUARANTINE_DURATION_S,
    PROBE_INTERVAL_S,
)
from vanguard.surgeon.failure_tracker import FailureTracker


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Test 1: CLOSED → OPEN when failure rate exceeds threshold ──────────────
def test_closed_to_open_transition():
    async def _test():
        cb = CircuitBreakerV2()
        tracker = FailureTracker()
        endpoint = "/players/broken"

        # Record enough failures to exceed threshold
        for _ in range(4):
            await tracker.record(endpoint, 200)  # 4 success
        for _ in range(8):
            await tracker.record(endpoint, 500)  # 8 failures = 66% > 50%

        # Total = 12 > min 10, rate = 0.66 > 0.50
        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            await cb.evaluate_endpoint(endpoint)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.OPEN, f"Expected OPEN, got {state}"

    _run(_test())


# ── Test 2: Blast radius routes cannot be set to OPEN ──────────────────────
def test_blast_radius_protection():
    async def _test():
        cb = CircuitBreakerV2()
        protected_routes = [
            "/healthz",
            "/readyz",
            "/health",
            "/health/deps",
            "/vanguard/health",
            "/vanguard/admin/incidents",
            "/admin/seed/data",
        ]

        for route in protected_routes:
            result = await cb.force_open(route)
            assert result is False, f"force_open should return False for {route}"

            state = await cb.get_state(route)
            assert state == CircuitState.CLOSED, f"Protected route {route} should always be CLOSED"

    _run(_test())


# ── Test 3: CIRCUIT_OPENED incident created on OPEN transition ─────────────
def test_circuit_opened_incident():
    async def _test():
        cb = CircuitBreakerV2()
        tracker = FailureTracker()
        endpoint = "/test/incident"
        incidents_posted = []

        # Mock storage to capture incidents
        async def mock_store(incident):
            incidents_posted.append(incident)
            return True

        mock_storage = MagicMock()
        mock_storage.store = mock_store

        # Set up failure data
        for _ in range(5):
            await tracker.record(endpoint, 200)
        for _ in range(15):
            await tracker.record(endpoint, 500)

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            with patch("vanguard.archivist.storage.get_incident_storage", return_value=mock_storage):
                await cb.evaluate_endpoint(endpoint)

        assert len(incidents_posted) == 1, f"Expected 1 incident, got {len(incidents_posted)}"
        incident = incidents_posted[0]
        assert incident["error_type"] == "CIRCUIT_OPENED"
        assert incident["severity"] == "RED"
        assert incident["endpoint"] == endpoint

    _run(_test())


# ── Test 4: CIRCUIT_RECOVERED incident on successful probe ─────────────────
def test_circuit_recovered_incident():
    async def _test():
        cb = CircuitBreakerV2()
        endpoint = "/test/recovery"
        incidents_posted = []

        async def mock_store(incident):
            incidents_posted.append(incident)
            return True

        mock_storage = MagicMock()
        mock_storage.store = mock_store

        # Force circuit OPEN
        with patch("vanguard.archivist.storage.get_incident_storage", return_value=mock_storage):
            with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker") as mock_ft:
                mock_tracker = FailureTracker()
                mock_ft.return_value = mock_tracker
                await cb.force_open(endpoint)

        incidents_posted.clear()  # Clear the CIRCUIT_OPENED incident

        # Manually set to HALF_OPEN
        entry = cb._circuits[endpoint]
        entry.state = CircuitState.HALF_OPEN

        # Record successful probe
        with patch("vanguard.archivist.storage.get_incident_storage", return_value=mock_storage):
            await cb.record_probe_result(endpoint, success=True)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.CLOSED, f"Expected CLOSED after recovery, got {state}"

        assert len(incidents_posted) == 1
        assert incidents_posted[0]["error_type"] == "CIRCUIT_RECOVERED"
        assert incidents_posted[0]["severity"] == "GREEN"

    _run(_test())


# ── Test 5: HALF_OPEN → OPEN on failed probe ──────────────────────────────
def test_half_open_to_open_on_failed_probe():
    async def _test():
        cb = CircuitBreakerV2()
        endpoint = "/test/probe-fail"

        # Create an entry in HALF_OPEN
        entry = await cb._get_or_create_entry(endpoint)
        entry.state = CircuitState.HALF_OPEN
        entry.opened_at = time.monotonic() - 100  # opened 100s ago

        await cb.record_probe_result(endpoint, success=False)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.OPEN, f"Expected OPEN after failed probe, got {state}"

        # Verify quarantine timer was reset (opened_at should be recent)
        assert entry.opened_at is not None
        elapsed = time.monotonic() - entry.opened_at
        assert elapsed < 5, f"Quarantine timer should be reset, elapsed={elapsed}"

    _run(_test())


# ── Test 6: OPEN → HALF_OPEN after quarantine period ──────────────────────
def test_open_to_half_open_after_quarantine():
    async def _test():
        cb = CircuitBreakerV2()
        endpoint = "/test/quarantine-expire"

        entry = await cb._get_or_create_entry(endpoint)
        entry.state = CircuitState.OPEN
        entry.opened_at = time.monotonic() - QUARANTINE_DURATION_S - 1  # expired

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker") as mock_ft:
            mock_ft.return_value = FailureTracker()
            state = await cb.get_state(endpoint)

        assert state == CircuitState.HALF_OPEN, f"Expected HALF_OPEN, got {state}"

    _run(_test())


# ── Test 7: Below minimum request threshold → no transition ───────────────
def test_minimum_request_threshold():
    async def _test():
        cb = CircuitBreakerV2()
        tracker = FailureTracker()
        endpoint = "/test/low-traffic"

        # Only 5 requests (below MIN_REQUESTS_IN_WINDOW=10), all failures
        for _ in range(5):
            await tracker.record(endpoint, 500)

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            await cb.evaluate_endpoint(endpoint)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.CLOSED, (
            f"Expected CLOSED (low traffic should not trigger), got {state}"
        )

    _run(_test())


# ── Test 8: force_open and force_closed admin controls ────────────────────
def test_force_open_and_close():
    async def _test():
        cb = CircuitBreakerV2()
        endpoint = "/test/admin-force"

        with patch("vanguard.archivist.storage.get_incident_storage") as mock_si:
            mock_storage = MagicMock()
            mock_storage.store = AsyncMock(return_value=True)
            mock_si.return_value = mock_storage
            with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker") as mock_ft:
                mock_ft.return_value = FailureTracker()
                result = await cb.force_open(endpoint)

        assert result is True
        state = await cb.get_state(endpoint)
        assert state == CircuitState.OPEN

        await cb.force_closed(endpoint)
        state = await cb.get_state(endpoint)
        assert state == CircuitState.CLOSED

    _run(_test())


# ── Test 9: get_all_states diagnostic snapshot ────────────────────────────
def test_get_all_states():
    async def _test():
        cb = CircuitBreakerV2()
        entry = await cb._get_or_create_entry("/test/snapshot")
        entry.state = CircuitState.OPEN
        entry.opened_at = time.monotonic()
        entry.failure_rate_at_open = 0.75

        snapshot = cb.get_all_states()
        assert "/test/snapshot" in snapshot
        assert snapshot["/test/snapshot"]["state"] == "OPEN"
        assert snapshot["/test/snapshot"]["failure_rate_at_open"] == 0.75

    _run(_test())


# ── Test 10: Unknown endpoint returns CLOSED ──────────────────────────────
def test_unknown_endpoint_is_closed():
    async def _test():
        cb = CircuitBreakerV2()
        state = await cb.get_state("/never/registered")
        assert state == CircuitState.CLOSED

    _run(_test())


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
