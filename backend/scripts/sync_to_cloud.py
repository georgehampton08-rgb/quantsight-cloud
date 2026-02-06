"""
Complete Local-to-Cloud Data Sync - FIXED
Maps local SQLite columns to Cloud SQL schema correctly
"""
import sqlite3
import requests
import json
import time

LOCAL_DB = r'C:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\data\nba_data.db'
CLOUD_API = "https://quantsight-cloud-458498663186.us-central1.run.app"

def get_local_players():
    """Get all players from local SQLite with correct column mapping"""
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get column info first
    cursor.execute("PRAGMA table_info(players)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Local player columns: {columns}")
    
    # Get all players
    cursor.execute("SELECT * FROM players")
    rows = cursor.fetchall()
    
    players = []
    for row in rows:
        row_dict = dict(row)
        
        # Map local columns to Cloud SQL schema
        # Local: player_id, name, team, position, headshot_url, avatar
        # Cloud: player_id, full_name, team_id, team_abbreviation
        players.append({
            'player_id': row_dict.get('player_id') or row_dict.get('id'),
            'full_name': row_dict.get('name') or row_dict.get('full_name', 'Unknown'),
            'team_id': row_dict.get('team_id', 0),
            'team_abbreviation': row_dict.get('team') or row_dict.get('team_abbreviation', 'FA')
        })
    
    conn.close()
    print(f"Loaded {len(players)} players")
    if players:
        print(f"Sample: {players[0]}")
    return players

def upload_players(players):
    """Upload players in batches"""
    print(f"\nUploading {len(players)} players...")
    
    batch_size = 50
    total_uploaded = 0
    
    for i in range(0, len(players), batch_size):
        batch = players[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{CLOUD_API}/admin/bulk-seed-players",
                json={'players': batch},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                total_uploaded += result.get('total', len(batch))
                print(f"  Batch {i//batch_size + 1}: OK ({result.get('total', len(batch))} players)")
            else:
                print(f"  Batch {i//batch_size + 1}: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"  Batch {i//batch_size + 1}: Error - {e}")
        
        time.sleep(0.3)
    
    return total_uploaded

def check_status():
    """Check Cloud SQL status"""
    try:
        r = requests.get(f"{CLOUD_API}/admin/db-status", timeout=15)
        if r.status_code == 200:
            data = r.json()
            counts = data.get('table_counts', {})
            print(f"Cloud SQL: players={counts.get('players', 0)}, teams={counts.get('teams', 0)}")
            return counts
    except Exception as e:
        print(f"Status error: {e}")
    return {}

def main():
    print("=" * 50)
    print(" LOCAL TO CLOUD PLAYER SYNC")
    print("=" * 50)
    
    # Check before
    print("\nBefore sync:")
    check_status()
    
    # Get and upload players
    players = get_local_players()
    if players:
        uploaded = upload_players(players)
        print(f"\nUploaded: {uploaded}")
    
    # Check after
    print("\nAfter sync:")
    check_status()

if __name__ == "__main__":
    main()
