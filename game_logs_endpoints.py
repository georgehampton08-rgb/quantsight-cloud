"""
Add game logs and boxscore endpoints to public_routes.py
"""

# Add these endpoints to public_routes.py after the matchup endpoint

@router.get("/game-logs")
async def get_game_logs(
    player_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Get game logs from Firestore
    Query params:
        player_id: Filter by player ID
        team_id: Filter by team abbreviation
        limit: Number of logs to return (default: 10, max: 100)
    """
    try:
        from firestore_db import get_firestore_db
        from google.cloud.firestore_v1.base_query import FieldFilter
        
        db = get_firestore_db()
        logs_ref = db.collection('game_logs')
        
        # Build query
        query = logs_ref
        if player_id:
            query = query.where(filter=FieldFilter('player_id', '==', str(player_id)))
        if team_id:
            query = query.where(filter=FieldFilter('team_abbreviation', '==', team_id.upper()))
        
        query = query.limit(limit)
        docs = query.stream()
        
        logs = []
        for doc in docs:
            log_data = doc.to_dict()
            log_data['id'] = doc.id
            logs.append(log_data)
        
        logger.info(f"✅ Returned {len(logs)} game logs")
        return logs
        
    except Exception as e:
        logger.error(f"Error fetching game logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boxscore/{game_id}")
async def get_boxscore(game_id: str):
    """
    Get boxscore for a specific game
    Returns player stats for both teams in the game
    """
    try:
        from firestore_db import get_firestore_db
        from google.cloud.firestore_v1.base_query import FieldFilter
        
        db = get_firestore_db()
        logs_ref = db.collection('game_logs')
        
        # Get all game logs for this game_id
        query = logs_ref.where(filter=FieldFilter('game_id', '==', game_id))
        docs = query.stream()
        
        player_stats = []
        for doc in docs:
            stat = doc.to_dict()
            stat['id'] = doc.id
            player_stats.append(stat)
        
        if not player_stats:
            raise HTTPException(status_code=404, detail=f"No boxscore found for game {game_id}")
        
        # Group by team
        home_team = None
        away_team = None
        home_players = []
        away_players = []
        
        for stat in player_stats:
            team_abbr = stat.get('team_abbreviation')
            if not home_team:
                home_team = team_abbr
                home_players.append(stat)
            elif team_abbr == home_team:
                home_players.append(stat)
            else:
                if not away_team:
                    away_team = team_abbr
                away_players.append(stat)
        
        logger.info(f"✅ Returned boxscore for game {game_id}")
        return {
            "game_id": game_id,
            "home_team": {
                "abbreviation": home_team,
                "players": home_players
            },
            "away_team": {
                "abbreviation": away_team,
                "players": away_players
            },
            "total_players": len(player_stats)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching boxscore for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
