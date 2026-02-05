"""
Game Logs API Endpoint
Provides game log data for players and teams
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date
import logging
from services.firebase_admin_service import get_firebase_service

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
        
        # Get Firebase service
        firebase = get_firebase_service()
        if not firebase:
            raise HTTPException(
                status_code=503,
                detail="Firebase service not available"
            )
        
        # Convert date to string format if provided
        date_str = date.isoformat() if date else None
        
        # Query Firestore (now synchronous)
        game_logs = firebase.query_game_logs(
            game_id=game_id,
            date=date_str,
            player_id=player_id,
            team_id=team_id,
            limit=limit
        )
        
        # Transform to flat player logs for easier consumption
        player_logs = []
        
        for game_log in game_logs:
            game_id_val = game_log.get('game_id')
            game_date = game_log.get('date')
            home_team = game_log.get('home_team')
            away_team = game_log.get('away_team')
            home_score = game_log.get('home_score')
            away_score = game_log.get('away_score')
            
            teams = game_log.get('teams', {})
            
            # Extract players from both teams
            for team_code, team_data in teams.items():
                players_dict = team_data.get('players', {})
                
                for pid, player_data in players_dict.items():
                    # Apply player_id filter if specified
                    if player_id and pid != player_id:
                        continue
                    
                    # Build flat player log entry
                    player_log = {
                        'player_id': pid,
                        'name': player_data.get('name'),
                        'team': team_code,
                        'game_id': game_id_val,
                        'game_date': game_date,
                        'matchup': f"{away_team} @ {home_team}",
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_score': home_score,
                        'away_score': away_score,
                        'position': player_data.get('position'),
                        'starter': player_data.get('starter'),
                        'stats': player_data.get('stats', {})
                    }
                    
                    player_logs.append(player_log)
        
        return {
            "filters_applied": {
                "player_id": player_id,
                "team_id": team_id,
                "game_id": game_id,
                "date": date_str
            },
            "count": len(player_logs),
            "limit": limit,
            "logs": player_logs[:limit]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Game logs query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

