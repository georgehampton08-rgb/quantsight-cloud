import requests
import sqlite3
import random
import time
import sys

BASE_URL = "http://localhost:5000"

def stress_test():
    print("🚀 Starting Backend Stress Test...")
    
    # 1. Get all player IDs from DB directly
    try:
        conn = sqlite3.connect('backend/data/nba_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT player_id, name, team_id FROM players")
        all_players = cursor.fetchall()
        conn.close()
        print(f"✅ Loaded {len(all_players)} players from DB.")
    except Exception as e:
        print(f"❌ Failed to load players from DB: {e}")
        return

    failures = []
    
    # 2. Test random sample of 20 players
    sample_size = 20
    test_suite = random.sample(all_players, min(sample_size, len(all_players)))
    
    print(f"\n🧪 Testing {len(test_suite)} random players against endpoints...")
    
    for pid, name, tid in test_suite:
        print(f"  > Testing {name} ({pid})...", end="\r")
        
        # Test Profile
        try:
            r = requests.get(f"{BASE_URL}/player/{pid}")
            if r.status_code != 200:
                failures.append(f"Profile {pid} {name}: {r.status_code}")
        except:
            failures.append(f"Profile {pid} {name}: Connection Error")
            
        # Test Matchup
        try:
            r = requests.get(f"{BASE_URL}/matchup/analyze?player_id={pid}&opponent=GSW")
            if r.status_code != 200:
                failures.append(f"Matchup {pid} {name}: {r.status_code}")
        except:
             failures.append(f"Matchup {pid} {name}: Connection Error")

    print("\n")
    
    # 3. Test General Endpoints
    print("🧪 Testing General Endpoints...")
    endpoints = [
        "/teams",
        "/injuries",
        "/schedule",
        "/players/search?q=",  # Empty search
        "/players/search?q=lebron" # Specific search
    ]
    
    for ep in endpoints:
        print(f"  > Testing {ep}...", end="\r")
        try:
            r = requests.get(f"{BASE_URL}{ep}")
            if r.status_code != 200:
                failures.append(f"Endpoint {ep}: {r.status_code}")
        except:
            failures.append(f"Endpoint {ep}: Connection Error")
    print("\n")

    # 4. Report
    if failures:
        print(f"\n❌ FAILED {len(failures)} TESTS:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("\n✅ ALL TESTS PASSED! System is robust.")
        sys.exit(0)

if __name__ == "__main__":
    stress_test()
