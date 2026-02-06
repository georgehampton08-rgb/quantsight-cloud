"""
Game Log Data Structure Visualization
=====================================
Shows exactly what data is saved for each player
"""
import sqlite3

conn = sqlite3.connect('data/nba_data.db')
c = conn.cursor()

print("\n" + "="*100)
print(" WHAT'S SAVED IN THE DATABASE")
print("="*100)

print("\n📊 TABLE 1: game_logs (Individual Game Performance)")
print("-" * 100)
print("Stores EVERY game a player has played with detailed stats\n")

# Example: LaMelo Ball's recent games
c.execute("""
    SELECT game_date, matchup, wl, CAST(min AS INTEGER) as minutes, 
           pts, reb, ast, stl, blk, tov, 
           ROUND(fg_pct*100, 1) as fg_pct, 
           ROUND(fg3_pct*100, 1) as fg3_pct,
           ROUND(ft_pct*100, 1) as ft_pct
    FROM game_logs 
    WHERE player_id = '203991' 
    ORDER BY game_date DESC 
    LIMIT 3
""")

print("Example: LaMelo Ball - Last 3 Games\n")
for i, row in enumerate(c.fetchall(), 1):
    print(f"Game {i}: {row[0]}")
    print(f"  • Matchup: {row[1]} ({row[2]})")
    print(f"  • Minutes: {row[3]}")
    print(f"  • Points: {row[4]} | Rebounds: {row[5]} | Assists: {row[6]}")
    print(f"  • Steals: {row[7]} | Blocks: {row[8]} | Turnovers: {row[9]}")
    print(f"  • Shooting: {row[10]}% FG | {row[11]}% 3PT | {row[12]}% FT")
    print()

print("\n" + "="*100)
print("\n📈 TABLE 2: player_rolling_averages (Season Summary)")
print("-" * 100)
print("Stores calculated season averages for each player\n")

c.execute("""
    SELECT player_name, avg_points, avg_rebounds, avg_assists, games_count
    FROM player_rolling_averages 
    WHERE player_id = '203991'
""")

row = c.fetchone()
if row:
    print(f"Player: {row[0]}")
    print(f"  • PPG: {row[1]}")
    print(f"  • RPG: {row[2]}")
    print(f"  • APG: {row[3]}")
    print(f"  • Games: {row[4]}\n")

print("="*100)
print("\n📦 DATABASE CONTENTS")
print("-" * 100)

c.execute("SELECT COUNT(*) FROM game_logs")
total_games = c.fetchone()[0]

c.execute("SELECT COUNT(DISTINCT player_id) FROM game_logs")
total_players_with_logs = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM player_rolling_averages")
total_players = c.fetchone()[0]

print(f"\nTotal game logs stored: {total_games:,}")
print(f"Total unique players: {total_players}")
print(f"Average games per player: {total_games // total_players_with_logs if total_players_with_logs > 0 else 0}")

# Show top 5 scorers
print("\n" + "="*100)
print("\n🏆 TOP 5 SCORERS (Currently in Database)")
print("-" * 100)

c.execute("""
    SELECT player_name, avg_points, avg_rebounds, avg_assists, games_count
    FROM player_rolling_averages 
    ORDER BY avg_points DESC 
    LIMIT 5
""")

for i, row in enumerate(c.fetchall(), 1):
    print(f"{i}. {row[0]:25s} | {row[1]:5.1f} PPG | {row[2]:4.1f} RPG | {row[3]:4.1f} APG | {row[4]} games")

conn.close()
print("\n" + "="*100 + "\n")
