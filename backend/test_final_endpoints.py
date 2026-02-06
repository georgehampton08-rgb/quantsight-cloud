"""
Final Comprehensive Endpoint Test with Schedule
Tests all endpoints including the new schedule endpoint
"""
import requests
import json

BASE = "https://quantsight-cloud-458498663186.us-central1.run.app"

print("=" * 70)
print(" FINAL COMPREHENSIVE ENDPOINT TEST")
print("=" * 70)

tests = []

# 1. Health
print("\n✓ Testing /health...")
try:
    r = requests.get(f"{BASE}/health", timeout=10)
    tests.append(("Health", "✅ PASS" if r.status_code == 200 else f"❌ FAIL"))
except Exception as e:
    tests.append(("Health", f"❌ ERROR"))

# 2. DB Status
print("✓ Testing /admin/db-status...")
try:
    r = requests.get(f"{BASE}/admin/db-status", timeout=10)
    tests.append(("DB Status", "✅ PASS" if r.status_code == 200 else f"❌ FAIL"))
    if r.status_code == 200:
        counts = r.json().get('table_counts', {})
        print(f"  Players: {counts.get('players')} | Teams: {counts.get('teams')}")
except Exception as e:
    tests.append(("DB Status", f"❌ ERROR"))

# 3. Teams
print("✓ Testing /teams...")
try:
    r = requests.get(f"{BASE}/teams", timeout=10)
    tests.append(("Teams", "✅ PASS" if r.status_code == 200 else f"❌ FAIL"))
    if r.status_code == 200:
        teams = r.json()
        print(f"  Got {len(teams)} teams")
except Exception as e:
    tests.append(("Teams", f"❌ ERROR"))

# 4. Roster
print("✓ Testing /roster/1610612747 (Lakers)...")
try:
    r = requests.get(f"{BASE}/roster/1610612747", timeout=10)
    tests.append(("Roster", "✅ PASS" if r.status_code == 200 else f"❌ FAIL"))
except Exception as e:
    tests.append(("Roster", f"❌ ERROR"))

# 5. Player Search
print("✓ Testing /players/search...")
try:
    r = requests.get(f"{BASE}/players/search?q=James", timeout=10)
    tests.append(("Player Search", "✅ PASS" if r.status_code == 200 else f"❌ FAIL"))
except Exception as e:
    tests.append(("Player Search", f"❌ ERROR"))

# 6. SCHEDULE (NEW!)
print("✓ Testing /schedule...")
try:
    r = requests.get(f"{BASE}/schedule", timeout=15)
    tests.append(("Schedule", "✅ PASS" if r.status_code == 200 else f"❌ FAIL"))
    if r.status_code == 200:
        data = r.json()
        print(f"  Date: {data.get('date')}")
        print(f"  Total Games: {data.get('total_games')}")
        
        # Show today's games
        for game in data.get('games', [])[:4]:
            away = game['away_team']['tricode']
            home = game['home_team']['tricode']
            status = game['status_text']
            print(f"  - {away} @ {home}: {status}")
except Exception as e:
    tests.append(("Schedule", f"❌ ERROR: {e}"))

# 7. Injuries
print("✓ Testing /injuries...")
try:
    r = requests.get(f"{BASE}/injuries", timeout=10)
    tests.append(("Injuries", "✅ PASS" if r.status_code == 200 else f"❌ FAIL"))
except Exception as e:
    tests.append(("Injuries", f"❌ ERROR"))

# Summary
print("\n" + "=" * 70)
print(" TEST SUMMARY")
print("=" * 70)
for name, result in tests:
    print(f"{name:20} {result}")

passed = sum(1 for _, r in tests if "PASS" in r)
print(f"\n✅ PASSED: {passed}/{len(tests)}")

if passed == len(tests):
    print("\n🎉 ALL ENDPOINTS WORKING!")
else:
    print(f"\n⚠️  {len(tests) - passed} endpoint(s) need attention")
