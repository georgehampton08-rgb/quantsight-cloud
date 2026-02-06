import sqlite3
conn = sqlite3.connect('data/nba_data.db')
cur = conn.cursor()

# Check DeMar DeRozan
cur.execute("SELECT player_id, name FROM players WHERE name LIKE '%DeRozan%'")
player = cur.fetchone()
print(f"Player: {player}")

if player:
    pid = player[0]
    cur.execute("SELECT COUNT(*) FROM player_game_logs WHERE player_id = ?", (str(pid),))
    count = cur.fetchone()[0]
    print(f"Game logs for {pid}: {count}")
    
    if count > 0:
        cur.execute("SELECT game_date, points FROM player_game_logs WHERE player_id = ? ORDER BY game_date DESC LIMIT 3", (str(pid),))
        for row in cur.fetchall():
            print(f"  {row}")

# How many players in today's game have logs?
cur.execute("SELECT player_id, name FROM players WHERE team_id IN ('PHI', 'SAC')")
players = cur.fetchall()
with_logs = 0
for pid, name in players:
    cur.execute("SELECT COUNT(*) FROM player_game_logs WHERE player_id = ?", (str(pid),))
    if cur.fetchone()[0] > 0:
        with_logs += 1
        
print(f"\nPlayers in PHI/SAC with game logs: {with_logs} / {len(players)}")

conn.close()
