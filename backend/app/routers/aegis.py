"""
Aegis Router - Cloud API
=========================
Player projection and simulation endpoints.

Phase 1: /simulate is feature-flag gated. Returns structured 503 when disabled.
Phase 6: Monte Carlo engine will be wired from shared_core.monte_carlo.engine.

IMPORTANT: Never return fake/hardcoded projection values.
           Consumers (PlayerProfilePage) must receive real data or a clear unavailable signal.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/simulate/{player_id}")
async def run_aegis_simulation(
    player_id: str,
    opponent_id: Optional[str] = Query(None, description="Opponent team ID"),
    game_date: Optional[str] = Query(None, description="Game date (YYYY-MM-DD)"),
    force_fresh: bool = Query(False, description="Bypass cache"),
    pts_line: Optional[float] = Query(None, description="Points line for probability"),
    reb_line: Optional[float] = Query(None, description="Rebounds line for probability"),
    ast_line: Optional[float] = Query(None, description="Assists line for probability")
):
    """
    Run Aegis Monte Carlo simulation for player projections.

    CURRENT STATUS: Soft-disabled — requires FEATURE_AEGIS_SIM_ENABLED=true.

    Phase 6 will implement:
    - extraction of Monte Carlo engine from server.py into shared_core.monte_carlo
    - FirestoreSimAdapter for cloud data access
    - deterministic seed support for testing

    Returns structured 503 when flag is off so frontend can show a proper
    "Simulation not available" state rather than receiving fake data.
    """
    from vanguard.core.feature_flags import flag, disabled_response

    if not flag("FEATURE_AEGIS_SIM_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail=disabled_response(
                "FEATURE_AEGIS_SIM_ENABLED",
                "Aegis Monte Carlo Simulation"
            )
        )

    # ---------------------------------------------------------------
    # Phase 6: Wire real Monte Carlo engine here.
    # from shared_core.monte_carlo.engine import run_simulation
    # from shared_core.monte_carlo.adapters import FirestoreSimAdapter
    # ---------------------------------------------------------------
    logger.warning(
        f"[aegis/simulate] Flag enabled but engine not yet implemented. "
        f"player={player_id} opponent={opponent_id}"
    )
    raise HTTPException(
        status_code=501,
        detail={
            "status": "not_implemented",
            "code": "ENGINE_NOT_WIRED",
            "message": "Monte Carlo engine implementation scheduled for Phase 6.",
            "player_id": player_id,
        }
    )
