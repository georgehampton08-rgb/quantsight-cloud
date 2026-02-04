"""
Import curated NBA stats from CSV to database
"""
import csv
import sqlite3
from pathlib import Path
from datetime import datetime

def import_stats():
    script_dir = Path(__file__).parent
    csv_path = script_dir / 'data' / 'nba_player_stats_2024_25.csv'
    db_path = script_dir / 'data' / 'nba_data.db'
    
    print(f"📁 CSV: {csv_path}")
    print(f"📁 Database: {db_path}")
    
    if not csv_path.exists():
        print("❌ CSV file not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Read CSV
    updated = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            player_id = row['player_id']
            name = row['name']
            
            # Update players table
            cursor.execute("""
                INSERT OR REPLACE INTO players 
                (player_id, name, team_id, position, status)
                VALUES (?, ?, ?, ?, 'active')
            """, (
                player_id,
                name,
                row['team'],
                row['position']
            ))
            
            # Update player_stats table
            cursor.execute("""
                INSERT OR REPLACE INTO player_stats 
                (player_id, season, games, points_avg, rebounds_avg, assists_avg, 
                 fg_pct, three_p_pct, ft_pct)
                VALUES (?, '2024-25', ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_id,
                int(row['games']),
                float(row['points_avg']),
                float(row['rebounds_avg']),
                float(row['assists_avg']),
                float(row['fg_pct']),
                float(row['fg3_pct']),
                float(row['ft_pct'])
            ))
            
            print(f"  ✅ {name}: {row['points_avg']} PPG, {row['rebounds_avg']} RPG, {row['assists_avg']} APG")
            updated += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Updated {updated} players in database")
    return updated


if __name__ == '__main__':
    import_stats()
