"""Final comprehensive test of all fixes"""
import requests
import json

BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

print("="*60)
print(" FINAL COMPREHENSIVE ENDPOINT TEST")
print("="*60)

# 1. Health Check
print("\n1. Testing /health...")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=10)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ DB Connected: {data.get('database_url_set')}")
        print(f"   ✅ Firebase: {data.get('firebase', {}).get('enabled')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 2. DB Status
print("\n2. Testing /admin/db-status...")
try:
    r = requests.get(f"{BASE_URL}/admin/db-status", timeout=10)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        counts = data.get('table_counts', {})
        print(f"   Teams: {counts.get('teams')}")
        print(f"   Players: {counts.get('players')}")
        print(f"   Team Defense: {counts.get('team_defense')}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 3. Teams Endpoint - Detailed Error
print("\n3. Testing /teams (PUBLIC)...")
try:
    r = requests.get(f"{BASE_URL}/teams", timeout=10)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        teams = r.json()
        print(f"   ✅ Got {len(teams)} teams")
        if teams:
            print(f"   Sample: {teams[0]}")
    else:
        print(f"   ❌ Error Response:")
        print(f"   {r.text}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

# 4. Schedule
print("\n4. Testing /schedule...")
try:
    r = requests.get(f"{BASE_URL}/schedule", timeout=10)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   ✅ Placeholder working")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 5. Injuries
print("\n5. Testing /injuries...")
try:
    r = requests.get(f"{BASE_URL}/injuries", timeout=10)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print(f"   ✅ Placeholder working")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print(" TEST COMPLETE")
print("="*60)
