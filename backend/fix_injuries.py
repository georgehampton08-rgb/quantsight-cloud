import sqlite3
conn = sqlite3.connect('data/nba_data.db')
c = conn.cursor()

# Check if injuries table exists
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='injuries'")
exists = c.fetchone() is not None
print(f"Injuries table exists: {exists}")

if not exists:
    print("Creating injuries table...")
    c.execute("""
        CREATE TABLE IF NOT EXISTS injuries (
            player_id TEXT PRIMARY KEY,
            player_name TEXT,
            team TEXT,
            status TEXT,
            injury_type TEXT,
            expected_return TEXT,
            last_updated TEXT
        )
    """)
    conn.commit()
    print("Table created!")

# Check count
c.execute("SELECT COUNT(*) FROM injuries")
print(f"Injury records: {c.fetchone()[0]}")

conn.close()
