"""
Tests for FailureTracker — Phase 4 Step 4.2 verification
=========================================================
Uses asyncio.run() directly — no pytest-asyncio dependency required.

Covers:
  1. 30 failures out of 40 requests → failure rate = 0.75
  2. Window expires → failure rate resets to 0.0
  3. Excluded routes never appear in tracker
  4. _is_excluded and _is_failure helpers
  5. LRU eviction at max capacity
  6. reset_endpoint clears counters
  7. record_exception counts as failure
  8. get_all_rates diagnostic snapshot
"""

import asyncio
import time
import sys
import os

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from vanguard.surgeon.failure_tracker import (
    FailureTracker,
    _is_excluded,
    _is_failure,
    WINDOW_SECONDS,
    MAX_ENDPOINTS,
)


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Test 1: Failure rate = 0.75 with 30 fails out of 40 requests ──────────
def test_failure_rate_calculation():
    async def _test():
        tracker = FailureTracker()
        endpoint = "/players/123"

        for _ in range(10):
            await tracker.record(endpoint, 200)
        for _ in range(30):
            await tracker.record(endpoint, 500)

        rate = await tracker.get_failure_rate(endpoint)
        assert rate == 0.75, f"Expected 0.75, got {rate}"

        count = await tracker.get_request_count(endpoint)
        assert count == 40, f"Expected 40 total requests, got {count}"

    _run(_test())


# ── Test 2: Window expires → failure rate resets to 0.0 ────────────────────
def test_window_expiry_resets_rate():
    async def _test():
        tracker = FailureTracker()
        endpoint = "/teams/456"

        for _ in range(10):
            await tracker.record(endpoint, 503)

        rate_before = await tracker.get_failure_rate(endpoint)
        assert rate_before == 1.0, f"Expected 1.0, got {rate_before}"

        # Fast-forward time past the window
        window = tracker._windows[endpoint]
        window.window_start = time.monotonic() - WINDOW_SECONDS - 1

        rate_after = await tracker.get_failure_rate(endpoint)
        assert rate_after == 0.0, f"Expected 0.0 after window expiry, got {rate_after}"

    _run(_test())


# ── Test 3: Excluded routes never appear in tracker ────────────────────────
def test_excluded_routes_not_tracked():
    async def _test():
        tracker = FailureTracker()
        excluded_routes = [
            "/healthz",
            "/readyz",
            "/health",
            "/health/deps",
            "/vanguard/health",
            "/vanguard/admin/incidents",
            "/admin/seed/data",
        ]

        for route in excluded_routes:
            await tracker.record(route, 500)
            await tracker.record(route, 200)

        assert len(tracker._windows) == 0, (
            f"Expected 0 windows, got {len(tracker._windows)}: {list(tracker._windows.keys())}"
        )

        for route in excluded_routes:
            rate = await tracker.get_failure_rate(route)
            assert rate == 0.0, f"Excluded route {route} has rate {rate}"

    _run(_test())


# ── Test 4: _is_excluded helper ────────────────────────────────────────────
def test_is_excluded_helper():
    assert _is_excluded("/healthz") is True
    assert _is_excluded("/readyz") is True
    assert _is_excluded("/health") is True
    assert _is_excluded("/health/deps") is True
    assert _is_excluded("/vanguard/admin/incidents") is True
    assert _is_excluded("/vanguard/health") is True
    assert _is_excluded("/admin/seed") is True

    assert _is_excluded("/players/123") is False
    assert _is_excluded("/teams/LAL") is False
    assert _is_excluded("/matchup/analyze") is False
    assert _is_excluded("/aegis/simulate") is False
    assert _is_excluded("/live/stream") is False


# ── Test 5: _is_failure helper ─────────────────────────────────────────────
def test_is_failure_helper():
    assert _is_failure(500) is True
    assert _is_failure(502) is True
    assert _is_failure(503) is True
    assert _is_failure(504) is True

    assert _is_failure(200) is False
    assert _is_failure(201) is False
    assert _is_failure(301) is False
    assert _is_failure(400) is False
    assert _is_failure(401) is False
    assert _is_failure(403) is False
    assert _is_failure(404) is False
    assert _is_failure(422) is False
    assert _is_failure(429) is False


# ── Test 6: LRU eviction at max capacity ──────────────────────────────────
def test_lru_eviction():
    async def _test():
        tracker = FailureTracker()

        for i in range(MAX_ENDPOINTS):
            await tracker.record(f"/test/endpoint-{i}", 200)

        assert len(tracker._windows) == MAX_ENDPOINTS

        await tracker.record("/test/overflow", 200)
        assert len(tracker._windows) == MAX_ENDPOINTS
        assert "/test/overflow" in tracker._windows

    _run(_test())


# ── Test 7: reset_endpoint clears counters ────────────────────────────────
def test_reset_endpoint():
    async def _test():
        tracker = FailureTracker()
        endpoint = "/teams/reset-me"

        for _ in range(20):
            await tracker.record(endpoint, 500)

        rate = await tracker.get_failure_rate(endpoint)
        assert rate == 1.0

        await tracker.reset_endpoint(endpoint)

        rate_after = await tracker.get_failure_rate(endpoint)
        assert rate_after == 0.0, f"Expected 0.0 after reset, got {rate_after}"

    _run(_test())


# ── Test 8: Unknown endpoint returns 0.0 rate and 0 count ─────────────────
def test_unknown_endpoint_defaults():
    async def _test():
        tracker = FailureTracker()
        rate = await tracker.get_failure_rate("/never/seen")
        assert rate == 0.0
        count = await tracker.get_request_count("/never/seen")
        assert count == 0

    _run(_test())


# ── Test 9: record_exception counts as failure ────────────────────────────
def test_record_exception():
    async def _test():
        tracker = FailureTracker()
        endpoint = "/matchup/crash"

        await tracker.record(endpoint, 200)
        await tracker.record_exception(endpoint)

        rate = await tracker.get_failure_rate(endpoint)
        assert rate == 0.5, f"Expected 0.5, got {rate}"

    _run(_test())


# ── Test 10: get_all_rates diagnostic snapshot ────────────────────────────
def test_get_all_rates():
    async def _test():
        tracker = FailureTracker()
        await tracker.record("/test/a", 200)
        await tracker.record("/test/a", 500)
        await tracker.record("/test/b", 200)

        snapshot = tracker.get_all_rates()
        assert "/test/a" in snapshot
        assert "/test/b" in snapshot
        assert snapshot["/test/a"]["total"] == 2
        assert snapshot["/test/a"]["failed"] == 1
        assert snapshot["/test/a"]["failure_rate"] == 0.5
        assert snapshot["/test/b"]["total"] == 1
        assert snapshot["/test/b"]["failed"] == 0

    _run(_test())


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
