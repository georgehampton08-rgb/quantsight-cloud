"""
Centralized Data Paths Configuration
=====================================
Single source of truth for all data file locations.
All modules should import from here to ensure consistency.

Usage:
    from data_paths import get_db_path, get_data_dir, DATA_TABLES
"""

import os
from pathlib import Path
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# PATH DETECTION
# ============================================================================

def _find_backend_dir() -> Path:
    """Find the backend directory from any script location"""
    # Start from this file's location
    current = Path(__file__).parent.absolute()
    
    # If we're already in backend/, we're good
    if current.name == 'backend':
        return current
    
    # If we're in a subdirectory of backend/ (like services/, aegis/)
    if current.parent.name == 'backend':
        return current.parent
    
    # Search upward for backend/
    for parent in current.parents:
        if (parent / 'backend').exists():
            return parent / 'backend'
        if parent.name == 'backend':
            return parent
    
    # Fallback: assume we're in backend/
    return current


def _find_exe_dir() -> Path:
    """Find executable directory (for packaged builds)"""
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return _find_backend_dir()


# ============================================================================
# CORE PATHS
# ============================================================================

BACKEND_DIR = _find_backend_dir()
DATA_DIR = BACKEND_DIR / 'data'
FETCHED_DIR = DATA_DIR / 'fetched'

# Database paths to check in order of priority
_DB_PATHS_TO_CHECK = [
    DATA_DIR / 'nba_data.db',                                    # Standard dev path
    BACKEND_DIR / 'nba_data.db',                                 # Alternative
    _find_exe_dir() / 'data' / 'nba_data.db',                   # Packaged mode
    Path(os.environ.get('APPDATA', '')) / 'QuantSight' / 'data' / 'nba_data.db',  # User data
]


def get_db_path() -> Optional[Path]:
    """
    Get the NBA database path.
    Checks multiple locations for packaged vs dev mode compatibility.
    Returns None if no database found.
    """
    for path in _DB_PATHS_TO_CHECK:
        if path.exists():
            return path
    
    # If none exist, return the default (for creation)
    return DATA_DIR / 'nba_data.db'


