"""
Comprehensive Local-to-Cloud Data Sync
Migrates all NBA data from local SQLite to Cloud SQL via admin API
"""
import sqlite3
import requests
import json

LOCAL_DB = r'C:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\data\nba_data.db'
CLOUD_API = "https://quantsight-cloud-458498663186.us-central1.run.app"

def analyze_local_db():
    """Analyze local SQLite database structure and content"""
    print("="*60)
    print(" LOCAL DATABASE ANALYSIS")
    print("="*60)
    
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\nFound {len(tables)} tables:")
    
    table_data = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} rows")
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        table_data[table] = {'count': count, 'columns': columns}
    
    conn.close()
    return table_data

def export_players():
    """Export players from local SQLite"""
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    
    # Check if players table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
    if not cursor.fetchone():
        print("No 'players' table found in local DB")
        # Try alternative tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%player%'")
        alternatives = [r[0] for r in cursor.fetchall()]
        print(f"Alternative player tables: {alternatives}")
        conn.close()
        return []
    
    cursor.execute("SELECT * FROM players LIMIT 5")
    sample = cursor.fetchall()
    print(f"Sample players: {sample}")
    
    cursor.execute("SELECT * FROM players")
    players = cursor.fetchall()
    conn.close()
    
    return players

def export_game_logs():
    """Export game logs from local SQLite"""
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_logs'")
    if not cursor.fetchone():
        print("No 'game_logs' table found")
        return []
    
    # Get column names
    cursor.execute("PRAGMA table_info(game_logs)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Game logs columns: {columns[:10]}...")
    
    cursor.execute("SELECT COUNT(*) FROM game_logs")
    count = cursor.fetchone()[0]
    print(f"Total game logs: {count}")
    
    # Get sample
    cursor.execute("SELECT * FROM game_logs LIMIT 3")
    sample = cursor.fetchall()
    print(f"Sample: {sample[0][:5] if sample else 'None'}...")
    
    conn.close()
    return count

def export_rolling_averages():
    """Export player rolling averages"""
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player_rolling_averages'")
    if not cursor.fetchone():
        print("No 'player_rolling_averages' table found")
        return 0
    
    cursor.execute("SELECT COUNT(*) FROM player_rolling_averages")
    count = cursor.fetchone()[0]
    print(f"Total rolling averages: {count}")
    
    conn.close()
    return count

def main():
    # Analyze local DB
    table_data = analyze_local_db()
    
    print("\n" + "="*60)
    print(" DATA EXPORT SUMMARY")
    print("="*60)
    
    # Export each data type
    players = export_players()
    game_logs_count = export_game_logs()
    rolling_avg_count = export_rolling_averages()
    
    print("\n" + "="*60)
    print(" READY FOR SYNC")
    print("="*60)
    print(f"Players: {len(players) if players else 'N/A'}")
    print(f"Game Logs: {game_logs_count}")
    print(f"Rolling Averages: {rolling_avg_count}")
    print(f"Tables: {list(table_data.keys())}")

if __name__ == "__main__":
    main()
