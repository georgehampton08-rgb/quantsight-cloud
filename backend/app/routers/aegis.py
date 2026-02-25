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
    # Phase 6: Wire real Monte Carlo engine
    # ---------------------------------------------------------------
    try:
        from aegis.sim_adapter import FirestoreSimAdapter
        from engines.deep_monte_carlo import DeepMonteCarloEngine

        adapter = FirestoreSimAdapter()
        player_stats = await adapter.get_player_stats(player_id)
        if not player_stats:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "not_found",
                    "code": "PLAYER_DATA_MISSING",
                    "message": f"No statistical data found for player {player_id}. "
                               "Data may not yet be hydrated.",
                    "player_id": player_id,
                }
            )

        opponent_defense = None
        if opponent_id:
            opponent_defense = await adapter.get_opponent_defense(opponent_id)

        engine = DeepMonteCarloEngine(n_games=500, verbose=False)
        projection = engine.run_deep_simulation(
            player_stats=player_stats,
            opponent_defense=opponent_defense,
            schedule_context=None,
        )

        # Build response with probability overrides
        result = {
            "player_id": player_id,
            "opponent_id": opponent_id,
            "game_date": game_date,
            "projection": {
                "floor": projection.floor_20th,
                "expected": projection.expected_value,
                "ceiling": projection.ceiling_80th,
                "variance": projection.variance_metrics,
            },
            "execution_time_ms": round(projection.execution_time_ms, 1),
            "engine": "deep_monte_carlo",
            "n_games": 500,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Optional: compute over/under probabilities for prop lines
        if any([pts_line, reb_line, ast_line]):
            import numpy as np
            probabilities = {}
            if pts_line is not None and "pts" in projection.game_distributions:
                dist = projection.game_distributions["pts"]
                probabilities["pts_over"] = round(float(np.mean(dist > pts_line)), 4)
            if reb_line is not None and "reb" in projection.game_distributions:
                dist = projection.game_distributions["reb"]
                probabilities["reb_over"] = round(float(np.mean(dist > reb_line)), 4)
            if ast_line is not None and "ast" in projection.game_distributions:
                dist = projection.game_distributions["ast"]
                probabilities["ast_over"] = round(float(np.mean(dist > ast_line)), 4)
            result["probabilities"] = probabilities

        return result

    except HTTPException:
        raise
    except ImportError as e:
        logger.error(f"[aegis/simulate] Engine import failed: {e}")
        raise HTTPException(
            status_code=501,
            detail={
                "status": "not_implemented",
                "code": "ENGINE_IMPORT_FAILED",
                "message": f"Monte Carlo engine not available: {e}",
                "player_id": player_id,
            }
        )
    except Exception as e:
        logger.error(f"[aegis/simulate] Simulation error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "code": "SIMULATION_FAILED",
                "message": f"Simulation failed: {str(e)}",
                "player_id": player_id,
            }
        )
