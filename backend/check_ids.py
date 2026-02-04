import sqlite3
conn = sqlite3.connect('data/nba_data.db')
cur = conn.cursor()

# Check Bam Adebayo
cur.execute("SELECT player_id, name FROM players WHERE name LIKE '%Adebayo%'")
print("Bam:", cur.fetchone())

# Check Coby White
cur.execute("SELECT player_id, name FROM players WHERE name LIKE '%Coby%'")  
print("Coby:", cur.fetchone())

# Check game logs for player 1628389
cur.execute("SELECT COUNT(*) FROM player_game_logs WHERE player_id = '1628389'")
print("Bam (1628389) game logs:", cur.fetchone()[0])

# Check game logs for player 1629632
cur.execute("SELECT COUNT(*) FROM player_game_logs WHERE player_id = '1629632'")
print("Coby (1629632) game logs:", cur.fetchone()[0])

# Check game logs for test IDs used in compare script
cur.execute("SELECT COUNT(*) FROM player_game_logs WHERE player_id = '201566'")
print("201566 game logs:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM player_game_logs WHERE player_id = '203897'")
print("203897 game logs:", cur.fetchone()[0])

conn.close()
