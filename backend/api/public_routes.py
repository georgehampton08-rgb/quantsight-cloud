"""
Public API Routes for Cloud Backend
Provides endpoints for frontend consumption
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared database engine - create once
_engine = None
_SessionLocal = None

def get_db_engine():
    """Get or create database engine"""
    global _engine, _SessionLocal
    
    if _engine is None:
        db_url = os.getenv('DATABASE_URL', '')
        if not db_url:
            raise Exception("DATABASE_URL not set")
        
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        
        # Use NullPool for Cloud Run (connection lifecycle per request)
        _engine = create_engine(
            db_url,
            poolclass=NullPool,
            connect_args={"connect_timeout": 10}
        )
        _SessionLocal = sessionmaker(bind=_engine)
        logger.info("✅ Database engine initialized")
    
    return _engine

def get_db_session():
    """Get database session"""
    try:
        get_db_engine()  # Ensure engine exists
        return _SessionLocal()
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        return None


@router.get("/teams")
async def get_teams():
    """Get all NBA teams"""
    session = get_db_session()
    if not session:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = session.execute(text("""
            SELECT team_id, abbreviation, city, name, full_name, conference, division
            FROM teams
            ORDER BY full_name
        """))
        
        teams = [
            {
                "id": str(row[0]),
                "abbreviation": row[1],
                "city": row[2],
                "name": row[3],
                "full_name": row[4],
                "conference": row[5],
                "division": row[6]
            }
            for row in result
        ]
        
        return teams
    except Exception as e:
        logger.error(f"Error fetching teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/roster/{team_id}")
async def get_roster(team_id: str):
    """Get team roster from players table"""
    session = get_db_session()
    if not session:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = session.execute(text("""
            SELECT player_id, name, position, team_abbreviation
            FROM players
            WHERE team_abbreviation = (SELECT abbreviation FROM teams WHERE team_id = :team_id)
            ORDER BY name
        """), {"team_id": int(team_id)})
        
        players = [
            {
                "id": str(row[0]),
                "name": row[1],
                "position": row[2] or "G",
                "team": row[3]
            }
            for row in result
        ]
        
        return players
    except Exception as e:
        logger.error(f"Error fetching roster: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/schedule")
async def get_schedule():
    """
    Get today's schedule
    NOTE: This is a placeholder since we don't have game schedule in Cloud SQL yet
    """
    # TODO: Add game_schedule table and implement properly
    return {
        "message": "Schedule endpoint under construction",
        "games": []
    }


@router.get("/injuries")
async def get_injuries():
    """
    Get current injuries
    NOTE: This is a placeholder since we don't have injuries table yet
    """
    # TODO: Add injuries table and implement properly
    return {
        "message": "Injuries endpoint under construction",
        "injuries": []
    }


@router.get("/players/search")
async def search_players(q: str = ""):
    """Search players by name"""
    session = get_db_session()
    if not session:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # If no query, return empty
        if not q or len(q) < 2:
            return []
        
        result = session.execute(text("""
            SELECT player_id, name, team_abbreviation, position
            FROM players
            WHERE LOWER(name) LIKE LOWER(:query)
            ORDER BY name
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
        
        return players
    except Exception as e:
        logger.error(f"Error searching players: {e}")
        return []  # Return empty array on error instead of 500
    finally:
        session.close()
