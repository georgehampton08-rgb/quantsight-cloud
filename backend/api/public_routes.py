"""
Public API Routes for Cloud Backend
Provides endpoints for frontend consumption
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text, create_engine
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_database_url() -> str:
    """Get database URL from environment."""
    db_url = os.getenv('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    return db_url


@router.get("/debug/teams-schema")
async def debug_teams_schema():
    """Debug endpoint to check teams table structure"""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Get column names
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'teams'
                ORDER BY ordinal_position
            """))
            
            columns = [{"name": row[0], "type": row[1]} for row in result]
            
            # Get sample row
            sample = conn.execute(text("SELECT * FROM teams LIMIT 1"))
            sample_row = dict(zip([col.name for col in sample.keys()], list(sample.fetchone() or [])))
        
        engine.dispose()
        return {
            "columns": columns,
            "sample_data": sample_row
        }
        
    except Exception as e:
        logger.error(f"Error debugging schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/teams")
async def get_teams():
    """Get all NBA teams"""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Use * to get all columns dynamically
            result = conn.execute(text("""
                SELECT *
                FROM teams
                ORDER BY full_name
            """))
            
            teams = []
            for row in result:
                row_dict = dict(row._mapping)
                teams.append({
                    "id": str(row_dict.get('team_id', '')),
                    "abbreviation": row_dict.get('abbreviation', ''),
                    "city": row_dict.get('city', ''),
                    "name": row_dict.get('nickname', ''),  # Try nickname first
                    "full_name": row_dict.get('full_name', ''),
                    "conference": row_dict.get('conference', ''),
                    "division": row_dict.get('division', '')
                })
        
        engine.dispose()
        return teams
        
    except Exception as e:
        logger.error(f"Error fetching teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players")
async def get_all_players():
    """Get all players for OmniSearch"""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_id, full_name, position, team_abbreviation
                FROM players
                ORDER BY full_name
            """))
            
            players = []
            for row in result:
                players.append({
                    "id": str(row[0]),
                    "name": row[1],
                    "position": row[2] or "G",
                    "team": row[3] or "FA"
                })
        
        engine.dispose()
        return players
        
    except Exception as e:
        logger.error(f"Error fetching players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roster/{team_id}")

async def get_roster(team_id: str):
    """Get team roster from players table"""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_id, full_name, position, team_abbreviation
                FROM players
                WHERE team_abbreviation = (SELECT abbreviation FROM teams WHERE team_id = :team_id)
                ORDER BY full_name
            """), {"team_id": int(team_id)})
            
            players = [
                {
                    "id": str(row[0]),
                    "name": row[1],  # full_name column
                    "position": row[2] or "G",
                    "team": row[3]
                }
                for row in result
            ]
        
        engine.dispose()
        return players
        
    except Exception as e:
        logger.error(f"Error fetching roster: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule")
async def get_schedule():
    """
    Get today's NBA schedule from NBA API
    Returns live, upcoming, and completed games for today
    """
    try:
        import requests
        from datetime import datetime
        
        # NBA API endpoint for today's scoreboard
        url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.nba.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        games_data = data.get('scoreboard', {}).get('games', [])
        
        games = []
        for game in games_data:
            games.append({
                'game_id': game.get('gameId'),
                'game_date': game.get('gameTimeUTC', '')[:10],
                'game_time': game.get('gameTimeUTC'),
                'home_team': {
                    'team_id': game.get('homeTeam', {}).get('teamId'),
                    'name': game.get('homeTeam', {}).get('teamName'),
                    'tricode': game.get('homeTeam', {}).get('teamTricode'),
                    'score': game.get('homeTeam', {}).get('score', 0),
                    'wins': game.get('homeTeam', {}).get('wins', 0),
                    'losses': game.get('homeTeam', {}).get('losses', 0)
                },
                'away_team': {
                    'team_id': game.get('awayTeam', {}).get('teamId'),
                    'name': game.get('awayTeam', {}).get('teamName'),
                    'tricode': game.get('awayTeam', {}).get('teamTricode'),
                    'score': game.get('awayTeam', {}).get('score', 0),
                    'wins': game.get('awayTeam', {}).get('wins', 0),
                    'losses': game.get('awayTeam', {}).get('losses', 0)
                },
                'status': game.get('gameStatus'),  # 1=scheduled, 2=live, 3=final
                'status_text': game.get('gameStatusText', ''),
                'period': game.get('period', 0),
                'game_clock': game.get('gameClock', ''),
                'arena': game.get('arenaName', ''),
                'city': game.get('arenaCity', '')
            })
        
        return {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_games": len(games),
            "games": games
        }
        
    except requests.RequestException as e:
        logger.error(f"NBA API error: {e}")
        # Return empty games list if NBA API fails
        return {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_games": 0,
            "games": [],
            "error": "Unable to fetch schedule from NBA API"
        }
    except Exception as e:
        logger.error(f"Schedule endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/injuries")
async def get_injuries():
    """
    Get current injuries
    NOTE: This is a placeholder since we don't have injuries table yet
    """
    return {
        "message": "Injuries endpoint under construction",
        "injuries": []
    }


@router.get("/players/search")
async def search_players(q: str = ""):
    """Search players by name"""
    # If no query or too short, return empty
    if not q or len(q) < 2:
        return []
    
    db_url = get_database_url()
    if not db_url:
        return []
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_id, full_name, team_abbreviation, position
                FROM players
                WHERE LOWER(full_name) LIKE LOWER(:query)
                ORDER BY full_name
                LIMIT 20
            """), {"query": f"%{q}%"})
            
            players = [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "team": row[2],
                    "position": row[3] or "G"
                }
                for row in result
            ]
        
        engine.dispose()
        return players
        
    except Exception as e:
        logger.error(f"Error searching players: {e}")
        return []  # Return empty array on error instead of 500
