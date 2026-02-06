import sqlite3

c = sqlite3.connect('data/nba_data.db')
cur = c.cursor()

# List all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

# Check player_game_logs table structure (production data source)
if 'player_game_logs' in tables:
    cur.execute("PRAGMA table_info(player_game_logs)")
    print("\nplayer_game_logs columns:")
    for col in cur.fetchall():
        print(f"  {col[1]}: {col[2]}")
    
    # Count and sample
    cur.execute("SELECT COUNT(*) FROM player_game_logs")
    count = cur.fetchone()[0]
    print(f"\nTotal rows: {count}")
    
    # Sample for LeBron (2544)
    cur.execute("SELECT * FROM player_game_logs WHERE player_id = '2544' ORDER BY game_date DESC LIMIT 3")
    print("\nLeBron's last 3 games:")
    for row in cur.fetchall():
        print(f"  {row}")
else:
    print("\n[ERROR] player_game_logs table NOT FOUND!")
    print("Available tables:", tables)

c.close()

