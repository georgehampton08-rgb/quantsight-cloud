import requests
import json

BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

print("=" * 80)
print("QUANTSIGHT ENDPOINT VERIFICATION")
print("=" * 80)

# Test 1: Teams endpoint
print("\n1. Testing /teams/LAL...")
try:
    resp = requests.get(f"{BASE_URL}/teams/LAL", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Team: {data.get('name', 'N/A')}")
    else:
        print(f"   ✗ Error: {resp.text[:200]}")
except Exception as e:
    print(f"   ✗ Exception: {e}")

# Test 2: Players endpoint
print("\n2. Testing /players/2544 (LeBron)...")
try:
    resp = requests.get(f"{BASE_URL}/players/2544", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Player: {data.get('name', 'N/A')}")
        print(f"   ✓ PPG: {data.get('stats', {}).get('ppg', 0)}")
    else:
        print(f"   ✗ Error: {resp.text[:200]}")
except Exception as e:
    print(f"   ✗ Exception: {e}")

# Test 3: Schedule
print("\n3. Testing /schedule...")
try:
    resp = requests.get(f"{BASE_URL}/schedule", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Date: {data.get('date', 'N/A')}")
        print(f"   ✓ Games: {data.get('total_games', 0)}")
    else:
        print(f"   ✗ Error: {resp.text[:200]}")
except Exception as e:
    print(f"   ✗ Exception: {e}")

# Test 4: Schedule with team filter
print("\n4. Testing /schedule?team=LAL...")
try:
    resp = requests.get(f"{BASE_URL}/schedule?team=LAL", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Filtered games: {data.get('total_games', 0)}")
    else:
        print(f"   ✗ Error: {resp.text[:200]}")
except Exception as e:
    print(f"   ✗ Exception: {e}")

# Test 5: Matchup analyze
print("\n5. Testing /matchup/analyze?home_team=LAL&away_team=GSW...")
try:
    resp = requests.get(f"{BASE_URL}/matchup/analyze?home_team=LAL&away_team=GSW", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✓ Matchup: {data.get('matchup', {}).get('home_team', {}).get('name  ', 'N/A')} vs {data.get('matchup', {}).get('away_team', {}).get('name', 'N/A')}")
        print(f"   ✓ Home win %: {data.get('prediction', {}).get('home_win_probability', 0) * 100}%")
    else:
        print(f"   ✗ Error: {resp.text[:200]}")
except Exception as e:
    print(f"   ✗ Exception: {e}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
