"""
Sync Local SQLite to Cloud SQL
Migrates player data from local desktop DB to cloud PostgreSQL
"""
import sqlite3
import os
from sqlalchemy import create_engine, text

# Local SQLite path
LOCAL_DB = r"C:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\nba_data.db"

# Cloud SQL connection (via Cloud SQL Proxy or direct)
CLOUD_DB_URL = os.getenv('DATABASE_URL', 'postgresql://quantsight:QuantSight2026!@/nba_data?host=/cloudsql/quantsight-prod:us-central1:quantsight-db')

def get_local_tables():
    """Get all tables from local SQLite"""
    conn = sqlite3.connect(LOCAL_DB)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor]
    conn.close()
    return tables

def get_table_count(conn, table):
    """Get row count from a table"""
    try:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]
    except:
        return 0

def sync_players():
    """Sync players from local to cloud"""
    local = sqlite3.connect(LOCAL_DB)
    local.row_factory = sqlite3.Row
    
    # Get players from local
    cursor = local.execute("SELECT * FROM players LIMIT 1")
    columns = [desc[0] for desc in cursor.description]
    print(f"Local players columns: {columns}")
    
    cursor = local.execute("SELECT * FROM players")
    players = [dict(row) for row in cursor]
    print(f"Found {len(players)} players in local DB")
    
    local.close()
    return players

def main():
    print("="*60)
    print(" LOCAL SQLITE DATABASE ANALYSIS")
    print("="*60)
    
    if not os.path.exists(LOCAL_DB):
        print(f"❌ Local DB not found: {LOCAL_DB}")
        return
    
    # Analyze local database
    tables = get_local_tables()
    print(f"\nTables in local DB: {tables}")
    
    conn = sqlite3.connect(LOCAL_DB)
    
    print("\nTable counts:")
    for table in tables:
        count = get_table_count(conn, table)
        print(f"  {table}: {count} rows")
    
    # Check players table structure
    print("\n" + "="*60)
    print(" PLAYERS TABLE STRUCTURE")
    print("="*60)
    
    try:
        cursor = conn.execute("PRAGMA table_info(players)")
        columns = [(row[1], row[2]) for row in cursor]
        print(f"Columns: {columns}")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()
    
    print("\n" + "="*60)
    print(" RECOMMENDATION")
    print("="*60)
    print("""
To sync local data to Cloud SQL:
1. Run: gcloud sql connect quantsight-db --user=quantsight --project=quantsight-prod
2. Or use a Cloud SQL Proxy to connect locally
3. Then run the INSERT statements

Alternatively, use the admin endpoint to seed from NBA API.
""")

if __name__ == "__main__":
    main()
