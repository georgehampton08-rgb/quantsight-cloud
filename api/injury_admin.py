"""
Injury Admin API
=================
REST endpoints for managing injuries via admin panel.
Protected by require_admin_role (Phase 3).
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from typing import List, Optional
import logging

from services.automated_injury_worker import get_injury_worker
from api.validators import safe_id, safe_injury_status, safe_text, safe_team_abbr
from api.auth_middleware import require_admin_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/injuries", tags=["admin"])


class InjuryInput(BaseModel):
    """Input model for adding an injury — validated and sanitized."""
    player_id: str
    player_name: str
    team: str
    status: str  # OUT, QUESTIONABLE, PROBABLE, GTD
    injury_desc: str

    @field_validator('player_id')
    @classmethod
    def validate_player_id(cls, v: str) -> str:
        return safe_id(v, 'player_id')

    @field_validator('team')
    @classmethod
    def validate_team(cls, v: str) -> str:
        return safe_team_abbr(v)

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        return safe_injury_status(v)

    @field_validator('injury_desc')
    @classmethod
    def validate_desc(cls, v: str) -> str:
        return safe_text(v, 'injury_desc', 500)

    @field_validator('player_name')
    @classmethod
    def validate_player_name(cls, v: str) -> str:
        return safe_text(v, 'player_name', 100)


class BulkInjuryInput(BaseModel):
    """Bulk injury input — max 50 entries per request."""
    injuries: List[InjuryInput]

    @field_validator('injuries')
    @classmethod
    def validate_count(cls, v: list) -> list:
        if len(v) > 50:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Max 50 injuries per bulk request")
        return v


@router.post("/add")
async def add_injury(injury: InjuryInput, admin: dict = Depends(require_admin_role)):
    """
    Add or update a player injury.

    Example:
    ```
    POST /admin/injuries/add
    {
        "player_id": "1628983",
        "player_name": "Austin Reaves",
        "team": "LAL",
        "status": "OUT",
        "injury_desc": "Left calf strain"
    }
    ```
    """
    try:
        worker = get_injury_worker()
        worker.mark_injured(
            player_id=injury.player_id,
            player_name=injury.player_name,
            team=injury.team,
            status=injury.status,
            injury_desc=injury.injury_desc
        )

        logger.info(f"Added injury: {injury.player_name} ({injury.team}) - {injury.status}")

        return {
            "success": True,
            "message": f"Injury added for {injury.player_name}",
            "injury": injury.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add injury: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk")
async def bulk_add_injuries(data: BulkInjuryInput, admin: dict = Depends(require_admin_role)):
    """
    Add multiple injuries at once. Max 50 per request.

    Example:
    ```
    POST /admin/injuries/bulk
    {
        "injuries": [
            {
                "player_id": "1628983",
                "player_name": "Austin Reaves",
                "team": "LAL",
                "status": "OUT",
                "injury_desc": "Left calf strain"
            },
            ...
        ]
    }
    ```
    """
    try:
        worker = get_injury_worker()
        added = 0

        for injury in data.injuries:
            worker.mark_injured(
                player_id=injury.player_id,
                player_name=injury.player_name,
                team=injury.team,
                status=injury.status,
                injury_desc=injury.injury_desc
            )
            added += 1

        logger.info(f"Bulk added {added} injuries")

        return {
            "success": True,
            "message": f"Added {added} injuries",
            "count": added
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk add failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/remove/{player_id}")
async def remove_injury(player_id: str, admin: dict = Depends(require_admin_role)):
    """
    Remove an injury (mark player as healthy).

    Example: DELETE /admin/injuries/remove/1628983
    """
    # Validate player_id path param
    safe_id(player_id, 'player_id')
    try:
        worker = get_injury_worker()
        worker.mark_healthy(player_id)

        logger.info(f"Removed injury for player {player_id}")

        return {
            "success": True,
            "message": f"Injury removed for player {player_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove injury: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_injuries(admin: dict = Depends(require_admin_role)):
    """
    Get all current injuries across NBA.

    Example: GET /admin/injuries/all
    """
    try:
        worker = get_injury_worker()

        # Get injuries for all teams
        all_teams = ['ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN',
                     'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA',
                     'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX',
                     'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']

        all_injuries = []
        for team in all_teams:
            team_injuries = worker.get_team_injuries(team)
            all_injuries.extend(team_injuries)

        return {
            "success": True,
            "total": len(all_injuries),
            "injuries": all_injuries
        }
    except Exception as e:
        logger.error(f"Failed to fetch injuries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/team/{team_abbr}")
async def get_team_injuries(team_abbr: str, admin: dict = Depends(require_admin_role)):
    """
    Get injuries for a specific team.

    Example: GET /admin/injuries/team/LAL
    """
    # Validate team abbreviation
    safe_team_abbr(team_abbr)
    try:
        worker = get_injury_worker()
        injuries = worker.get_team_injuries(team_abbr.upper())

        return {
            "success": True,
            "team": team_abbr.upper(),
            "total": len(injuries),
            "injuries": injuries
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch team injuries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
