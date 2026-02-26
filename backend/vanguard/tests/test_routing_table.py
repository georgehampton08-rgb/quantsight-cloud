"""
Tests for Phase 5 Step 5.2 — Routing Table + Heuristic Triage
==============================================================
Verifies:
  - RoutingTable activation/deactivation with hysteresis
  - Blast radius protection
  - Heuristic triage pattern matching
  - Snapshot hysteresis counter logic
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone


# ── A) Routing Table Unit Tests ──────────────────────────────────────────────

@pytest.fixture
def fresh_routing_table():
    """Create a fresh RoutingTable (not the singleton)."""
    from vanguard.surgeon.routing_table import RoutingTable
    return RoutingTable()


@pytest.mark.asyncio
async def test_routing_table_default_routes(fresh_routing_table):
    """RoutingTable initializes with the gemini_triage_path default entry."""
    rt = fresh_routing_table
    route = rt.get_route("gemini_triage_path")
    assert route is not None
    assert route.primary_handler == "vanguard.ai.ai_analyzer.VanguardAIAnalyzer.analyze_incident"
    assert route.fallback_handler == "vanguard.ai.heuristic_triage.generate_heuristic_triage"
    assert route.fallback_active is False


@pytest.mark.asyncio
async def test_routing_table_activate_deactivate(fresh_routing_table):
    """Activating and deactivating a fallback follows correct lifecycle."""
    rt = fresh_routing_table

    # Activate
    result = await rt.activate_fallback("gemini_triage_path", "test reason")
    assert result is True
    assert rt.is_fallback_active("gemini_triage_path") is True

    # Get active fallbacks
    active = rt.get_active_fallbacks()
    assert len(active) == 1
    assert active[0]["route_key"] == "gemini_triage_path"
    assert active[0]["reason"] == "test reason"

    # Deactivate
    recovery_time = await rt.deactivate_fallback("gemini_triage_path")
    assert recovery_time is not None
    assert recovery_time >= 0.0
    assert rt.is_fallback_active("gemini_triage_path") is False
    assert len(rt.get_active_fallbacks()) == 0


@pytest.mark.asyncio
async def test_routing_table_activate_idempotent(fresh_routing_table):
    """Activating an already-active fallback is idempotent (returns True)."""
    rt = fresh_routing_table
    await rt.activate_fallback("gemini_triage_path", "first")
    result = await rt.activate_fallback("gemini_triage_path", "second")
    assert result is True  # idempotent


@pytest.mark.asyncio
async def test_routing_table_deactivate_when_not_active(fresh_routing_table):
    """Deactivating an inactive fallback returns None."""
    rt = fresh_routing_table
    result = await rt.deactivate_fallback("gemini_triage_path")
    assert result is None


@pytest.mark.asyncio
async def test_routing_table_blast_radius_protection(fresh_routing_table):
    """Blast-radius routes cannot be registered or activated."""
    rt = fresh_routing_table

    # Cannot register
    result = rt.register_route("/healthz", "some.handler")
    assert result is False

    result = rt.register_route("/vanguard/admin/incidents", "some.handler")
    assert result is False

    # Cannot activate (even if manually constructed)
    result = await rt.activate_fallback("/healthz", "test")
    assert result is False


@pytest.mark.asyncio
async def test_routing_table_no_fallback_handler(fresh_routing_table):
    """Cannot activate fallback on a route with no fallback_handler."""
    rt = fresh_routing_table
    rt.register_route("test_route", "primary.handler")
    result = await rt.activate_fallback("test_route", "test")
    assert result is False


@pytest.mark.asyncio
async def test_routing_table_unknown_route(fresh_routing_table):
    """Activating an unknown route returns False."""
    rt = fresh_routing_table
    result = await rt.activate_fallback("nonexistent_route", "test")
    assert result is False


def test_routing_table_get_all_routes(fresh_routing_table):
    """get_all_routes returns a diagnostic snapshot."""
    rt = fresh_routing_table
    snapshot = rt.get_all_routes()
    assert "gemini_triage_path" in snapshot
    assert snapshot["gemini_triage_path"]["fallback_active"] is False


def test_routing_table_register_custom_route(fresh_routing_table):
    """Can register a non-blast-radius route with fallback."""
    rt = fresh_routing_table
    result = rt.register_route("custom_route", "primary.func", "fallback.func")
    assert result is True
    route = rt.get_route("custom_route")
    assert route is not None
    assert route.primary_handler == "primary.func"
    assert route.fallback_handler == "fallback.func"


# ── B) Heuristic Triage Tests ────────────────────────────────────────────────

def _make_incident(error_type="KeyError", error_message="", endpoint="/api/test", severity="RED"):
    return {
        "fingerprint": "test-fp-123",
        "error_type": error_type,
        "error_message": error_message,
        "endpoint": endpoint,
        "severity": severity,
        "occurrence_count": 1,
    }


def test_heuristic_triage_key_error():
    """Heuristic triage matches KeyError pattern."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(error_type="KeyError", error_message="'player_id'")
    analysis = generate_heuristic_triage(incident)
    assert analysis.fingerprint == "test-fp-123"
    assert analysis.confidence == 55
    assert analysis.prompt_version == "heuristic-1.0"
    assert analysis.model_id == "heuristic-engine"


