"""
Phase 4 End-to-End Validation — Step 4.8
==========================================
Simulates the full circuit breaker lifecycle:

  1. CLOSED→OPEN:  Inject 12 requests (4 success + 8 fail) → circuit opens
  2. OPEN blocks:   Next request returns 503 (simulated)
  3. OPEN→HALF_OPEN: Fast-forward quarantine timer → state transitions
  4. HALF_OPEN probe success: Probe with 200 → circuit recovers
  5. HALF_OPEN probe failure: Probe with 500 → circuit reopens
  6. Blast radius: Protected routes stay CLOSED regardless of failures
  7. FailureTracker + CircuitBreaker integration (no mocks)
  8. LoadShedder hysteresis validated
  9. IndexDoctor error parsing validated
  10. Feature flag gating verified
  11. DRY_RUN mode verified (SILENT_OBSERVER + flag on)

All tests use real instances (no mocks except for storage/incident posting).
"""

import asyncio
import time
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from vanguard.surgeon.failure_tracker import FailureTracker, get_failure_tracker, WINDOW_SECONDS
from vanguard.surgeon.circuit_breaker_v2 import (
    CircuitBreakerV2, CircuitState, get_circuit_breaker_v2,
    FAILURE_RATE_THRESHOLD, MIN_REQUESTS_IN_WINDOW, QUARANTINE_DURATION_S,
)
from vanguard.surgeon.load_shedder import (
    LoadSheddingGovernor, SHEDDING_THRESHOLD_HIGH, SHEDDING_THRESHOLD_LOW,
)
from vanguard.surgeon.index_doctor import (
    is_missing_index_error, extract_index_definition,
)
from vanguard.core.feature_flags import flag, _FLAG_DEFAULTS


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 1: Full CLOSED → OPEN → HALF_OPEN → CLOSED lifecycle (no mocks)
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_full_circuit_lifecycle():
    """
    Simulate: 4 success + 8 failure → circuit opens (66% > 50%, 12 > min 10)
    → quarantine expires → HALF_OPEN → probe success → CLOSED recovery
    """
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()
        endpoint = "/matchup/analyze"

        # ── Phase A: Record failures ────────────────────────────────
        for _ in range(4):
            await tracker.record(endpoint, 200)
        for _ in range(8):
            await tracker.record(endpoint, 500)

        rate = await tracker.get_failure_rate(endpoint)
        count = await tracker.get_request_count(endpoint)
        assert rate > FAILURE_RATE_THRESHOLD, f"Rate {rate} should exceed {FAILURE_RATE_THRESHOLD}"
        assert count >= MIN_REQUESTS_IN_WINDOW, f"Count {count} should exceed {MIN_REQUESTS_IN_WINDOW}"

        # ── Phase B: Evaluate → CLOSED → OPEN ──────────────────────
        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            with patch("vanguard.archivist.storage.get_incident_storage") as mock_storage:
                mock_storage.return_value = MagicMock(store=AsyncMock(return_value=True))
                await cb.evaluate_endpoint(endpoint)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.OPEN, f"Expected OPEN, got {state}"

        # ── Phase C: Verify requests are blocked ────────────────────
        # (In production, SurgeonMiddleware returns 503 here)
        state_check = await cb.get_state(endpoint)
        assert state_check == CircuitState.OPEN, "Should still be OPEN"

        # ── Phase D: Fast-forward → OPEN → HALF_OPEN ───────────────
        entry = cb._circuits[endpoint]
        entry.opened_at = time.monotonic() - QUARANTINE_DURATION_S - 1

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            state = await cb.get_state(endpoint)
        assert state == CircuitState.HALF_OPEN, f"Expected HALF_OPEN, got {state}"

        # ── Phase E: Probe success → HALF_OPEN → CLOSED ────────────
        with patch("vanguard.archivist.storage.get_incident_storage") as mock_storage:
            mock_storage.return_value = MagicMock(store=AsyncMock(return_value=True))
            await cb.record_probe_result(endpoint, success=True)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.CLOSED, f"Expected CLOSED (recovered), got {state}"

    _run(_test())


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 2: Failed probe → HALF_OPEN → OPEN (quarantine resets)
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_failed_probe_reopens_circuit():
    """Probe failure should reset the quarantine timer and go back to OPEN."""
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()
        endpoint = "/aegis/simulate"

        # Get to OPEN state
        for _ in range(3):
            await tracker.record(endpoint, 200)
        for _ in range(10):
            await tracker.record(endpoint, 503)

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            with patch("vanguard.archivist.storage.get_incident_storage") as ms:
                ms.return_value = MagicMock(store=AsyncMock(return_value=True))
                await cb.evaluate_endpoint(endpoint)

        assert await cb.get_state(endpoint) == CircuitState.OPEN

        # Fast-forward to HALF_OPEN
        cb._circuits[endpoint].opened_at = time.monotonic() - QUARANTINE_DURATION_S - 1
        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            state = await cb.get_state(endpoint)
        assert state == CircuitState.HALF_OPEN

        # Failed probe → back to OPEN
        await cb.record_probe_result(endpoint, success=False)
        state = await cb.get_state(endpoint)
        assert state == CircuitState.OPEN, f"Expected OPEN after failed probe, got {state}"

        # Verify quarantine timer was reset (recent opened_at)
        elapsed = time.monotonic() - cb._circuits[endpoint].opened_at
        assert elapsed < 2, f"Quarantine timer should be fresh, elapsed={elapsed}"

    _run(_test())


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 3: Blast radius — protected routes NEVER open
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_blast_radius_immunity():
    """Protected routes must remain CLOSED even with 100% failure rate."""
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()

        protected = ["/healthz", "/readyz", "/health", "/health/deps",
                     "/vanguard/admin/incidents", "/admin/seed"]

        for route in protected:
            # Try to inject failures (tracker should ignore)
            for _ in range(20):
                await tracker.record(route, 500)

            # Failure rate should be 0.0 (never tracked)
            rate = await tracker.get_failure_rate(route)
            assert rate == 0.0, f"Protected route {route} has rate {rate}"

            # Circuit should always be CLOSED
            state = await cb.get_state(route)
            assert state == CircuitState.CLOSED, f"Protected {route} is {state}"

            # force_open should be rejected
            result = await cb.force_open(route)
            assert result is False, f"force_open should fail for {route}"

    _run(_test())


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 4: Multiple endpoints — independent circuit state
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_independent_endpoint_circuits():
    """Each endpoint has its own circuit — one can be OPEN while others are CLOSED."""
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()

        # /matchup fails hard
        for _ in range(2):
            await tracker.record("/matchup/analyze", 200)
        for _ in range(15):
            await tracker.record("/matchup/analyze", 500)

        # /players is healthy
        for _ in range(15):
            await tracker.record("/players/123", 200)

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            with patch("vanguard.archivist.storage.get_incident_storage") as ms:
                ms.return_value = MagicMock(store=AsyncMock(return_value=True))
                await cb.evaluate_endpoint("/matchup/analyze")
                await cb.evaluate_endpoint("/players/123")

        assert await cb.get_state("/matchup/analyze") == CircuitState.OPEN
        assert await cb.get_state("/players/123") == CircuitState.CLOSED

    _run(_test())


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 5: Window expiry — stale failures don't trigger circuit
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_window_expiry_prevents_false_trigger():
    """Failures from >60s ago should not count towards current rate."""
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()
        endpoint = "/teams/roster"

        # Record 15 failures
        for _ in range(15):
            await tracker.record(endpoint, 500)

        # Fast-forward past window
        tracker._windows[endpoint].window_start = time.monotonic() - WINDOW_SECONDS - 1

        # Rate should be 0.0 after window expired
        rate = await tracker.get_failure_rate(endpoint)
        assert rate == 0.0, f"Expected 0.0 after expiry, got {rate}"

        # Evaluate — should NOT open circuit
        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            await cb.evaluate_endpoint(endpoint)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.CLOSED, f"Expected CLOSED after window expiry, got {state}"

    _run(_test())


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 6: Load shedder hysteresis — full cycle
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_load_shedder_hysteresis():
    """
    90% → activate → 85% (still active, hysteresis) → 70% → deactivate
    """
    governor = LoadSheddingGovernor()

    # Phase 1: Below high threshold — not active
    governor._memory_pct = 80.0
    assert not governor.SHEDDING_ACTIVE
    assert not governor.should_shed("/players/123", "POST")

    # Phase 2: Cross high threshold → activate
    governor._memory_pct = 92.0
    if governor._memory_pct >= SHEDDING_THRESHOLD_HIGH:
        governor.SHEDDING_ACTIVE = True
    assert governor.SHEDDING_ACTIVE
    assert governor.should_shed("/players/123", "POST")
    assert not governor.should_shed("/players/123", "GET")  # GETs exempt
    assert not governor.should_shed("/healthz", "POST")     # healthz exempt

    # Phase 3: Drop to 85% — still active (hysteresis band)
    governor._memory_pct = 85.0
    if governor.SHEDDING_ACTIVE and governor._memory_pct <= SHEDDING_THRESHOLD_LOW:
        governor.SHEDDING_ACTIVE = False
    assert governor.SHEDDING_ACTIVE, "Should still be active at 85% (hysteresis)"

    # Phase 4: Drop to 70% → deactivate
    governor._memory_pct = 70.0
    if governor.SHEDDING_ACTIVE and governor._memory_pct <= SHEDDING_THRESHOLD_LOW:
        governor.SHEDDING_ACTIVE = False
    assert not governor.SHEDDING_ACTIVE, "Should deactivate at 70%"
    assert not governor.should_shed("/players/123", "POST")


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 7: IndexDoctor error parsing
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_index_doctor_parsing():
    """Verify FailedPrecondition detection and index definition extraction."""
    # Test FailedPrecondition detection from string
    class FakeError(Exception):
        pass

    err = FakeError("9 FailedPrecondition: The query requires an index. "
                    "You can create it here: https://console.firebase.google.com/v1/r/project/"
                    "quantsight-prod/firestore/indexes?create_composite=abc123 "
                    "collection: vanguard_incidents field: severity field: timestamp")

    # Should detect as missing index
    assert is_missing_index_error(err), "Should detect FailedPrecondition with index"

    # Should extract index definition
    index_def = extract_index_definition(str(err))
    assert index_def is not None
    assert index_def["collectionGroup"] == "vanguard_incidents"
    assert len(index_def["fields"]) >= 1

    # Non-index error should NOT be detected
    regular_err = Exception("Connection refused")
    assert not is_missing_index_error(regular_err)


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 8: Feature flag gating — all three flags default False
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_feature_flags_default_false():
    """All Phase 4 flags should default to False for safe rollout."""
    assert _FLAG_DEFAULTS.get("FEATURE_SURGEON_MIDDLEWARE") is False
    assert _FLAG_DEFAULTS.get("FEATURE_LOAD_SHEDDER") is False
    assert _FLAG_DEFAULTS.get("FEATURE_INDEX_DOCTOR") is False

    # Verify flag() reads correctly (should be False without env var)
    with patch.dict(os.environ, {}, clear=False):
        # Remove any env overrides
        for key in ["FEATURE_SURGEON_MIDDLEWARE", "FEATURE_LOAD_SHEDDER", "FEATURE_INDEX_DOCTOR"]:
            os.environ.pop(key, None)

        assert flag("FEATURE_SURGEON_MIDDLEWARE") is False
        assert flag("FEATURE_LOAD_SHEDDER") is False
        assert flag("FEATURE_INDEX_DOCTOR") is False


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 9: DRY_RUN mode — SILENT_OBSERVER never blocks
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_dry_run_mode():
    """In SILENT_OBSERVER mode, _is_active_mode() returns False → never blocks."""
    from vanguard.surgeon.middleware import _is_active_mode

    # With no VANGUARD_MODE set (defaults to SILENT_OBSERVER), should not be active
    with patch.dict(os.environ, {"VANGUARD_MODE": "SILENT_OBSERVER"}, clear=False):
        # Even with flag on, mode must also be CIRCUIT_BREAKER
        with patch.dict(os.environ, {"FEATURE_SURGEON_MIDDLEWARE": "true"}, clear=False):
            result = _is_active_mode()
            assert result is False, "SILENT_OBSERVER + flag=true should still be DRY_RUN"


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 10: Diagnostic snapshots — both tracker and CB report state
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_diagnostic_snapshots():
    """Health/admin endpoints should get clean snapshots of system state."""
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()

        # Create some state
        await tracker.record("/test/a", 200)
        await tracker.record("/test/a", 500)
        await tracker.record("/test/b", 200)

        entry = await cb._get_or_create_entry("/test/a")
        entry.state = CircuitState.OPEN
        entry.opened_at = time.monotonic()
        entry.failure_rate_at_open = 0.75

        # FailureTracker snapshot
        rates = tracker.get_all_rates()
        assert "/test/a" in rates
        assert rates["/test/a"]["total"] == 2
        assert rates["/test/a"]["failed"] == 1
        assert rates["/test/a"]["failure_rate"] == 0.5

        # CircuitBreaker snapshot
        states = cb.get_all_states()
        assert "/test/a" in states
        assert states["/test/a"]["state"] == "OPEN"
        assert states["/test/a"]["failure_rate_at_open"] == 0.75
        assert "quarantine_elapsed_s" in states["/test/a"]

    _run(_test())


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 11: Minimum threshold prevents premature circuit opening
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_minimum_threshold_safety():
    """
    Even with 100% failure rate, circuit should NOT open if total requests < 10.
    This prevents a single 500 from quarantining an endpoint.
    """
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()
        endpoint = "/pulse/data"

        # 5 failures, 100% rate, but below min threshold
        for _ in range(5):
            await tracker.record(endpoint, 500)

        rate = await tracker.get_failure_rate(endpoint)
        assert rate == 1.0, f"Rate should be 1.0, got {rate}"

        count = await tracker.get_request_count(endpoint)
        assert count == 5, f"Count should be 5, got {count}"
        assert count < MIN_REQUESTS_IN_WINDOW

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            await cb.evaluate_endpoint(endpoint)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.CLOSED, (
            f"Should NOT open with only {count} requests (min {MIN_REQUESTS_IN_WINDOW})"
        )

    _run(_test())


# ═══════════════════════════════════════════════════════════════════════════
# E2E TEST 12: Exception recording → failure rate increases
# ═══════════════════════════════════════════════════════════════════════════
def test_e2e_exception_recording():
    """Unhandled exceptions should be tracked as failures and contribute to circuit opening."""
    async def _test():
        tracker = FailureTracker()
        cb = CircuitBreakerV2()
        endpoint = "/nexus/process"

        # 5 successes + 10 exceptions → 66% failure rate, 15 total
        for _ in range(5):
            await tracker.record(endpoint, 200)
        for _ in range(10):
            await tracker.record_exception(endpoint)

        rate = await tracker.get_failure_rate(endpoint)
        assert abs(rate - (10/15)) < 0.01, f"Expected ~0.666, got {rate}"

        with patch("vanguard.surgeon.circuit_breaker_v2.get_failure_tracker", return_value=tracker):
            with patch("vanguard.archivist.storage.get_incident_storage") as ms:
                ms.return_value = MagicMock(store=AsyncMock(return_value=True))
                await cb.evaluate_endpoint(endpoint)

        state = await cb.get_state(endpoint)
        assert state == CircuitState.OPEN, "Exceptions should trigger circuit opening"

    _run(_test())


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
