import requests
import json

print("Testing Matchup Lab API...")
print("=" * 60)

try:
    r = requests.get(
        'http://localhost:5000/aegis/matchup',
        params={'home_team_id': '1610612747', 'away_team_id': '1610612764'},
        timeout=30
    )
    
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        
        print(f"\n✅ SUCCESS!")
        print(f"\nHome Team: {data.get('home_team', {}).get('team_name', 'N/A')}")
        print(f"Home Players: {len(data.get('home_team', {}).get('players', []))}")
        
        print(f"\nAway Team: {data.get('away_team', {}).get('team_name', 'N/A')}")
        print(f"Away Players: {len(data.get('away_team', {}).get('players', []))}")
        
        # Show first 3 players from each team
        home_players = data.get('home_team', {}).get('players', [])
        if home_players:
            print(f"\nFirst 3 Home Players:")
            for p in home_players[:3]:
                print(f"  • {p.get('player_name', 'N/A'):20s} - Grade: {p.get('efficiency_grade', 'N/A'):3s} - EV: {p.get('ev_points', 0):.1f} pts")
        
        away_players = data.get('away_team', {}).get('players', [])
        if away_players:
            print(f"\nFirst 3 Away Players:")
            for p in away_players[:3]:
                print(f"  • {p.get('player_name', 'N/A'):20s} - Grade: {p.get('efficiency_grade', 'N/A'):3s} - EV: {p.get('ev_points', 0):.1f} pts")
    else:
        print(f"\n❌ ERROR: {r.status_code}")
        print(r.text[:500])
        
except Exception as e:
    print(f"\n❌ EXCEPTION: {e}")
