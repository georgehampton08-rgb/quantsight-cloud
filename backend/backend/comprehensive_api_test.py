"""
Comprehensive API Test Suite - ALL 10 TESTS
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_endpoint(name, url, timeout=60):
    """Test an endpoint"""
    print(f"\n[TEST] {name}")
    print(f"       URL: {url}")
    
    try:
        start = time.time()
        r = requests.get(url, timeout=timeout)
        elapsed = (time.time() - start) * 1000
        
        if r.status_code == 200:
            data = r.json()
            size = len(data) if isinstance(data, list) else len(str(data))
            print(f"       [PASS] {r.status_code} OK ({elapsed:.0f}ms, {size} bytes)")
            return True, data
        else:
            print(f"       [FAIL] {r.status_code} - {r.text[:100]}")
            return False, None
            
    except Exception as e:
        print(f"       [FAIL] {e}")
        return False, None


def main():
    print("\n" + "="*60)
    print("  QUANTSIGHT API TEST SUITE - 10 TESTS")
    print("="*60)
    
    results = {}
    
    # Test 1
    ok, _ = test_endpoint("1. Health Check", f"{BASE_URL}/health")
    results["health"] = ok
    
    # Test 2
    ok, data = test_endpoint("2. Aegis Health", f"{BASE_URL}/aegis/health")
    results["aegis_health"] = ok
    if data:
        print(f"       Status: {data.get('status')} | Vertex: {data.get('vertex_engine')}")
    
    # Test 3  
    ok, data = test_endpoint("3. Schedule", f"{BASE_URL}/schedule")
    results["schedule"] = ok
    if data:
        games = data.get("games", [])
        print(f"       Games today: {len(games)}")
    
    # Test 4
    ok, data = test_endpoint("4. Teams List", f"{BASE_URL}/teams")
    results["teams"] = ok
    if data:
        print(f"       Teams: {len(data)}")
    
    # Test 5
    ok, data = test_endpoint("5. Roster (LAL)", f"{BASE_URL}/roster/LAL")
    results["roster"] = ok
    if data:
        print(f"       Players: {len(data)}")
    
    # Test 6
    ok, data = test_endpoint("6. Player Search", f"{BASE_URL}/players/search?q=LeBron")
    results["player_search"] = ok
    if data and len(data) > 0:
        print(f"       Found: {data[0].get('name')}")
    
    # Test 7
    ok, _ = test_endpoint("7. Team Defense", f"{BASE_URL}/data/team-defense/GSW")
    results["team_defense"] = ok
    
    # Test 8
    ok, data = test_endpoint("8. Matchup Lab", f"{BASE_URL}/aegis/matchup?home_team_id=1610612747&away_team_id=1610612764")
    results["matchup_lab"] = ok
    if data:
        home = data.get("home_team", {}).get("players", [])
        away = data.get("away_team", {}).get("players", [])
        print(f"       Home: {len(home)} players | Away: {len(away)} players")
        if home:
            print(f"       Top: {home[0].get('player_name')} - {home[0].get('efficiency_grade')}")
    
    # Test 9
    ok, data = test_endpoint("9. Radar Chart", f"{BASE_URL}/radar/2544")
    results["radar"] = ok
    if data:
        print(f"       Dimensions: {len(data.get('dimensions', []))}")
    
    # Test 10
    ok, data = test_endpoint("10. Player Data", f"{BASE_URL}/players/2544")
    results["player_data"] = ok
    if data:
        print(f"       Player: {data.get('name', 'N/A')}")
    
    # Summary
    print("\n" + "="*60)
    print("  RESULTS")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"   {name:20s}: {status}")
    
    print("-"*60)
    print(f"   TOTAL: {passed}/{total}")
    
    if passed == total:
        print("\n   ALL 10 TESTS PASSED!")
        return True
    else:
        print(f"\n   {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    main()
