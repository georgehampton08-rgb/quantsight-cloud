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
    """Search players by name - returns ALL if q is empty"""
    db_url = get_database_url()
    if not db_url:
        return []
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # If query empty, return ALL active players
            # Otherwise search by name
            if not q or len(q.strip()) == 0:
                result = conn.execute(text("""
                    SELECT player_id, full_name, team_abbreviation, position
                    FROM players
                    ORDER BY full_name
                    LIMIT 500
                """))
            else:
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


# === NEW ENDPOINTS FOR PWA COMPATIBILITY ===

@router.post("/settings/keys")
async def save_gemini_key(data: dict):
    """Save Gemini API key to Cloud Secret Manager (placeholder)"""
    api_key = data.get("gemini_api_key", "")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="gemini_api_key required")
    
    # TODO: In production, save to Google Secret Manager
    # For now, return success (key would need to be set via gcloud or .env.yaml)
    logger.info(f"Gemini API key save requested (length: {len(api_key)})")
    
    return {
        "status": "success",
        "message": "Gemini API key configuration received. For Cloud Run, please set GEMINI_API_KEY via: gcloud run services update quantsight-cloud --set-env-vars GEMINI_API_KEY=your_key --region us-central1"
    }


@router.get("/matchup-lab/games")
async def get_matchup_lab_games():
    """Get today's games for Matchup Lab - reuses schedule endpoint"""
    return await get_schedule()


@router.get("/usage-vacuum/analyze")
async def analyze_usage_vacuum(player_ids: str = ""):
    """Analyze usage vacuum for players when teammates are out (placeholder)"""
    # TODO: Implement usage vacuum analysis
    # Would analyze player usage rate changes when key teammates are injured
    return {
        "status": "not_implemented",
        "message": "Usage Vacuum analysis feature coming soon",
        "player_ids": player_ids.split(",") if player_ids else []
    }


@router.post("/matchup-lab/crucible-sim")
async def crucible_simulation(data: dict = None):
    """Run Crucible simulation for matchup scenarios (placeholder)"""
    # TODO: Implement or redirect to /aegis/crucible/simulate endpoint
    return {
        "status": "not_implemented",
        "message": "Crucible simulation coming soon - use /aegis/simulate/{player_id} for basic projections"
    }
