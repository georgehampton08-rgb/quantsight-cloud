"""
Quick script to check and calculate player_vs_team matchup data
"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check current data
print("=== PLAYER VS TEAM DATA STATUS ===")
cursor.execute("SELECT COUNT(*) FROM player_vs_team")
print(f"Total matchup records: {cursor.fetchone()[0]}")

cursor.execute("SELECT opponent, COUNT(*) FROM player_vs_team GROUP BY opponent ORDER BY COUNT(*) DESC LIMIT 10")
print("\nTop opponents with data:")
for row in cursor.fetchall():
    print(f"  vs {row[0]}: {row[1]} players")

# Check for LAL and CLE players specifically
print("\n=== CHECKING LAL AND CLE PLAYERS ===")

# Get LAL player IDs from player_bio
cursor.execute("SELECT player_id, player_name FROM player_bio WHERE team = 'LAL'")
lal_players = cursor.fetchall()
print(f"\nLAL players in bio: {len(lal_players)}")

# Check which have matchup data vs CLE
print("\nLAL players vs CLE matchup history:")
for pid, name in lal_players[:5]:
    cursor.execute("SELECT avg_pts, games FROM player_vs_team WHERE player_id = ? AND opponent = 'CLE'", (str(pid),))
    result = cursor.fetchone()
    if result:
        print(f"  ✅ {name}: {result[0]:.1f} PPG over {result[1]} games vs CLE")
    else:
        print(f"  ❌ {name}: No matchup history vs CLE")

# Get CLE player IDs
cursor.execute("SELECT player_id, player_name FROM player_bio WHERE team = 'CLE'")
cle_players = cursor.fetchall()
print(f"\nCLE players in bio: {len(cle_players)}")

print("\nCLE players vs LAL matchup history:")
for pid, name in cle_players[:5]:
    cursor.execute("SELECT avg_pts, games FROM player_vs_team WHERE player_id = ? AND opponent = 'LAL'", (str(pid),))
    result = cursor.fetchone()
    if result:
        print(f"  ✅ {name}: {result[0]:.1f} PPG over {result[1]} games vs LAL")
    else:
        print(f"  ❌ {name}: No matchup history vs LAL")

# Recalculate player_vs_team from game logs
print("\n=== RECALCULATING PLAYER VS TEAM FROM GAME LOGS ===")
cursor.execute("SELECT COUNT(*) FROM player_game_logs")
print(f"Total game logs: {cursor.fetchone()[0]}")

# Check game logs structure
cursor.execute("PRAGMA table_info(player_game_logs)")
cols = [row[1] for row in cursor.fetchall()]
print(f"Game logs columns: {cols}")

# Calculate aggregates
print("\nCalculating player vs team aggregates...")

# First check if 'games' column exists in player_vs_team
cursor.execute("PRAGMA table_info(player_vs_team)")
pvt_cols = [row[1] for row in cursor.fetchall()]
print(f"player_vs_team columns: {pvt_cols}")

# Try to determine the games column name
games_col = 'games'  # Default

try:
    cursor.execute(f"""
        INSERT OR REPLACE INTO player_vs_team
        (player_id, opponent, {games_col}, avg_pts, avg_reb, avg_ast, avg_fg_pct, last_game_date, updated_at)
        SELECT 
            player_id,
            opponent,
            COUNT(*) as {games_col},
            ROUND(AVG(points), 1) as avg_pts,
            ROUND(AVG(rebounds), 1) as avg_reb,
            ROUND(AVG(assists), 1) as avg_ast,
            ROUND(AVG(fg_pct), 3) as avg_fg_pct,
            MAX(game_date) as last_game_date,
            datetime('now') as updated_at
        FROM player_game_logs
        WHERE opponent IS NOT NULL AND opponent != ''
        GROUP BY player_id, opponent
    """)
    conn.commit()
    print(f"✅ Calculated {cursor.rowcount} matchup records")
except Exception as e:
    print(f"❌ Error: {e}")

# Check final count
cursor.execute("SELECT COUNT(*) FROM player_vs_team")
print(f"\nFinal matchup records: {cursor.fetchone()[0]}")

# Show sample of populated data
print("\n=== SAMPLE MATCHUP DATA ===")
cursor.execute("""
    SELECT pvt.player_id, pb.player_name, pvt.opponent, pvt.avg_pts, pvt.games
    FROM player_vs_team pvt
    JOIN player_bio pb ON pvt.player_id = pb.player_id
    WHERE pvt.avg_pts > 15
    ORDER BY pvt.avg_pts DESC
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"  {row[1]:20} vs {row[2]}: {row[3]:.1f} PPG ({row[4]}g)")

conn.close()
print("\n✅ Done!")
