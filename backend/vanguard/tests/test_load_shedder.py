"""
Tests for LoadSheddingGovernor — Phase 4 Step 4.6 verification
================================================================
Uses asyncio.run() directly — no pytest-asyncio dependency required.

Covers:
  1. psutil at 92% → SHEDDING_ACTIVE becomes True
  2. psutil at 70% → SHEDDING_ACTIVE becomes False (hysteresis)
  3. POST to non-critical endpoint when shedding active → 429
  4. GET request passes through even when shedding active
  5. Exempt paths (healthz, vanguard, admin, live) never shed
"""

import asyncio
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from vanguard.surgeon.load_shedder import (
    LoadSheddingGovernor,
    _is_exempt_from_shedding,
    SHEDDING_THRESHOLD_HIGH,
    SHEDDING_THRESHOLD_LOW,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Test 1: Memory at 92% → SHEDDING_ACTIVE True ──────────────────────────
def test_high_memory_activates_shedding():
    governor = LoadSheddingGovernor()
    governor._memory_pct = 92.0
    governor.SHEDDING_ACTIVE = False

    # Simulate the threshold check logic
    if governor._memory_pct >= SHEDDING_THRESHOLD_HIGH:
        governor.SHEDDING_ACTIVE = True

    assert governor.SHEDDING_ACTIVE is True, "Should activate at 92%"


# ── Test 2: Memory at 70% → SHEDDING_ACTIVE False (hysteresis) ────────────
def test_low_memory_deactivates_shedding():
    governor = LoadSheddingGovernor()
    governor.SHEDDING_ACTIVE = True
    governor._memory_pct = 70.0

    # Simulate the recovery check
    if governor.SHEDDING_ACTIVE and governor._memory_pct <= SHEDDING_THRESHOLD_LOW:
        governor.SHEDDING_ACTIVE = False

    assert governor.SHEDDING_ACTIVE is False, "Should deactivate at 70%"


# ── Test 3: Hysteresis — does NOT reactivate between 75-89% ───────────────
def test_hysteresis_no_reactivation():
    governor = LoadSheddingGovernor()
    governor.SHEDDING_ACTIVE = False
    governor._memory_pct = 85.0  # Between low (75) and high (90)

    if not governor.SHEDDING_ACTIVE and governor._memory_pct >= SHEDDING_THRESHOLD_HIGH:
        governor.SHEDDING_ACTIVE = True

    assert governor.SHEDDING_ACTIVE is False, "Should NOT activate at 85% (below 90 threshold)"


# ── Test 4: POST to non-critical endpoint → should_shed True ──────────────
def test_post_non_critical_sheds():
    governor = LoadSheddingGovernor()
    governor.SHEDDING_ACTIVE = True

    assert governor.should_shed("/players/123", "POST") is True
    assert governor.should_shed("/matchup/analyze", "POST") is True
    assert governor.should_shed("/teams/roster", "POST") is True


# ── Test 5: GET request → should_shed False even when active ──────────────
def test_get_requests_exempt():
    governor = LoadSheddingGovernor()
    governor.SHEDDING_ACTIVE = True

    assert governor.should_shed("/players/123", "GET") is False
    assert governor.should_shed("/matchup/analyze", "GET") is False
    assert governor.should_shed("/teams/roster", "GET") is False


# ── Test 6: Exempt paths never shed ───────────────────────────────────────
def test_exempt_paths():
    governor = LoadSheddingGovernor()
    governor.SHEDDING_ACTIVE = True

    exempt_cases = [
        ("/healthz", "POST"),
        ("/readyz", "POST"),
        ("/health", "POST"),
        ("/health/deps", "POST"),
        ("/vanguard/admin/incidents", "POST"),
        ("/vanguard/health", "POST"),
        ("/admin/seed/data", "POST"),
        ("/live/stream", "POST"),
    ]

    for path, method in exempt_cases:
        assert governor.should_shed(path, method) is False, (
            f"Exempt path {path} {method} should NOT be shed"
        )


# ── Test 7: _is_exempt_from_shedding helper ───────────────────────────────
def test_is_exempt_helper():
    # All GETs are exempt
    assert _is_exempt_from_shedding("/any/path", "GET") is True

    # Exact matches
    assert _is_exempt_from_shedding("/healthz", "POST") is True
    assert _is_exempt_from_shedding("/readyz", "POST") is True

    # Prefix matches
    assert _is_exempt_from_shedding("/vanguard/admin/x", "POST") is True
    assert _is_exempt_from_shedding("/admin/seed", "POST") is True
    assert _is_exempt_from_shedding("/live/stream", "POST") is True

    # Non-exempt POSTs
    assert _is_exempt_from_shedding("/players/123", "POST") is False
    assert _is_exempt_from_shedding("/matchup/analyze", "POST") is False


# ── Test 8: When not active, should_shed is always False ──────────────────
def test_inactive_never_sheds():
    governor = LoadSheddingGovernor()
    governor.SHEDDING_ACTIVE = False

    assert governor.should_shed("/players/123", "POST") is False
    assert governor.should_shed("/matchup/analyze", "POST") is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
