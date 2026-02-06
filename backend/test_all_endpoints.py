"""
Comprehensive Endpoint Test Suite
Tests all QuantSight Cloud API endpoints
"""
import requests

BASE = "https://quantsight-cloud-458498663186.us-central1.run.app"

def test_endpoints():
    print("=" * 60)
    print(" COMPREHENSIVE ENDPOINT TEST")
    print("=" * 60)
    
    tests = []
    
    # 1. Health Check
    print("\n1. Testing /health...")
    try:
        r = requests.get(f"{BASE}/health", timeout=10)
        status = "✅ PASS" if r.status_code == 200 else f"❌ FAIL ({r.status_code})"
        tests.append(("Health", status))
        if r.status_code == 200:
            data = r.json()
            print(f"   DB: {data.get('database_url_set')}")
            print(f"   Firebase: {data.get('firebase', {}).get('enabled')}")
    except Exception as e:
        tests.append(("Health", f"❌ ERROR: {e}"))
    
    # 2. DB Status
    print("\n2. Testing /admin/db-status...")
    try:
        r = requests.get(f"{BASE}/admin/db-status", timeout=10)
        status = "✅ PASS" if r.status_code == 200 else f"❌ FAIL ({r.status_code})"
        tests.append(("DB Status", status))
        if r.status_code == 200:
            counts = r.json().get('table_counts', {})
            print(f"   Teams: {counts.get('teams')}")
            print(f"   Players: {counts.get('players')} ⭐")
            print(f"   Team Defense: {counts.get('team_defense')}")
    except Exception as e:
        tests.append(("DB Status", f"❌ ERROR: {e}"))
    
    # 3. Teams Endpoint
    print("\n3. Testing /teams...")
    try:
        r = requests.get(f"{BASE}/teams", timeout=10)
        status = "✅ PASS" if r.status_code == 200 else f"❌ FAIL ({r.status_code})"
        tests.append(("Teams", status))
        if r.status_code == 200:
            teams = r.json()
            print(f"   Got {len(teams)} teams")
            if teams:
                print(f"   Sample: {teams[0].get('name')} ({teams[0].get('abbreviation')})")
    except Exception as e:
        tests.append(("Teams", f"❌ ERROR: {e}"))
    
    # 4. Roster Endpoint (Lakers)
    print("\n4. Testing /roster/1610612747 (Lakers)...")
    try:
        r = requests.get(f"{BASE}/roster/1610612747", timeout=10)
        status = "✅ PASS" if r.status_code == 200 else f"❌ FAIL ({r.status_code})"
        tests.append(("Roster", status))
        if r.status_code == 200:
            roster = r.json()
            print(f"   Got {len(roster)} players")
            if roster:
                print(f"   Sample: {roster[0].get('name')}")
    except Exception as e:
        tests.append(("Roster", f"❌ ERROR: {e}"))
    
    # 5. Player Search
    print("\n5. Testing /players/search?q=LeBron...")
    try:
        r = requests.get(f"{BASE}/players/search?q=LeBron", timeout=10)
        status = "✅ PASS" if r.status_code == 200 else f"❌ FAIL ({r.status_code})"
        tests.append(("Player Search", status))
        if r.status_code == 200:
            players = r.json()
            print(f"   Found {len(players)} players")
            if players:
                print(f"   Match: {players[0].get('name')} ({players[0].get('team')})")
    except Exception as e:
        tests.append(("Player Search", f"❌ ERROR: {e}"))
    
    # 6. Schedule
    print("\n6. Testing /schedule...")
    try:
        r = requests.get(f"{BASE}/schedule", timeout=10)
        status = "✅ PASS" if r.status_code == 200 else f"❌ FAIL ({r.status_code})"
        tests.append(("Schedule", status))
        if r.status_code == 200:
            print(f"   {r.json().get('message')}")
    except Exception as e:
        tests.append(("Schedule", f"❌ ERROR: {e}"))
    
    # 7. Injuries
    print("\n7. Testing /injuries...")
    try:
        r = requests.get(f"{BASE}/injuries", timeout=10)
        status = "✅ PASS" if r.status_code == 200 else f"❌ FAIL ({r.status_code})"
        tests.append(("Injuries", status))
        if r.status_code == 200:
            print(f"   {r.json().get('message')}")
    except Exception as e:
        tests.append(("Injuries", f"❌ ERROR: {e}"))
    
    # Summary
    print("\n" + "=" * 60)
    print(" TEST SUMMARY")
    print("=" * 60)
    for name, result in tests:
        print(f"{name:20} {result}")
    
    passed = sum(1 for _, r in tests if "PASS" in r)
    print(f"\nPassed: {passed}/{len(tests)}")

if __name__ == "__main__":
    test_endpoints()
