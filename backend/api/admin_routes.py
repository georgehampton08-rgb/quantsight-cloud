"""
Cloud Admin Routes - Database Initialization & Data Seeding
============================================================
Protected endpoints for database management (call once per environment).
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


def get_database_url() -> str:
    """Get database URL from environment."""
    db_url = os.getenv('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    return db_url


@router.post("/init-schema")
async def initialize_schema():
    """
    Create all database tables.
    Call this ONCE after first deployment.
    """
    from scripts.init_cloud_db import Base, verify_schema
    
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    logger.info("🔧 Initializing database schema...")
    
    try:
        engine = create_engine(db_url, echo=True)
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        # Verify
        tables_created = list(Base.metadata.tables.keys())
        
        # Quick verification
        with engine.connect() as conn:
            result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            existing_tables = [row[0] for row in result]
        
        engine.dispose()
        
        return {
            "status": "success",
            "message": "Schema initialized successfully",
            "tables_created": tables_created,
            "tables_verified": existing_tables
        }
        
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed-teams")
async def seed_teams():
    """Seed NBA teams (30 teams, static data)."""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    # NBA Teams data
    NBA_TEAMS = [
        (1610612737, "ATL", "Atlanta Hawks", "Atlanta", "Hawks", "East", "Southeast"),
        (1610612738, "BOS", "Boston Celtics", "Boston", "Celtics", "East", "Atlantic"),
        (1610612751, "BKN", "Brooklyn Nets", "Brooklyn", "Nets", "East", "Atlantic"),
        (1610612766, "CHA", "Charlotte Hornets", "Charlotte", "Hornets", "East", "Southeast"),
        (1610612741, "CHI", "Chicago Bulls", "Chicago", "Bulls", "East", "Central"),
        (1610612739, "CLE", "Cleveland Cavaliers", "Cleveland", "Cavaliers", "East", "Central"),
        (1610612742, "DAL", "Dallas Mavericks", "Dallas", "Mavericks", "West", "Southwest"),
        (1610612743, "DEN", "Denver Nuggets", "Denver", "Nuggets", "West", "Northwest"),
        (1610612765, "DET", "Detroit Pistons", "Detroit", "Pistons", "East", "Central"),
        (1610612744, "GSW", "Golden State Warriors", "Golden State", "Warriors", "West", "Pacific"),
        (1610612745, "HOU", "Houston Rockets", "Houston", "Rockets", "West", "Southwest"),
        (1610612754, "IND", "Indiana Pacers", "Indiana", "Pacers", "East", "Central"),
        (1610612746, "LAC", "LA Clippers", "Los Angeles", "Clippers", "West", "Pacific"),
        (1610612747, "LAL", "Los Angeles Lakers", "Los Angeles", "Lakers", "West", "Pacific"),
        (1610612763, "MEM", "Memphis Grizzlies", "Memphis", "Grizzlies", "West", "Southwest"),
        (1610612748, "MIA", "Miami Heat", "Miami", "Heat", "East", "Southeast"),
        (1610612749, "MIL", "Milwaukee Bucks", "Milwaukee", "Bucks", "East", "Central"),
        (1610612750, "MIN", "Minnesota Timberwolves", "Minnesota", "Timberwolves", "West", "Northwest"),
        (1610612740, "NOP", "New Orleans Pelicans", "New Orleans", "Pelicans", "West", "Southwest"),
        (1610612752, "NYK", "New York Knicks", "New York", "Knicks", "East", "Atlantic"),
        (1610612760, "OKC", "Oklahoma City Thunder", "Oklahoma City", "Thunder", "West", "Northwest"),
        (1610612753, "ORL", "Orlando Magic", "Orlando", "Magic", "East", "Southeast"),
        (1610612755, "PHI", "Philadelphia 76ers", "Philadelphia", "76ers", "East", "Atlantic"),
        (1610612756, "PHX", "Phoenix Suns", "Phoenix", "Suns", "West", "Pacific"),
        (1610612757, "POR", "Portland Trail Blazers", "Portland", "Trail Blazers", "West", "Northwest"),
        (1610612758, "SAC", "Sacramento Kings", "Sacramento", "Kings", "West", "Pacific"),
        (1610612759, "SAS", "San Antonio Spurs", "San Antonio", "Spurs", "West", "Southwest"),
        (1610612761, "TOR", "Toronto Raptors", "Toronto", "Raptors", "East", "Atlantic"),
        (1610612762, "UTA", "Utah Jazz", "Utah", "Jazz", "West", "Northwest"),
        (1610612764, "WAS", "Washington Wizards", "Washington", "Wizards", "East", "Southeast"),
    ]
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Insert teams
            for team in NBA_TEAMS:
                conn.execute(text("""
                    INSERT INTO teams (team_id, abbreviation, full_name, city, nickname, conference, division)
                    VALUES (:team_id, :abbr, :full_name, :city, :nickname, :conf, :div)
                    ON CONFLICT (team_id) DO UPDATE SET
                        abbreviation = EXCLUDED.abbreviation,
                        full_name = EXCLUDED.full_name
                """), {
                    "team_id": team[0],
                    "abbr": team[1],
                    "full_name": team[2],
                    "city": team[3],
                    "nickname": team[4],
                    "conf": team[5],
                    "div": team[6]
                })
            conn.commit()
        
        engine.dispose()
        
        return {
            "status": "success",
            "message": f"Seeded {len(NBA_TEAMS)} NBA teams"
        }
        
    except Exception as e:
        logger.error(f"❌ Team seeding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed-team-defense")
async def seed_team_defense():
    """Seed team defense ratings for current season."""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    # 2024-25 Team Defense Ratings (approximate - will be updated by daily job)
    TEAM_DEFENSE = [
        ("CLE", 105.2, 1), ("OKC", 106.8, 2), ("HOU", 107.5, 3), ("BOS", 108.1, 4),
        ("MEM", 108.5, 5), ("LAC", 109.2, 6), ("ORL", 109.5, 7), ("MIN", 110.0, 8),
        ("DEN", 110.3, 9), ("NYK", 110.5, 10), ("MIA", 110.8, 11), ("GSW", 111.0, 12),
        ("SAC", 111.3, 13), ("MIL", 111.5, 14), ("LAL", 111.8, 15), ("PHX", 112.0, 16),
        ("DAL", 112.3, 17), ("IND", 112.5, 18), ("SAS", 112.8, 19), ("TOR", 113.0, 20),
        ("NOP", 113.3, 21), ("BKN", 113.5, 22), ("ATL", 114.0, 23), ("CHI", 114.3, 24),
        ("POR", 114.5, 25), ("PHI", 114.8, 26), ("DET", 115.0, 27), ("CHA", 115.5, 28),
        ("UTA", 116.0, 29), ("WAS", 118.5, 30),
    ]
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            for team in TEAM_DEFENSE:
                conn.execute(text("""
                    INSERT INTO team_defense (team_abbreviation, season, defensive_rating, defensive_rank, last_updated)
                    VALUES (:abbr, '2024-25', :def_rating, :rank, NOW())
                    ON CONFLICT (team_abbreviation, season) DO UPDATE SET
                        defensive_rating = EXCLUDED.defensive_rating,
                        defensive_rank = EXCLUDED.defensive_rank,
                        last_updated = NOW()
                """), {
                    "abbr": team[0],
                    "def_rating": team[1],
                    "rank": team[2]
                })
            conn.commit()
        
        engine.dispose()
        
        return {
            "status": "success",
            "message": f"Seeded defense ratings for {len(TEAM_DEFENSE)} teams"
        }
        
    except Exception as e:
        logger.error(f"❌ Defense seeding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed-players")
async def seed_players():
    """Seed all active NBA players from NBA Stats API"""
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    logger.info("🔧 Fetching players from NBA Stats API...")
    
    try:
        import requests
        from datetime import datetime
        
        # Fetch all active players from NBA API
        url = "https://stats.nba.com/stats/commonallplayers"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
            'Referer': 'https://stats.nba.com/',
            'Origin': 'https://stats.nba.com'
        }
        params = {
            'LeagueID': '00',
            'Season': '2024-25',
            'IsOnlyCurrentSeason': '1'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        players_data = data['resultSets'][0]
        headers_list = players_data['headers']
        rows = players_data['rowSet']
        
        # Find column indices
        person_id_idx = headers_list.index('PERSON_ID')
        display_name_idx = headers_list.index('DISPLAY_FIRST_LAST')
        team_id_idx = headers_list.index('TEAM_ID')
        team_abbr_idx = headers_list.index('TEAM_ABBREVIATION')
        
        logger.info(f"✅ Fetched {len(rows)} players from NBA API")
        
        # Insert into database
        engine = create_engine(db_url)
        inserted_count = 0
        
        with engine.connect() as conn:
            for row in rows:
                player_id = row[person_id_idx]
                full_name = row[display_name_idx]
                team_id = row[team_id_idx]
                team_abbr = row[team_abbr_idx]
                
                # Skip if no team (free agents)
                if not team_id or team_id == 0:
                    continue
                
                # Split name into first name, last name
                parts = full_name.split(' ', 1)
                first_name = parts[0] if parts else ''
                last_name = parts[1] if len(parts) > 1 else parts[0]
                
                conn.execute(text("""
                    INSERT INTO players (
                        player_id, full_name, first_name, last_name,
                        team_id, team_abbreviation, is_active, last_updated
                    )
                    VALUES (
                        :player_id, :full_name, :first_name, :last_name,
                        :team_id, :team_abbr, TRUE, :now
                    )
                    ON CONFLICT (player_id) DO UPDATE SET
                        full_name = EXCLUDED.full_name,
                        team_id = EXCLUDED.team_id,
                        team_abbreviation = EXCLUDED.team_abbreviation,
                        last_updated = EXCLUDED.last_updated
                """), {
                    "player_id": player_id,
                    "full_name": full_name,
                    "first_name": first_name,
                    "last_name": last_name,
                    "team_id": team_id,
                    "team_abbr": team_abbr,
                    "now": datetime.utcnow()
                })
                inserted_count += 1
            
            conn.commit()
        
        engine.dispose()
        
        logger.info(f"✅ Successfully seeded {inserted_count} players")
        
        return {
            "status": "success",
            "message": f"Seeded {inserted_count} active NBA players",
            "total_fetched": len(rows),
            "total_inserted": inserted_count
        }
        
    except Exception as e:
        logger.error(f"❌ Player seeding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db-status")
async def database_status():
    """Check database connection and table counts."""
    db_url = get_database_url()
    if not db_url:
        return {"status": "error", "message": "DATABASE_URL not configured"}
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Get table counts
            tables = ["teams", "players", "player_stats", "player_rolling_averages", "game_logs", "team_defense"]
            counts = {}
            
            for table in tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    counts[table] = result.scalar()
                except Exception:
                    counts[table] = "table not found"
        
        engine.dispose()
        
        return {
            "status": "connected",
            "database": "Cloud SQL PostgreSQL",
            "table_counts": counts
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
