"""
Populate Firestore with current active NBA players from 2024-25 rosters
Uses nba_api to fetch current team rosters
"""
import sys
sys.path.insert(0, 'backend')

from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import commonteamroster
from firestore_db import get_firestore_db
import time

print("🏀 Fetching active NBA rosters for 2024-25 season...")

db = get_firestore_db()

# Get all NBA teams
nba_teams = teams.get_teams()
print(f"Found {len(nba_teams)} NBA teams")

all_active_players = {}  # player_id -> player data
team_rosters = {}  # team_abbr -> list of player_ids

for team in nba_teams:
    team_id = team['id']
    team_abbr = team['abbreviation']
    team_name = team['full_name']
    
    print(f"\n📋 Fetching roster for {team_name} ({team_abbr})...")
    
    try:
        # Fetch current roster from NBA API
        roster = commonteamroster.CommonTeamRoster(
            team_id=team_id,
            season='2024-25'
        )
        
        roster_data = roster.get_data_frames()[0]
        
        team_rosters[team_abbr] = []
        
        for _, player_row in roster_data.iterrows():
            player_id = str(player_row['PLAYER_ID'])
            player_name = player_row['PLAYER']
            
            # Store active player data
            all_active_players[player_id] = {
                'player_id': player_id,
                'name': player_name,
                'team_abbreviation': team_abbr,
                'team_name': team_name,
                'is_active': True,
                'season': '2024-25',
                'jersey_number': player_row.get('NUM', ''),
                'position': player_row.get('POSITION', ''),
                'height': player_row.get('HEIGHT', ''),
                'weight': player_row.get('WEIGHT', ''),
                'age': player_row.get('AGE', 0)
            }
            
            team_rosters[team_abbr].append(player_id)
            print(f"  ✅ {player_name} (#{player_row.get('NUM', '?')})")
        
        print(f"  📊 {len(team_rosters[team_abbr])} players on {team_abbr} roster")
        
        # Rate limit to avoid API throttling
        time.sleep(0.6)
        
    except Exception as e:
        print(f"  ❌ Error fetching roster for {team_abbr}: {e}")
        continue

print(f"\n\n✅ Total active players found: {len(all_active_players)}")

# Update Firestore
print("\n🔄 Updating Firestore...")

batch = db.batch()
count = 0

for player_id, player_data in all_active_players.items():
    # Use player_id as document ID
    player_ref = db.collection('players').document(player_id)
    
    batch.set(player_ref, player_data, merge=True)
    count += 1
    
    # Commit every 500 (Firestore limit)
    if count >= 500:
        batch.commit()
        print(f"  ✅ Committed batch ({count} players)")
        batch = db.batch()
        count = 0

# Commit remaining
if count > 0:
    batch.commit()
    print(f"  ✅ Committed final batch ({count} players)")

print(f"\n🎉 Successfully updated {len(all_active_players)} active players in Firestore!")

# Print summary by team
print("\n📊 Summary by Team:")
for team_abbr, player_ids in sorted(team_rosters.items()):
    print(f"  {team_abbr}: {len(player_ids)} players")
