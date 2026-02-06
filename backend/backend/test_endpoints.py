import requests
import json

# Test schedule
print("Testing /schedule endpoint...")
try:
    r = requests.get("http://localhost:5000/schedule", timeout=30)
    if r.ok:
        data = r.json()
        games = data.get('games', [])
        print(f"  Games found: {len(games)}")
        for g in games[:3]:
            print(f"    {g.get('away_team')} @ {g.get('home_team')}")
    else:
        print(f"  Error: {r.status_code}")
except Exception as e:
    print(f"  Failed: {e}")

# Test players
print("\nTesting /players endpoint...")
try:
    r = requests.get("http://localhost:5000/players?limit=5", timeout=30)
    if r.ok:
        data = r.json()
        players = data if isinstance(data, list) else data.get('players', [])
        print(f"  Players found: {len(players)}")
        for p in players[:3]:
            print(f"    {p.get('name', 'Unknown')}")
    else:
        print(f"  Error: {r.status_code}")
except Exception as e:
    print(f"  Failed: {e}")

# Test simulation
print("\nTesting /aegis/simulate endpoint...")
try:
    r = requests.get("http://localhost:5000/aegis/simulate/1628389?opponent_id=1610612741", timeout=30)
    if r.ok:
        data = r.json()
        proj = data.get('projections', {})
        ev = proj.get('expected_value', {})
        print(f"  PTS: {ev.get('points', 'N/A')}")
        print(f"  REB: {ev.get('rebounds', 'N/A')}")
    else:
        print(f"  Error: {r.status_code}")
except Exception as e:
    print(f"  Failed: {e}")

print("\nDone!")
