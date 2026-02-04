"""
Diagnostic script to check player lab issue
"""
import requests
import json

print("=" * 70)
print("PLAYER LAB DIAGNOSTIC")
print("=" * 70)

# 1. Check if player search works
print("\n1. Testing player search endpoint...")
try:
    r = requests.get('http://localhost:5000/players/search?q=lebron', timeout=10)
    print(f"   Status: {r.status_code}")
    if r.ok:
        players = r.json()
        print(f"   Players found: {len(players)}")
        if players:
            print(f"   First player: {players[0]['name']} (ID: {players[0]['id']})")
    else:
        print(f"   Error: {r.text[:100]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# 2. Check if empty search returns all players
print("\n2. Testing empty search (should return all players)...")
try:
    r = requests.get('http://localhost:5000/players/search?q=', timeout=10)
    print(f"   Status: {r.status_code}")
    if r.ok:
        players = r.json()
        print(f"   Total players: {len(players)}")
        print(f"   Sample: {[p['name'] for p in players[:5]]}")
    else:
        print(f"   Error: {r.text[:100]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# 3. Check player profile endpoint
print("\n3. Testing player profile endpoint (LeBron James)...")
try:
    r = requests.get('http://localhost:5000/players/2544', timeout=10)
    print(f"   Status: {r.status_code}")
    if r.ok:
        profile = r.json()
        print(f"   Player: {profile.get('name', 'Unknown')}")
        print(f"   Team: {profile.get('team', 'Unknown')}")
    else:
        print(f"   Error: {r.text[:100]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# 4. Check teams endpoint
print("\n4. Testing teams endpoint...")
try:
    r = requests.get('http://localhost:5000/teams', timeout=10)
    print(f"   Status: {r.status_code}")
    if r.ok:
        data = r.json()
        teams = data.get('teams', [])
        print(f"   Teams found: {len(teams)}")
        if teams:
            print(f"   Sample: {teams[0]['name']} ({teams[0]['abbreviation']})")
    else:
        print(f"   Error: {r.text[:100]}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

# 5. Check frontend
print("\n5. Testing frontend...")
try:
    r = requests.get('http://localhost:5173', timeout=10)
    print(f"   Status: {r.status_code}")
    print(f"   Frontend: {'✅ Running' if r.ok else '❌ Not running'}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)
