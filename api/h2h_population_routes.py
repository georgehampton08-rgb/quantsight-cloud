"""
H2H Population Routes
=====================
API endpoints for triggering H2H data population.
Enables on-demand and scheduled data population for matchup analysis.
"""
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import H2H fetcher
try:
    from services.h2h_fetcher import get_h2h_fetcher
    from services.h2h_firestore_adapter import get_h2h_adapter
    HAS_H2H = True
except ImportError:
    HAS_H2H = False
    get_h2h_fetcher = None
    get_h2h_adapter = None

router = APIRouter(prefix="/api/h2h", tags=["H2H Data"])


class PopulateRequest(BaseModel):
    """Request model for H2H population"""
    team_a: str
    team_b: str
    max_players: Optional[int] = 12


class PopulateResponse(BaseModel):
    """Response model for H2H population"""
    status: str
    message: str
    team_a: str
    team_b: str


class H2HStatusResponse(BaseModel):
    """Response for H2H status check"""
    player_id: str
    opponent: str
    has_data: bool
    is_fresh: bool
    games: int
    stats: Optional[dict] = None


def _background_populate(team_a: str, team_b: str, max_players: int):
    """Background task for H2H population"""
    if not HAS_H2H or not get_h2h_fetcher:
        logger.error("H2H fetcher not available")
        return
    
    fetcher = get_h2h_fetcher()
    
    # Fetch H2H for team_a vs team_b
    logger.info(f"Starting H2H population: {team_a} vs {team_b}")
    result_a = fetcher.fetch_roster_h2h(team_a, team_b, max_players)
    logger.info(f"H2H for {team_a} vs {team_b}: {result_a}")
    
    # Fetch H2H for team_b vs team_a
    result_b = fetcher.fetch_roster_h2h(team_b, team_a, max_players)
    logger.info(f"H2H for {team_b} vs {team_a}: {result_b}")


@router.post("/populate", response_model=PopulateResponse)
async def populate_h2h(request: PopulateRequest, background_tasks: BackgroundTasks):
    """
    Trigger H2H data population for two teams.
    
    This endpoint queues background jobs to fetch H2H data from NBA API
    and store it in Firestore for all players on both teams.
    
    Args:
        request: PopulateRequest with team_a, team_b, max_players
        
    Returns:
        PopulateResponse with status and message
    """
    if not HAS_H2H:
        raise HTTPException(status_code=503, detail="H2H service not available")
    
    team_a = request.team_a.upper()
    team_b = request.team_b.upper()
    
    # Queue background task
    background_tasks.add_task(
        _background_populate,
        team_a,
        team_b,
        request.max_players
    )
    
    return PopulateResponse(
        status="queued",
        message=f"H2H population started for {team_a} vs {team_b}. Data will be available in ~30-60 seconds.",
        team_a=team_a,
        team_b=team_b
    )


@router.get("/status/{player_id}/{opponent}", response_model=H2HStatusResponse)
async def get_h2h_status(player_id: str, opponent: str):
    """
    Check H2H data status for a player vs opponent.
    
    Args:
        player_id: NBA player ID
        opponent: Team abbreviation
        
    Returns:
        H2HStatusResponse with data status and stats
    """
    if not HAS_H2H:
        raise HTTPException(status_code=503, detail="H2H service not available")
    
    adapter = get_h2h_adapter() if get_h2h_adapter else None
    
    if not adapter:
        return H2HStatusResponse(
            player_id=player_id,
            opponent=opponent.upper(),
            has_data=False,
            is_fresh=False,
            games=0,
            stats=None
        )
    
    # Get H2H stats
    stats = adapter.get_h2h_stats(player_id, opponent)
    has_data = stats is not None and stats.get('games', 0) > 0
    is_fresh = adapter.check_freshness(player_id, opponent) if has_data else False
    
    return H2HStatusResponse(
        player_id=player_id,
        opponent=opponent.upper(),
        has_data=has_data,
        is_fresh=is_fresh,
        games=stats.get('games', 0) if stats else 0,
        stats=stats
    )


@router.post("/fetch/{player_id}/{opponent}")
async def fetch_single_h2h(player_id: str, opponent: str, background_tasks: BackgroundTasks):
    """
    Fetch H2H data for a single player vs opponent.
    
    Args:
        player_id: NBA player ID
        opponent: Team abbreviation
        
    Returns:
        Status message
    """
    if not HAS_H2H:
        raise HTTPException(status_code=503, detail="H2H service not available")
    
    fetcher = get_h2h_fetcher()
    
    # Queue background fetch
    def _fetch():
        result = fetcher.fetch_h2h(player_id, opponent.upper())
        logger.info(f"Single H2H fetch complete: {result}")
    
    background_tasks.add_task(_fetch)
    
    return {
        "status": "queued",
        "message": f"H2H fetch started for player {player_id} vs {opponent}",
        "player_id": player_id,
        "opponent": opponent.upper()
    }


@router.get("/games/{player_id}/{opponent}")
async def get_h2h_games(player_id: str, opponent: str, limit: int = 10):
    """
    Get individual H2H game records for a player vs opponent.
    
    Args:
        player_id: NBA player ID
        opponent: Team abbreviation
        limit: Max games to return
        
    Returns:
        List of game records
    """
    if not HAS_H2H:
        raise HTTPException(status_code=503, detail="H2H service not available")
    
    adapter = get_h2h_adapter() if get_h2h_adapter else None
    
    if not adapter:
        return {"games": [], "count": 0}
    
    games = adapter.get_h2h_games(player_id, opponent, limit)
    
    return {
        "player_id": player_id,
        "opponent": opponent.upper(),
        "games": games,
        "count": len(games)
    }
