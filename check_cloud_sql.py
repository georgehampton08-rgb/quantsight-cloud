import psycopg2

conn = psycopg2.connect('postgresql://quantsight:QSInvest2026@35.226.224.122:5432/nba_data')
cursor = conn.cursor()
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
tables = [row[0] for row in cursor.fetchall()]
print(f"\nCloud SQL Tables: {len(tables)}")
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count} rows")
conn.close()
