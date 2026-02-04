"""
Sync 3PM Data to Game Logs
==========================
Updates player_game_logs with fg3_made data from game log records.
"""
import sqlite3
from pathlib import Path
from nba_api.stats.endpoints import playergamelog
import time

DB_PATH = Path(__file__).parent / 'data' / 'nba_data.db'

def get_players_missing_3pm():
    """Get players who have game logs but missing fg3_made data"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT player_id, player_name 
        FROM player_game_logs 
        WHERE fg3_made IS NULL
    """)
    players = cursor.fetchall()
    conn.close()
    return players

def update_game_logs_with_3pm(player_id: str):
    """Fetch game logs with 3PM data and update existing records"""
    try:
        print(f"  Fetching game logs for player {player_id}...")
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season='2024-25'
        )
        df = gamelog.get_data_frames()[0]
        
        if df.empty:
            print(f"  No game logs found")
            return 0
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        updated = 0
        
        for _, row in df.iterrows():
            game_id = row.get('Game_ID', '')
            fg3m = row.get('FG3M', 0) or 0
            fg3a = row.get('FG3A', 0) or 0
            fg3_pct = row.get('FG3_PCT', 0) or 0
            
            # Update existing game log record
            cursor.execute("""
                UPDATE player_game_logs 
                SET fg3_made = ?, fg3_attempted = ?, fg3_pct = ?
                WHERE player_id = ? AND game_id = ?
            """, (fg3m, fg3a, fg3_pct, str(player_id), game_id))
            
            if cursor.rowcount > 0:
                updated += 1
        
        conn.commit()
        conn.close()
        print(f"  Updated {updated} game logs with 3PM data")
        return updated
        
    except Exception as e:
        print(f"  Error: {e}")
        return 0

def main():
    print("=" * 60)
    print("3PM Data Sync")
    print("=" * 60)
    
    players = get_players_missing_3pm()
    print(f"\nFound {len(players)} players with missing 3PM data")
    
    total_updated = 0
    for player_id, player_name in players:
        print(f"\n{player_name} ({player_id})")
        updated = update_game_logs_with_3pm(player_id)
        total_updated += updated
        time.sleep(0.6)  # Rate limiting
    
    print(f"\n{'=' * 60}")
    print(f"Total records updated: {total_updated}")
    print("=" * 60)

if __name__ == "__main__":
    main()
