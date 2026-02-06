"""Check player bio teams"""
import sqlite3

conn = sqlite3.connect('data/nba_data.db')
cursor = conn.cursor()

# Check what teams are in player_bio
cursor.execute("SELECT DISTINCT team FROM player_bio LIMIT 30")
teams = cursor.fetchall()
print("Teams in player_bio:")
print([t[0] for t in teams])

# Check SAS/CHA specifically
cursor.execute("SELECT COUNT(*) FROM player_bio WHERE team = 'SAS'")
sas_count = cursor.fetchone()[0]
print(f"\nSAS players: {sas_count}")

cursor.execute("SELECT COUNT(*) FROM player_bio WHERE team = 'CHA'")
cha_count = cursor.fetchone()[0]
print(f"CHA players: {cha_count}")

# Check what player_rolling_averages has for these players
cursor.execute("""
    SELECT pra.player_name, pra.avg_points, pb.team 
    FROM player_rolling_averages pra 
    JOIN player_bio pb ON pra.player_id = pb.player_id 
    WHERE pb.team IN ('SAS', 'CHA')
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"  {row}")
