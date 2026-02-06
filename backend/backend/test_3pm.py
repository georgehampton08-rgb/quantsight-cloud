"""Test 3PM data"""
import sqlite3

conn = sqlite3.connect('data/nba_data.db')
cursor = conn.cursor()

# Check if player_game_logs has 3PM data
cursor.execute("PRAGMA table_info(player_game_logs)")
cols = [c[1] for c in cursor.fetchall()]
print("player_game_logs columns:", cols)

# Check for 3PM data
if 'fg3m' in cols:
    cursor.execute("SELECT player_id, fg3m FROM player_game_logs WHERE fg3m IS NOT NULL LIMIT 5")
    rows = cursor.fetchall()
    print("\nSample fg3m data:", rows)
    
    # Check Victor Wembanyama's 3PM
    cursor.execute("SELECT player_id, player_name FROM player_bio WHERE player_name LIKE '%Wemb%'")
    player = cursor.fetchone()
    if player:
        player_id = player[0]
        cursor.execute("SELECT AVG(fg3m) FROM player_game_logs WHERE player_id = ? AND fg3m IS NOT NULL", (player_id,))
        avg = cursor.fetchone()[0]
        print(f"\nWembanyama ({player_id}) avg 3PM: {avg}")
else:
    print("fg3m column not found")
