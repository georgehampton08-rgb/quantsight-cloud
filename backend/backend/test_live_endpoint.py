"""Final verification - check live endpoint returns both teams"""
import requests
import json

try:
    # Test the actual HTTP endpoint
    url = "http://localhost:5000/matchup/analyze"
    params = {
        "game_id": "0022500688",
        "home_team": "BOS",
        "away_team": "MIA"
    }
    
    print(f"Testing: {url}")
    print(f"Params: {params}\n")
    
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    
    # Count teams
    teams = {}
    for p in data.get('projections', []):
        team = p.get('team', 'UNKNOWN')
        teams[team] = teams.get(team, 0) + 1
        
    print(f"Status: {response.status_code}")
    print(f"Total Players: {len(data.get('projections', []))}")
    print(f"Team Breakdown: {json.dumps(teams, indent=2)}")
    
    # Show sample from each team
    print("\nSample BOS Players:")
    bos_players = [p for p in data['projections'] if p.get('team') == 'BOS'][:3]
    for p in bos_players:
        print(f"  - {p['player_name']}: {p.get('classification', '?')}")
    
    print("\nSample MIA Players:")
    mia_players = [p for p in data['projections'] if p.get('team') == 'MIA'][:3]
    for p in mia_players:
        print(f"  - {p['player_name']}: {p.get('classification', '?')}")
        
    if len(teams) == 2 and len(data['projections']) >= 18:
        print("\n✅ PASS: Both teams returned correctly!")
    else:
        print(f"\n❌ FAIL: Expected 2 teams with ~20 players, got {len(teams)} teams with {len(data['projections'])} players")
        
except Exception as e:
    print(f"❌ Error: {e}")
