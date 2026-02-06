"""
Migrate data from local SQLite to Firebase Firestore
Handles all collections: teams, players, player_stats, game_logs, team_stats
"""
import sqlite3
import sys
import logging
from datetime import datetime
from backend.firestore_db import (
    get_firestore_db,
    batch_write_teams,
    batch_write_players,
    batch_write_collection
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Local SQLite database path  
SQLITE_DB = r"c:\Users\georg\quantsight_engine\quantsight_cloud_build\backend\data\nba_data.db"

def migrate_teams():
    """Migrate teams from SQLite to Firestore"""
    logger.info("📦 Migrating teams...")
    
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM teams")
    rows = cursor.fetchall()
    
    teams = []
    for row in rows:
        team = dict(row)
        # Use tricode/abbreviation as document ID
        team['id'] = team.get('tricode', team.get('abbreviation', team.get('id')))
        team['last_updated'] = datetime.utcnow()
        teams.append(team)
    
    batch_write_teams(teams)
    logger.info(f"✅ Migrated {len(teams)} teams")
    
    conn.close()
    return len(teams)

def migrate_players():
    """Migrate players from SQLite to Firestore"""
    logger.info("📦 Migrating players...")
    
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all players
    cursor.execute("SELECT * FROM players")
    rows = cursor.fetchall()
    
    players = []
    for row in rows:
        player = dict(row)
        
        # Ensure is_active field exists (default to True for current season)
        if 'is_active' not in player or player['is_active'] is None:
            # Mark as active if they have a team
            player['is_active'] = bool(player.get('team_abbreviation'))
        
        # Convert to boolean if it's an integer
        if isinstance(player.get('is_active'), int):
            player['is_active'] = bool(player['is_active'])
        
        player['last_updated'] = datetime.utcnow()
        
        # Denormalize: add team name if we have team abbreviation
        if player.get('team_abbreviation'):
            # We'll fetch team name from teams table
            team_abbr = player['team_abbreviation']
            cursor.execute("SELECT full_name FROM teams WHERE tricode = ? OR abbreviation = ?", (team_abbr, team_abbr))
            team_row = cursor.fetchone()
            if team_row:
                player['team_name'] = team_row['full_name']
        
        players.append(player)
    
    # Write in batches (Firestore limit is 500 per batch)
    batch_write_players(players)
    logger.info(f"✅ Migrated {len(players)} players (2020+ seasons)")
    
    conn.close()
    return len(players)

def migrate_player_stats():
    """Migrate player_stats from SQLite to Firestore"""
    logger.info("📦 Migrating player_stats...")
    
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM player_stats")
        rows = cursor.fetchall()
        
        stats = []
        for row in rows:
            stat = dict(row)
            stats.append(stat)
        
        if stats:
            batch_write_collection('player_stats', stats, id_field='player_id')
            logger.info(f"✅ Migrated {len(stats)} player_stats")
        else:
            logger.warning("⚠️ No player_stats found in SQLite")
        
        conn.close()
        return len(stats)
    except sqlite3.OperationalError as e:
        logger.warning(f"⚠️ player_stats table not found: {e}")
        conn.close()
        return 0

def migrate_game_logs():
    """Migrate game_logs from SQLite to Firestore (2020+ only)"""
    logger.info("📦 Migrating game_logs (2020+ seasons)...")
    
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Only get recent game logs (2020+) to save space
        cursor.execute("""
            SELECT * FROM game_logs 
            WHERE game_date >= '2020-01-01' 
            ORDER BY game_date DESC 
            LIMIT 10000
        """)
        rows = cursor.fetchall()
        
        logs = []
        for row in rows:
            log = dict(row)
            # Create composite ID: game_id + player_id
            log['id'] = f"{log.get('game_id', '')}_{log.get('player_id', '')}"
            logs.append(log)
        
        if logs:
            batch_write_collection('game_logs', logs, id_field='id')
            logger.info(f"✅ Migrated {len(logs)} game_logs (2020+)")
        else:
            logger.warning("⚠️ No game_logs found in SQLite")
        
        conn.close()
        return len(logs)
    except sqlite3.OperationalError as e:
        logger.warning(f"⚠️ game_logs table not found or no game_date column: {e}")
        conn.close()
        return 0

def migrate_team_stats():
    """Migrate team_stats from SQLite to Firestore"""
    logger.info("📦 Migrating team_stats...")
    
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM team_stats")
        rows = cursor.fetchall()
        
        stats = []
        for row in rows:
            stat = dict(row)
            # Use team_id or team_abbreviation as document ID
            if 'id' not in stat and 'team_id' not in stat:
                stat['id'] = stat.get('team_abbreviation', stat.get('tricode'))
            stats.append(stat)
        
        if stats:
            batch_write_collection('team_stats', stats, id_field='team_id' if 'team_id' in stats[0] else 'id')
            logger.info(f"✅ Migrated {len(stats)} team_stats")
        else:
            logger.warning("⚠️ No team_stats found in SQLite")
        
        conn.close()
        return len(stats)
    except sqlite3.OperationalError as e:
        logger.warning(f"⚠️ team_stats table not found: {e}")
        conn.close()
        return 0

def verify_migration():
    """Verify all data was migrated correctly"""
    logger.info("🔍 Verifying migration...")
    
    db = get_firestore_db()
    
    collections = {
        'teams': db.collection('teams').stream(),
        'players': db.collection('players').stream(),
        'player_stats': db.collection('player_stats').stream(),
        'game_logs': db.collection('game_logs').stream(),
        'team_stats': db.collection('team_stats').stream()
    }
    
    for collection_name, docs in collections.items():
        count = sum(1 for _ in docs)
        logger.info(f"  {collection_name}: {count} documents")
    
    # Verify active players count
    active_players = db.collection('players').where(filter=FieldFilter('is_active', '==', True)).stream()
    active_count = sum(1 for _ in active_players)
    logger.info(f"  active players: {active_count} documents")

def main():
    """Run complete migration"""
    logger.info("🚀 Starting Firestore migration...")
    logger.info(f"📂 Source: {SQLITE_DB}")
    
    try:
        # Import FieldFilter here to avoid initialization issues
        from google.cloud.firestore_v1.base_query import FieldFilter
        globals()['FieldFilter'] = FieldFilter
        
        teams_count = migrate_teams()
        players_count = migrate_players()
        stats_count = migrate_player_stats()
        logs_count = migrate_game_logs()
        team_stats_count = migrate_team_stats()
        
        logger.info("\n" + "="*50)
        logger.info("✅ Migration Complete!")
        logger.info("="*50)
        logger.info(f"Teams: {teams_count}")
        logger.info(f"Players: {players_count}")
        logger.info(f"Player Stats: {stats_count}")
        logger.info(f"Game Logs: {logs_count}")
        logger.info(f"Team Stats: {team_stats_count}")
        logger.info("="*50)
        
        verify_migration()
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
