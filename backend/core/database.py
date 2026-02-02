"""
Database Configuration for Cloud Backend
=========================================
Hybrid setup: SQLite for local development, PostgreSQL for Cloud Run production.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

# Database URL selection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    # Default: SQLite for local testing
    f"sqlite:///{Path(__file__).parent.parent / 'data' / 'nba_data.db'}"
)

# For Cloud Run, expect:
# DATABASE_URL=postgresql://user:password@/cloudsql/project:region:instance

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific config
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    # PostgreSQL-specific config (Cloud SQL)
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=2,
        pool_timeout=30,
        pool_recycle=1800,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI routes to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_connection():
    """Legacy compatibility for raw connection access."""
    return engine.connect()