def test_heuristic_triage_firestore_index():
    """Heuristic triage matches Firestore missing index pattern."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(
        error_type="FailedPrecondition",
        error_message="missing composite index",
    )
    analysis = generate_heuristic_triage(incident)
    assert analysis.confidence == 75
    assert "index" in analysis.root_cause.lower()


def test_heuristic_triage_timeout():
    """Heuristic triage matches timeout patterns."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(
        error_type="DeadlineExceeded",
        error_message="Timed out waiting for Firestore",
    )
    analysis = generate_heuristic_triage(incident)
    assert analysis.confidence == 65
    assert "timeout" in analysis.root_cause.lower() or "timed out" in analysis.root_cause.lower()


def test_heuristic_triage_import_error():
    """Heuristic triage matches ImportError with high confidence."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(
        error_type="ImportError",
        error_message="No module named 'nba_api'",
    )
    analysis = generate_heuristic_triage(incident)
    assert analysis.confidence == 80
    assert "import" in analysis.root_cause.lower() or "module" in analysis.root_cause.lower()


def test_heuristic_triage_unknown_pattern():
    """Unknown error types get the fallback rule with confidence 30."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(
        error_type="SomeBizarreException",
        error_message="Very unusual error",
    )
    analysis = generate_heuristic_triage(incident)
    assert analysis.confidence == 30
    assert "no heuristic pattern matched" in analysis.root_cause.lower()


def test_heuristic_triage_impact_estimation():
    """Impact estimation scales with severity and occurrence count."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage

    # RED + high count
    incident_red = _make_incident(severity="RED")
    incident_red["occurrence_count"] = 15
    analysis_red = generate_heuristic_triage(incident_red)
    assert "high" in analysis_red.impact.lower()

    # YELLOW
    incident_yellow = _make_incident(severity="YELLOW")
    analysis_yellow = generate_heuristic_triage(incident_yellow)
    assert "low" in analysis_yellow.impact.lower()


def test_heuristic_triage_nba_api():
    """Heuristic triage matches NBA API failure pattern."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(
        error_type="ConnectionError",
        error_message="Connection to stats.nba.com timeout",
    )
    analysis = generate_heuristic_triage(incident)
    assert analysis.confidence >= 60


def test_heuristic_triage_permission_denied():
    """Heuristic triage matches permission/auth errors."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(
        error_type="PermissionDenied",
        error_message="The caller does not have permission",
    )
    analysis = generate_heuristic_triage(incident)
    assert analysis.confidence == 70
    assert "permission" in analysis.root_cause.lower() or "auth" in analysis.root_cause.lower()


def test_heuristic_triage_memory_error():
    """Heuristic triage matches memory pressure incidents."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    incident = _make_incident(
        error_type="MemoryError",
        error_message="Out of memory",
    )
    analysis = generate_heuristic_triage(incident)
    assert analysis.confidence == 70
    assert "memory" in analysis.root_cause.lower()


def test_heuristic_triage_returns_incident_analysis():
    """Heuristic triage returns a proper IncidentAnalysis Pydantic model."""
    from vanguard.ai.heuristic_triage import generate_heuristic_triage
    from vanguard.ai.ai_analyzer import IncidentAnalysis
    incident = _make_incident()
    analysis = generate_heuristic_triage(incident)
    assert isinstance(analysis, IncidentAnalysis)
    assert analysis.ready_to_resolve is False
    assert analysis.cached is False


