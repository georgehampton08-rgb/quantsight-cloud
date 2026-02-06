"""
SQLite to Cloud SQL Data Export Script
Safely exports all data from local SQLite to Cloud SQL PostgreSQL
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
import sys

# Database connections
SQLITE_DB = r"c:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\data\nba_data.db"
POSTGRES_URL = "postgresql://quantsight:QSInvest2026@35.226.224.122:5432/nba_data"

def inspect_sqlite():
    """Inspect SQLite database structure and data counts"""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"\n{'='*80}")
    print(f"SQLite Database Inspection: {SQLITE_DB}")
    print(f"{'='*80}\n")
    
    table_info = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        
        table_info[table] = {
            'count': count,
            'columns': [col[1] for col in columns]
        }
        
        print(f"Table: {table}")
        print(f"  Rows: {count:,}")
        print(f"  Columns: {', '.join(table_info[table]['columns'])}")
        print()
    
    conn.close()
    return table_info

def export_table(table_name, sqlite_conn, postgres_conn):
    """Export a single table from SQLite to PostgreSQL"""
    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor()
    
    # Get all data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"  ⚠️  Table {table_name} is empty, skipping...")
        return 0
    
    # Get column names
    column_names = [description[0] for description in sqlite_cursor.description]
    
    # Create INSERT statement
    placeholders = ', '.join(['%s'] * len(column_names))
    columns_str = ', '.join(column_names)
    insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    
    # Batch insert
    execute_batch(postgres_cursor, insert_sql, rows, page_size=100)
    postgres_conn.commit()
    
    return len(rows)

def main():
    print("\n" + "="*80)
    print("QUANTSIGHT DATA MIGRATION: SQLite → Cloud SQL PostgreSQL")
    print("="*80 + "\n")
    
    # Step 1: Inspect SQLite
    print("STEP 1: Inspecting SQLite Database...")
    table_info = inspect_sqlite()
    
    total_rows = sum(info['count'] for info in table_info.values())
    print(f"Total tables: {len(table_info)}")
    print(f"Total rows to export: {total_rows:,}\n")
    
    # Step 2: Connect to PostgreSQL
    print("STEP 2: Connecting to Cloud SQL...")
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        postgres_conn = psycopg2.connect(POSTGRES_URL)
        print("✅ Connected to both databases\n")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return
    
    # Step 3: Export each table
    print("STEP 3: Exporting data...")
    exported_counts = {}
    
    for table_name in table_info.keys():
        print(f"  Exporting {table_name}...")
        try:
            count = export_table(table_name, sqlite_conn, postgres_conn)
            exported_counts[table_name] = count
            print(f"    ✅ Exported {count:,} rows")
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            exported_counts[table_name] = 0
    
    print()
    
    # Step 4: Verify
    print("STEP 4: Verifying export...")
    postgres_cursor = postgres_conn.cursor()
    
    for table_name in table_info.keys():
        postgres_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        postgres_count = postgres_cursor.fetchone()[0]
        sqlite_count = table_info[table_name]['count']
        
        if postgres_count >= sqlite_count:
            print(f"  ✅ {table_name}: {postgres_count:,} rows (expected {sqlite_count:,})")
        else:
            print(f"  ⚠️  {table_name}: {postgres_count:,} rows (expected {sqlite_count:,})")
    
    # Close connections
    sqlite_conn.close()
    postgres_conn.close()
    
    print("\n" + "="*80)
    print("MIGRATION COMPLETE!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
