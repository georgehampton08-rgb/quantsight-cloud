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


@router.get("/teams/{team_abbrev}")
async def get_team_by_abbrev(team_abbrev: str):
    """Get individual team information"""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT team_id, full_name, tricode, city, state, year_founded
                FROM teams
                WHERE UPPER(tricode) = UPPER(:abbrev)
            """), {"abbrev": team_abbrev})
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Team {team_abbrev} not found")
        
        engine.dispose()
        
        return {
            "id": int(row[0]),
            "name": row[1],
            "abbreviation": row[2],
            "city": row[3] or "",
            "state": row[4] or "",
            "founded": int(row[5]) if row[5] else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching team {team_abbrev}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedule")
async def get_schedule(date: str = None, team: str = None):
    """
    Get today's NBA schedule from NBA API
    Optional filters: date (YYYY-MM-DD), team (abbreviation)
    Returns live, upcoming, and completed games for today
    """
    try:
        import requests
        from datetime import datetime
        
        # Use date param if provided, otherwise today
        target_date = date if date else datetime.utcnow().strftime("%Y-%m-%d")
        
        # NBA API endpoint for today's scoreboard (NBA API doesn't support historical dates easily for this endpoint)
        # For now, we'll always fetch today's scoreboard and filter by date if needed (though the API itself is "todaysScoreboard")
        url = f"https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.nba.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        games_list = data.get("scoreboard", {}).get("games", [])
        
        # Filter by team if specified
        if team:
            team_upper = team.upper()
            games_list = [
                game for game in games_list
                if game.get("homeTeam", {}).get("teamTricode", "").upper() == team_upper
                or game.get("awayTeam", {}).get("teamTricode", "").upper() == team_upper
            ]
        
        # Transform to our format
        transformed_games = []
        for game in games_list:
            transformed_games.append({
                "game_id": game.get("gameId", ""),
                "game_date": game.get("gameTimeUTC", "")[:10],
                "game_time": game.get("gameTimeUTC", ""),
                "home_team": {
                    "team_id": game.get("homeTeam", {}).get("teamId", 0),
                    "name": game.get("homeTeam", {}).get("teamName", ""),
                    "tricode": game.get("homeTeam", {}).get("teamTricode", ""),
                    "score": game.get("homeTeam", {}).get("score", 0),
                    "wins": game.get("homeTeam", {}).get("wins", 0),
                    "losses": game.get("homeTeam", {}).get("losses", 0),
                },
                "away_team": {
                    "team_id": game.get("awayTeam", {}).get("teamId", 0),
                    "name": game.get("awayTeam", {}).get("teamName", ""),
                    "tricode": game.get("awayTeam", {}).get("teamTricode", ""),
                    "score": game.get("awayTeam", {}).get("score", 0),
                    "wins": game.get("awayTeam", {}).get("wins", 0),
                    "losses": game.get("awayTeam", {}).get("losses", 0),
                },
                "status": game.get("gameStatus", 0),
                "status_text": game.get("gameStatusText", ""),
                "period": game.get("period", 0),
                "game_clock": game.get("gameClock", ""),
                "arena": game.get("arenaName", ""),
                "city": game.get("arenaCity", "")
            })
        
        return {
            "date": target_date,
            "total_games": len(transformed_games),
            "games": transformed_games
        }
    
    except requests.RequestException as e:
        logger.error(f"NBA API error: {e}")
        # Return empty games list if NBA API fails
        return {
            "date": date or datetime.utcnow().strftime("%Y-%m-%d"),
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


@router.get("/players/{player_id}")
async def get_player_by_id(player_id: str):
    """Get individual player profile with stats"""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Get player basic info
            result = conn.execute(text("""
                SELECT player_id, full_name, team_abbreviation, position, height, weight
                FROM players
                WHERE player_id = :pid
            """), {"pid": player_id})
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Player not found")
            
            # Get player stats (current season)
            stats_result = conn.execute(text("""
                SELECT points_avg, rebounds_avg, assists_avg, 
                       fg_pct, three_pct, ft_pct, games_played
                FROM player_rolling_averages
                WHERE player_id = :pid
                ORDER BY last_updated DESC
                LIMIT 1
            """), {"pid": player_id})
            
            stats_row = stats_result.fetchone()
            
        engine.dispose()
        
        return {
            "id": str(row[0]),
            "name": row[1],
            "team": row[2] or "N/A",
            "position": row[3] or "G",
            "height": row[4] or "N/A",
            "weight": row[5] or "N/A",
            "stats": {
                "ppg": float(stats_row[0]) if stats_row and stats_row[0] else 0.0,
                "rpg": float(stats_row[1]) if stats_row and stats_row[1] else 0.0,
                "apg": float(stats_row[2]) if stats_row and stats_row[2] else 0.0,
                "fg_pct": float(stats_row[3]) if stats_row and stats_row[3] else 0.0,
                "three_pct": float(stats_row[4]) if stats_row and stats_row[4] else 0.0,
                "ft_pct": float(stats_row[5]) if stats_row and stats_row[5] else 0.0,
                "games": int(stats_row[6]) if stats_row and stats_row[6] else 0
            } if stats_row else {"ppg": 0.0, "rpg": 0.0, "apg": 0.0}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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




@router.get("/matchup/analyze")
async def analyze_matchup(home_team: str = None, away_team: str = None):
    """
    Basic team matchup analysis (cloud-optimized version without Vertex Engine)
    Analyzes team stats and provides win probability
    """
    if not home_team or not away_team:
        raise HTTPException(status_code=400, detail="home_team and away_team parameters required")
    
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Fetch team stats for both teams
            home_stats = conn.execute(text("""
                SELECT t.full_name, t.tricode, COUNT(DISTINCT p.player_id) as roster_size
                FROM teams t
                LEFT JOIN players p ON t.tricode = p.team_abbreviation
                WHERE UPPER(t.tricode) = UPPER(:team)
                GROUP BY t.full_name, t.tricode
            """), {"team": home_team}).fetchone()
            
            away_stats = conn.execute(text("""
                SELECT t.full_name, t.tricode, COUNT(DISTINCT p.player_id) as roster_size  
                FROM teams t
                LEFT JOIN players p ON t.tricode = p.team_abbreviation
                WHERE UPPER(t.tricode) = UPPER(:team)
                GROUP BY t.full_name, t.tricode
            """), {"team": away_team}).fetchone()
            
            if not home_stats or not away_stats:
                raise HTTPException(status_code=404, detail="One or both teams not found")
        
        engine.dispose()
        
        # Simple win probability (50-50 baseline for cloud version)
        # In desktop version with Vertex Engine, this uses advanced ML models
        return {
            "matchup": {
                "home_team": {
                    "name": home_stats[0],
                    "abbreviation": home_stats[1],
                    "roster_size": int(home_stats[2])
                },
                "away_team": {
                    "name": away_stats[0],
                    "abbreviation": away_stats[1],
                    "roster_size": int(away_stats[2])
                }
            },
            "prediction": {
                "home_win_probability": 0.52,  # Slight home advantage
                "away_win_probability": 0.48,
                "confidence": "low",
                "note": "Basic analysis - Desktop version has advanced ML predictions via Vertex Engine"
            },
            "key_factors": [
                "Home court advantage typically +3-4% win rate",
                "Team rosters loaded successfully",
                "For advanced predictions, use desktop version with Vertex Engine"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing matchup {home_team} vs {away_team}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/matchup-lab/crucible-sim")
async def crucible_simulation(data: dict = None):
    """Run Crucible simulation for matchup scenarios (placeholder)"""
    # TODO: Implement or redirect to /aegis/crucible/simulate endpoint
    return {
        "status": "not_implemented",
        "message": "Crucible simulation coming soon - use /aegis/simulate/{player_id} for basic projections"
    }
