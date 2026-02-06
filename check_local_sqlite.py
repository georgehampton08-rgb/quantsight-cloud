import sqlite3

conn = sqlite3.connect(r"c:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\data\nba_data.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print(f"\nLocal SQLite Tables: {len(tables)}")
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count:,} rows")
conn.close()
