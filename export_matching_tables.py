"""
Export only matching tables from SQLite to PostgreSQL
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch

SQLITE_DB = r"c:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\data\nba_data.db"
POSTGRES_URL = "postgresql://quantsight:QSInvest2026@35.226.224.122:5432/nba_data"

# Get tables from both databases
sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_cursor = sqlite_conn.cursor()
sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
sqlite_tables = set(row[0] for row in sqlite_cursor.fetchall())

postgres_conn = psycopg2.connect(POSTGRES_URL)
postgres_cursor = postgres_conn.cursor()
postgres_cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
postgres_tables = set(row[0] for row in postgres_cursor.fetchall())

# Find matching tables
matching_tables = sqlite_tables & postgres_tables

print(f"\nSQLite tables: {len(sqlite_tables)}")
print(f"PostgreSQL tables: {len(postgres_tables)}")
print(f"Matching tables: {len(matching_tables)}")
print(f"\nMatching tables: {', '.join(sorted(matching_tables))}\n")

# Export each matching table
for table in sorted(matching_tables):
    print(f"Exporting {table}...")
    
    # Get data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"  ⚠️  Empty, skipping...")
        continue
    
    # Get column names
    column_names = [description[0] for description in sqlite_cursor.description]
    
    # Create INSERT statement  
    placeholders = ', '.join(['%s'] * len(column_names))
    columns_str = ', '.join(column_names)
    insert_sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    
    try:
        execute_batch(postgres_cursor, insert_sql, rows, page_size=100)
        postgres_conn.commit()
        print(f"  ✅ Exported {len(rows):,} rows")
    except Exception as e:
        postgres_conn.rollback()
        print(f"  ❌ Failed: {str(e)[:100]}")

# Verify
print("\nVerifying export...")
for table in sorted(matching_tables):
    postgres_cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = postgres_cursor.fetchone()[0]
    print(f"  {table}: {count:,} rows")

sqlite_conn.close()
postgres_conn.close()

print("\n✅ Export complete!")
