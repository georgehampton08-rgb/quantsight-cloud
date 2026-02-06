"""Populate missing position data in player_rolling_averages from player_bio"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check current status
cur.execute("SELECT COUNT(*) FROM player_rolling_averages WHERE position IS NOT NULL AND position != ''")
with_pos = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM player_rolling_averages WHERE position IS NULL OR position = ''")
missing_pos = cur.fetchone()[0]

print(f"Players with position: {with_pos}")
print(f"Players missing position: {missing_pos}")

# Update from player_bio
if missing_pos > 0:
    print(f"\nUpdating {missing_pos} players with position data from player_bio...")
    
    cur.execute("""
        UPDATE player_rolling_averages
        SET position = (
            SELECT pb.position 
            FROM player_bio pb 
            WHERE pb.player_id = player_rolling_averages.player_id
        )
        WHERE position IS NULL OR position = ''
    """)
    
    # Also update team_abbr if missing
    cur.execute("""
        UPDATE player_rolling_averages
        SET team_abbr = (
            SELECT pb.team 
            FROM player_bio pb 
            WHERE pb.player_id = player_rolling_averages.player_id
        )
        WHERE team_abbr IS NULL OR team_abbr = ''
    """)
    
    conn.commit()
    print(f"Updated {cur.rowcount} rows")

# Verify
cur.execute("SELECT COUNT(*) FROM player_rolling_averages WHERE position IS NOT NULL AND position != ''")
new_with_pos = cur.fetchone()[0]
print(f"\nNow with position: {new_with_pos}")

# Sample check
cur.execute("SELECT player_name, team_abbr, position FROM player_rolling_averages LIMIT 5")
print("\nSample data:")
for row in cur.fetchall():
    print(f"  {row['player_name']}: {row['team_abbr']} - {row['position']}")

conn.close()
print("\n✅ Position data populated!")
