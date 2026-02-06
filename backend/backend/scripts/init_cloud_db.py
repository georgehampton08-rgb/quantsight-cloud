"""
Cloud SQL Database Initialization Script
==========================================
Creates PostgreSQL schema matching desktop SQLite for Cloud SQL.

Usage:
    python init_cloud_db.py

Environment:
    DATABASE_URL: PostgreSQL connection string
    Example: postgresql://user:password@/nba_data?host=/cloudsql/project:region:instance
"""
import os
import sys
import logging
from datetime import datetime

from sqlalchemy import (
    create_engine, MetaData, Table, Column, 
    Integer, String, Float, DateTime, Boolean, Text, Date,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

Base = declarative_base()


# =============================================================================
# SCHEMA DEFINITIONS (Matching Desktop SQLite)
# =============================================================================

class Team(Base):
    """NBA Teams table - static reference data."""
    __tablename__ = 'teams'
    
    team_id = Column(Integer, primary_key=True)
    abbreviation = Column(String(3), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    city = Column(String(50))
    nickname = Column(String(50))
    conference = Column(String(10))  # East/West
    division = Column(String(20))
    logo_url = Column(String(255))
    primary_color = Column(String(7))  # Hex color
    secondary_color = Column(String(7))
    
    # Indexes
    __table_args__ = (
        Index('idx_teams_abbr', 'abbreviation'),
    )


class Player(Base):
    """NBA Players table - biographical and roster data."""
    __tablename__ = 'players'
    
    player_id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    team_id = Column(Integer, ForeignKey('teams.team_id'))
    team_abbreviation = Column(String(3))
    jersey_number = Column(String(5))
    position = Column(String(10))
    height = Column(String(10))  # e.g., "6-6"
    weight = Column(Integer)  # lbs
    birth_date = Column(Date)
    country = Column(String(50))
    draft_year = Column(Integer)
    draft_round = Column(Integer)
    draft_number = Column(Integer)
    is_active = Column(Boolean, default=True)
    headshot_url = Column(String(255))
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_players_name', 'full_name'),
        Index('idx_players_team', 'team_id'),
        Index('idx_players_active', 'is_active'),
    )


class PlayerStats(Base):
    """Player season statistics - aggregated per season."""
    __tablename__ = 'player_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    season = Column(String(10), nullable=False)  # e.g., "2024-25"
    team_abbreviation = Column(String(3))
    games_played = Column(Integer)
    games_started = Column(Integer)
    minutes_per_game = Column(Float)
    points_per_game = Column(Float)
    rebounds_per_game = Column(Float)
    assists_per_game = Column(Float)
    steals_per_game = Column(Float)
    blocks_per_game = Column(Float)
    turnovers_per_game = Column(Float)
    field_goal_pct = Column(Float)
    three_point_pct = Column(Float)
    free_throw_pct = Column(Float)
    true_shooting_pct = Column(Float)
    effective_fg_pct = Column(Float)
    usage_rate = Column(Float)
    pie = Column(Float)  # Player Impact Estimate
    plus_minus = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('player_id', 'season', name='uq_player_season'),
        Index('idx_player_stats_player', 'player_id'),
        Index('idx_player_stats_season', 'season'),
    )


class PlayerRollingAverages(Base):
    """
    Rolling averages for Heat Scale calculation.
    ⚠️ PROPRIETARY - Contains Alpha metrics, NOT exposed publicly.
    """
    __tablename__ = 'player_rolling_averages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    season = Column(String(10), nullable=False)
    window_size = Column(Integer, default=10)  # Last N games
    rolling_pts = Column(Float)
    rolling_reb = Column(Float)
    rolling_ast = Column(Float)
    rolling_ts_pct = Column(Float)  # Key for Heat Scale
    rolling_usage = Column(Float)
    rolling_pie = Column(Float)
    computed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('player_id', 'season', 'window_size', name='uq_player_rolling'),
        Index('idx_rolling_player', 'player_id'),
    )