def get_data_dir() -> Path:
    """Get the data directory, creating if needed"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_fetched_dir() -> Path:
    """Get the fetched data directory, creating if needed"""
    FETCHED_DIR.mkdir(parents=True, exist_ok=True)
    return FETCHED_DIR


# ============================================================================
# TABLE REGISTRY
# ============================================================================

DATA_TABLES = {
    # Core player data
    'players': {
        'description': 'Basic player info (name, team, position)',
        'primary_key': 'player_id',
        'updated_by': ['fetch_advanced_stats.py', 'fetch_gamelogs_smart.py'],
    },
    'player_stats': {
        'description': 'Season averages (PPG, RPG, APG)',
        'primary_key': 'player_id',
        'updated_by': ['fetch_advanced_stats.py'],
    },
    'player_advanced_stats': {
        'description': 'Advanced analytics (TS%, Usage%, PIE)',
        'primary_key': 'player_id',
        'updated_by': ['fetch_advanced_stats.py'],
    },
    
    # Game-level data
    'player_game_logs': {
        'description': 'Individual game records with opponent',
        'primary_key': ['player_id', 'game_id'],
        'updated_by': ['fetch_todays_games.py', 'fetch_gamelogs_smart.py'],
        'date_column': 'fetched_at',
    },
    'player_rolling_averages': {
        'description': 'Rolling averages and hot/cold trends',
        'primary_key': 'player_id',
        'updated_by': ['fetch_todays_games.py', 'fetch_gamelogs_smart.py'],
        'date_column': 'updated_at',
    },
    'player_bio': {
        'description': 'Biographical info (height, weight, age, headshot)',
        'primary_key': 'player_id',
        'updated_by': ['fetch_todays_games.py', 'fetch_gamelogs_smart.py'],
        'date_column': 'updated_at',
    },
    
    # Team/matchup intelligence
    'team_defense': {
        'description': 'Team defensive ratings and pace',
        'primary_key': 'team_abbr',
        'updated_by': ['fetch_team_defense.py'],
        'date_column': 'updated_at',
    },
    'player_vs_team': {
        'description': 'Historical player performance vs each team',
        'primary_key': ['player_id', 'opponent'],
        'updated_by': ['fetch_team_defense.py'],
        'date_column': 'updated_at',
    },
    
    # Quick batch data
    'team_standings': {
        'description': 'Current team standings and records',
        'primary_key': 'team_id',
        'updated_by': ['fetch_quick_batch.py'],
        'date_column': 'updated_at',
    },
    'league_leaders': {
        'description': 'Top 10 in each stat category',
        'primary_key': ['category', 'rank'],
        'updated_by': ['fetch_quick_batch.py'],
        'date_column': 'updated_at',
    },
    'todays_games': {
        'description': 'Today\'s schedule and scores',
        'primary_key': 'game_id',
        'updated_by': ['fetch_quick_batch.py'],
        'date_column': 'updated_at',
    },
    
    # System tables
    'fetcher_registry': {
        'description': 'Registered data fetchers and schedules',
        'primary_key': 'fetcher_id',
        'updated_by': ['fetcher_registry.py'],
    },
    'fetcher_runs': {
        'description': 'Fetcher run history and status',
        'primary_key': 'fetcher_id',
        'updated_by': ['fetcher_registry.py'],
    },
}


def get_table_info(table_name: str) -> Optional[Dict]:
    """Get metadata about a table"""
    return DATA_TABLES.get(table_name)


def get_all_tables() -> List[str]:
    """Get list of all registered tables"""
    return list(DATA_TABLES.keys())


# ============================================================================
# CONNECTION HELPER
# ============================================================================

def get_db_connection(row_factory=None, timeout=30, enable_wal=True):
    """
    Get a database connection with optional row factory.
    
    Features:
        - WAL mode: Enables concurrent reads while writing (prevents locks)
        - Busy timeout: Waits instead of failing on contention
        - Row factory: Optional dict results
    
    Usage:
        conn = get_db_connection()
        # or for dict results:
        conn = get_db_connection(row_factory='dict')
    """
    import sqlite3
    
    db_path = get_db_path()
    if not db_path or not db_path.exists():
        logger.warning(f"Database not found at {db_path}")
        return None
    
    # Connect with timeout for busy waiting
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    
    # Enable WAL mode for concurrent access 
    # WAL allows readers to not block writers and vice versa
    if enable_wal:
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')  # Faster writes, still safe with WAL
        except Exception as e:
            logger.warning(f"Could not enable WAL mode: {e}")
    
    # Set busy timeout (milliseconds to wait for lock)
    conn.execute(f'PRAGMA busy_timeout={timeout * 1000}')
    
    if row_factory == 'dict':
        def dict_factory(cursor, row):
            return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        conn.row_factory = dict_factory
    elif row_factory:
        conn.row_factory = row_factory
    
    return conn


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (table_name,))
        
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    except Exception:
        return False


def get_table_freshness(table_name: str) -> Optional[Dict]:
    """Get freshness info for a table"""
    table_info = DATA_TABLES.get(table_name)
    if not table_info:
        return None
    
    try:
        conn = get_db_connection(row_factory='dict')
        if not conn:
            return {'available': False}
        
        cursor = conn.cursor()
        date_col = table_info.get('date_column', 'updated_at')
        
        cursor.execute(f"""
            SELECT MAX({date_col}) as last_update, COUNT(*) as count
            FROM {table_name}
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            from datetime import datetime
            last_update = row.get('last_update')
            if last_update:
                age_minutes = (datetime.now() - datetime.fromisoformat(last_update)).total_seconds() / 60
            else:
                age_minutes = None
            
            return {
                'table': table_name,
                'last_update': last_update,
                'age_minutes': round(age_minutes) if age_minutes else None,
                'record_count': row.get('count', 0),
                'available': True,
            }
    except Exception as e:
        return {'table': table_name, 'available': False, 'error': str(e)}


# ============================================================================
# HEALTH CHECK
# ============================================================================

def get_data_health() -> Dict:
    """
    Get comprehensive data health status.
    Useful for health endpoints and monitoring.
    """
    from datetime import datetime
    
    db_path = get_db_path()
    health = {
        'database_path': str(db_path) if db_path else None,
        'database_exists': db_path.exists() if db_path else False,
        'data_dir': str(DATA_DIR),
        'data_dir_exists': DATA_DIR.exists(),
        'checked_at': datetime.now().isoformat(),
        'tables': {}
    }
    
    if not health['database_exists']:
        health['status'] = 'no_database'
        return health
    
    # Check each registered table
    for table_name in DATA_TABLES:
        if check_table_exists(table_name):
            freshness = get_table_freshness(table_name)
            health['tables'][table_name] = freshness
        else:
            health['tables'][table_name] = {'available': False, 'reason': 'table_not_found'}
    
    # Overall status
    available_tables = sum(1 for t in health['tables'].values() if t.get('available'))
    total_tables = len(DATA_TABLES)
    
    if available_tables == total_tables:
        health['status'] = 'healthy'
    elif available_tables > 0:
        health['status'] = 'partial'
    else:
        health['status'] = 'empty'
    
    health['available_tables'] = available_tables
    health['total_tables'] = total_tables
    
    return health


# Quick test when run directly
if __name__ == '__main__':
    print("="*60)
    print("DATA PATHS CONFIGURATION")
    print("="*60)
    print(f"\nBackend Dir: {BACKEND_DIR}")
    print(f"Data Dir: {DATA_DIR}")
    print(f"DB Path: {get_db_path()}")
    print(f"DB Exists: {get_db_path().exists() if get_db_path() else False}")
    print(f"\nRegistered Tables: {len(DATA_TABLES)}")
    
    print("\n" + "-"*60)
    health = get_data_health()
    print(f"Status: {health['status']}")
    print(f"Available: {health['available_tables']}/{health['total_tables']} tables")
