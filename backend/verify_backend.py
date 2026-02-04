"""
Comprehensive backend verification
"""
import requests
import json

BASE = "http://localhost:5000"

def test(name, url, check_fn=None):
    print(f"\n{'='*50}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print('='*50)
    try:
        r = requests.get(url, timeout=30)
        print(f"Status: {r.status_code}")
        if r.ok:
            data = r.json()
            if check_fn:
                check_fn(data)
            else:
                print(f"Response: {json.dumps(data, indent=2)[:500]}...")
            return True
        else:
            print(f"Error: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"Failed: {e}")
        return False

def main():
    results = {}
    
    # 1. Schedule
    results['schedule'] = test(
        "Schedule (Today's Games)",
        f"{BASE}/schedule",
        lambda d: print(f"  Games: {len(d.get('games', []))}\n  First: {d.get('games', [{}])[0]}")
    )
    
    # 2. Players Search
    results['players_search'] = test(
        "Player Search",
        f"{BASE}/players/search?q=LeBron",
        lambda d: print(f"  Found: {len(d)} players\n  First: {d[0].get('name') if d else 'None'}")
    )
    
    # 3. Team Roster
    results['roster'] = test(
        "Team Roster (LAL)",
        f"{BASE}/roster/LAL",
        lambda d: print(f"  Players: {len(d)}\n  First: {d[0].get('name') if d else 'None'}")
    )
    
    # 4. Aegis Simulation
    results['simulation'] = test(
        "Aegis Simulation (Bam Adebayo)",
        f"{BASE}/aegis/simulate/1628389?opponent_id=1610612741",
        lambda d: print(f"  PTS: {d.get('projections',{}).get('expected_value',{}).get('points', 'N/A')}\n  REB: {d.get('projections',{}).get('expected_value',{}).get('rebounds', 'N/A')}")
    )
    
    # 5. Matchup Lab
    results['matchup'] = test(
        "Matchup Lab Games",
        f"{BASE}/matchup-lab/games",
        lambda d: print(f"  Games: {len(d) if isinstance(d, list) else d.get('count', 'N/A')}")
    )
    
    # 6. Injuries
    results['injuries'] = test(
        "Current Injuries",
        f"{BASE}/injuries/current",
        lambda d: print(f"  Injuries: {len(d) if isinstance(d, list) else 'N/A'}")
    )
    
    # Summary
    print("\n" + "="*50)
    print("VERIFICATION SUMMARY")
    print("="*50)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n✅ Passed: {passed}/{total}")
    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    return passed == total

if __name__ == "__main__":
    main()