class GameLog(Base):
    """Individual game statistics per player."""
    __tablename__ = 'game_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.player_id'), nullable=False)
    game_id = Column(String(20), nullable=False)
    game_date = Column(Date, nullable=False)
    season = Column(String(10))
    matchup = Column(String(20))  # e.g., "LAL vs. GSW"
    is_home = Column(Boolean)
    opponent_team = Column(String(3))
    result = Column(String(5))  # "W" or "L"
    minutes = Column(Integer)
    points = Column(Integer)
    rebounds = Column(Integer)
    assists = Column(Integer)
    steals = Column(Integer)
    blocks = Column(Integer)
    turnovers = Column(Integer)
    fgm = Column(Integer)
    fga = Column(Integer)
    fg3m = Column(Integer)
    fg3a = Column(Integer)
    ftm = Column(Integer)
    fta = Column(Integer)
    plus_minus = Column(Integer)
    
    __table_args__ = (
        UniqueConstraint('player_id', 'game_id', name='uq_player_game'),
        Index('idx_game_logs_player', 'player_id'),
        Index('idx_game_logs_date', 'game_date'),
        Index('idx_game_logs_season', 'season'),
        Index('idx_game_logs_opponent', 'opponent_team'),
    )


class TeamDefense(Base):
    """Team defensive ratings - cached for matchup analysis."""
    __tablename__ = 'team_defense'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_abbreviation = Column(String(3), nullable=False)
    season = Column(String(10), nullable=False)
    defensive_rating = Column(Float)  # Points allowed per 100 possessions
    opponent_fg_pct = Column(Float)
    opponent_3pt_pct = Column(Float)
    opponent_ft_pct = Column(Float)
    steals_per_game = Column(Float)
    blocks_per_game = Column(Float)
    defensive_rank = Column(Integer)  # 1-30
    vs_guards_rating = Column(Float)  # Position-specific defense
    vs_wings_rating = Column(Float)
    vs_bigs_rating = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('team_abbreviation', 'season', name='uq_team_defense_season'),
        Index('idx_team_defense_abbr', 'team_abbreviation'),
    )


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def get_database_url() -> str:
    """Get database URL from environment."""
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        logger.error("DATABASE_URL environment variable not set!")
        logger.info("Set it to: postgresql://user:pass@localhost/nba_data")
        sys.exit(1)
    
    # Handle Cloud SQL Unix socket format
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    return db_url


def create_database_engine(db_url: str) -> Engine:
    """Create SQLAlchemy engine with connection pooling."""
    return create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        echo=True  # Enable SQL logging for debugging
    )


def initialize_schema(engine: Engine):
    """Create all tables in the database."""
    logger.info("🔧 Creating database schema...")
    
    Base.metadata.create_all(engine)
    
    # Log created tables
    logger.info("✅ Tables created:")
    for table_name in Base.metadata.tables.keys():
        logger.info(f"   └─ {table_name}")


def verify_schema(engine: Engine):
    """Verify all tables exist and are accessible."""
    logger.info("🔍 Verifying schema...")
    
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    expected_tables = {'teams', 'players', 'player_stats', 'player_rolling_averages', 'game_logs', 'team_defense'}
    actual_tables = set(inspector.get_table_names())
    
    missing = expected_tables - actual_tables
    if missing:
        logger.error(f"❌ Missing tables: {missing}")
        return False
    
    logger.info("✅ All tables verified!")
    return True


def main():
    """Main entry point for database initialization."""
    logger.info("=" * 60)
    logger.info("QuantSight Cloud SQL - Database Initialization")
    logger.info("=" * 60)
    
    # Get database URL
    db_url = get_database_url()
    logger.info(f"📡 Connecting to database...")
    
    # Create engine
    engine = create_database_engine(db_url)
    
    try:
        # Test connection
        with engine.connect() as conn:
            logger.info("✅ Database connection successful!")
        
        # Create schema
        initialize_schema(engine)
        
        # Verify
        if verify_schema(engine):
            logger.info("=" * 60)
            logger.info("🎉 Database initialization complete!")
            logger.info("=" * 60)
        else:
            logger.error("Schema verification failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