# ── C) Snapshot Hysteresis Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_snapshot_gemini_hysteresis_activation():
    """3 consecutive gemini_ok=False checks should activate heuristic fallback."""
    import vanguard.snapshot as snap
    from vanguard.surgeon.routing_table import RoutingTable

    # Reset counters
    snap._gemini_consecutive_failures = 0
    snap._gemini_consecutive_successes = 0

    test_rt = RoutingTable()

    with patch("vanguard.surgeon.routing_table.get_routing_table", return_value=test_rt), \
         patch("vanguard.core.config.get_vanguard_config") as mock_config, \
         patch.object(snap, "_post_routing_incident", new_callable=AsyncMock):

        from vanguard.core.config import VanguardMode
        mock_cfg = MagicMock()
        mock_cfg.mode = VanguardMode.FULL_SOVEREIGN
        mock_config.return_value = mock_cfg

        # 1st failure — no activation
        await snap._evaluate_gemini_routing(False)
        assert snap._gemini_consecutive_failures == 1
        assert not test_rt.is_fallback_active("gemini_triage_path")

        # 2nd failure — no activation
        await snap._evaluate_gemini_routing(False)
        assert snap._gemini_consecutive_failures == 2
        assert not test_rt.is_fallback_active("gemini_triage_path")

        # 3rd failure — ACTIVATION
        await snap._evaluate_gemini_routing(False)
        assert snap._gemini_consecutive_failures == 3
        assert test_rt.is_fallback_active("gemini_triage_path")


@pytest.mark.asyncio
async def test_snapshot_gemini_hysteresis_deactivation():
    """2 consecutive gemini_ok=True checks should deactivate heuristic fallback."""
    import vanguard.snapshot as snap
    from vanguard.surgeon.routing_table import RoutingTable

    snap._gemini_consecutive_failures = 0
    snap._gemini_consecutive_successes = 0

    test_rt = RoutingTable()
    await test_rt.activate_fallback("gemini_triage_path", "test")
    assert test_rt.is_fallback_active("gemini_triage_path")

    with patch("vanguard.surgeon.routing_table.get_routing_table", return_value=test_rt), \
         patch("vanguard.core.config.get_vanguard_config") as mock_config, \
         patch.object(snap, "_post_routing_incident", new_callable=AsyncMock):

        from vanguard.core.config import VanguardMode
        mock_cfg = MagicMock()
        mock_cfg.mode = VanguardMode.FULL_SOVEREIGN
        mock_config.return_value = mock_cfg

        # 1st success — no deactivation
        await snap._evaluate_gemini_routing(True)
        assert snap._gemini_consecutive_successes == 1
        assert test_rt.is_fallback_active("gemini_triage_path")

        # 2nd success — DEACTIVATION
        await snap._evaluate_gemini_routing(True)
        assert snap._gemini_consecutive_successes == 2
        assert not test_rt.is_fallback_active("gemini_triage_path")


@pytest.mark.asyncio
async def test_snapshot_gemini_routing_circuit_breaker_mode_skips():
    """In CIRCUIT_BREAKER mode, routing table evaluation is skipped."""
    import vanguard.snapshot as snap

    snap._gemini_consecutive_failures = 0
    snap._gemini_consecutive_successes = 0

    with patch("vanguard.core.config.get_vanguard_config") as mock_config:
        from vanguard.core.config import VanguardMode
        mock_cfg = MagicMock()
        mock_cfg.mode = VanguardMode.CIRCUIT_BREAKER
        mock_config.return_value = mock_cfg

        for _ in range(5):
            await snap._evaluate_gemini_routing(False)

        # Function returns early in CIRCUIT_BREAKER mode — counters unchanged
        assert snap._gemini_consecutive_failures == 0


@pytest.mark.asyncio
async def test_snapshot_gemini_failure_resets_success_counter():
    """A failure after successes resets the success counter."""
    import vanguard.snapshot as snap

    snap._gemini_consecutive_failures = 0
    snap._gemini_consecutive_successes = 3

    with patch("vanguard.core.config.get_vanguard_config") as mock_config:
        from vanguard.core.config import VanguardMode
        mock_cfg = MagicMock()
        mock_cfg.mode = VanguardMode.FULL_SOVEREIGN
        mock_config.return_value = mock_cfg

        await snap._evaluate_gemini_routing(False)
        assert snap._gemini_consecutive_failures == 1
        assert snap._gemini_consecutive_successes == 0
