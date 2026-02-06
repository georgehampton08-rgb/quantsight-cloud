"""
Merge game_logs table into player_game_logs and drop the smaller table.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "nba_data.db"

def main():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Check current counts
    cursor.execute("SELECT COUNT(*) FROM player_game_logs")
    pgl_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM game_logs")
    gl_count = cursor.fetchone()[0]
    
    print(f"Before merge:")
    print(f"  player_game_logs: {pgl_count} rows")
    print(f"  game_logs: {gl_count} rows")
    
    # Check schema of both tables
    cursor.execute("PRAGMA table_info(player_game_logs)")
    pgl_cols = [row[1] for row in cursor.fetchall()]
    
    cursor.execute("PRAGMA table_info(game_logs)")
    gl_cols = [row[1] for row in cursor.fetchall()]
    
    print(f"\nplayer_game_logs columns: {pgl_cols}")
    print(f"game_logs columns: {gl_cols}")
    
    # Insert data from game_logs into player_game_logs (avoid duplicates by player_id + game_id)
    # Map columns appropriately
    cursor.execute("""
        INSERT OR IGNORE INTO player_game_logs 
        (player_id, game_id, game_date, opponent, points, rebounds, assists, 
         steals, blocks, turnovers, fg_made, fg_attempted, fg3_made, fg3_attempted,
         ft_made, ft_attempted, plus_minus)
        SELECT 
            player_id, game_id, game_date, opponent, 
            pts, reb, ast, stl, blk, tov, 
            fgm, fga, fg3m, fg3a, ftm, fta, plus_minus
        FROM game_logs
        WHERE NOT EXISTS (
            SELECT 1 FROM player_game_logs p 
            WHERE p.player_id = game_logs.player_id 
            AND p.game_id = game_logs.game_id
        )
    """)
    
    merged = cursor.rowcount
    print(f"\nMerged {merged} unique rows from game_logs into player_game_logs")
    
    # Drop the old table
    cursor.execute("DROP TABLE game_logs")
    print("Dropped game_logs table")
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM player_game_logs")
    final_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT player_id) FROM player_game_logs")
    unique_players = cursor.fetchone()[0]
    
    print(f"\nAfter merge:")
    print(f"  player_game_logs: {final_count} rows, {unique_players} unique players")
    
    conn.close()
    print("\n✅ Table consolidation complete!")


if __name__ == "__main__":
    main()
