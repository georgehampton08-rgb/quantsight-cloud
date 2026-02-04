"""
Game Logs API Endpoint
Provides game log data for players and teams
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/game-logs")
async def get_game_logs(
    player_id: Optional[str] = Query(None, description="NBA player ID"),
    team_id: Optional[str] = Query(None, description="Team tricode"),
    game_id: Optional[str] = Query(None, description="NBA game ID"),
    date: Optional[date] = Query(None, description="Game date (YYYY-MM-DD)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of logs to return")
):
    """
    Get game logs with filters
    
    At least one filter (player_id, team_id, game_id, or date) must be provided.
    
    Args:
        player_id: Filter by player ID
        team_id: Filter by team tricode
        game_id: Filter by specific game
        date: Filter by game date
        limit: Maximum results (1-100)
    
    Returns:
        Game logs matching filters
    """
    try:
        # Validate at least one filter
        if not any([player_id, team_id, game_id, date]):
            raise HTTPException(
                status_code=400, 
                detail="Must provide at least one filter: player_id, team_id, game_id, or date"
            )
        
        # TODO: Implement actual Firestore query
        # For now, return structured placeholder
        
        logs = []
        
        if player_id:
            # Fetch player game logs from Firestore
            logs.append({
                "player_id": player_id,
                "game_id": "example_game_id",
                "date": date.isoformat() if date else "2026-02-04",
                "stats": {
                    "pts": 0,
                    "reb": 0,
                    "ast": 0,
                    "min": "0:00"
                }
            })
        
        return {
            "filters": {
                "player_id": player_id,
                "team_id": team_id,
                "game_id": game_id,
                "date": date.isoformat() if date else None
            },
            "count": len(logs),
            "limit": limit,
            "logs": logs[:limit],
            "status": "placeholder - implement Firestore query"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Game logs query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
