import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "data" / "nba_data.db"
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check columns
cursor.execute("PRAGMA table_info(player_game_logs)")
cols = [row[1] for row in cursor.fetchall()]
print("Columns:", cols)

# Test LeBron query
cursor.execute("""
    SELECT player_id, game_date, points, rebounds, assists
    FROM player_game_logs 
    WHERE player_id = '2544'
    ORDER BY game_date DESC
    LIMIT 3
""")
rows = cursor.fetchall()
print(f"\nLeBron's last 3 games:")
for row in rows:
    print(f"  {dict(row)}")

# Test the actual router query
cursor.execute("""
    SELECT 
        player_id, game_id, game_date, opponent,
        points as pts, rebounds as reb, assists as ast,
        steals as stl, blocks as blk, turnovers as tov,
        fg_made as fgm, fg_attempted as fga,
        fg3_made as fg3m, fg3_attempted as fg3a,
        ft_made as ftm, ft_attempted as fta,
        minutes as min, plus_minus
    FROM player_game_logs 
    WHERE player_id = '2544'
    ORDER BY game_date DESC
    LIMIT 3
""")
rows = cursor.fetchall()
print(f"\nWith aliases:")
for row in rows:
    d = dict(row)
    print(f"  pts={d.get('pts')}, reb={d.get('reb')}, ast={d.get('ast')}")

conn.close()
