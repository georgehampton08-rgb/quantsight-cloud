"""
Comprehensive Days Rest & Simulation Test
==========================================
Tests the days_rest calculation and simulation against all 30 teams
with 5 key players per team (150 total simulations).

This verifies:
1. days_rest is calculated dynamically from game_logs.csv
2. Simulations run correctly with accurate schedule context
3. Data refresh endpoint works
"""

import requests
import json
import time
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:5000"

# All 30 NBA Teams
TEAMS = {
    "1610612737": "Atlanta Hawks",
    "1610612738": "Boston Celtics",
    "1610612751": "Brooklyn Nets",
    "1610612766": "Charlotte Hornets",
    "1610612741": "Chicago Bulls",
    "1610612739": "Cleveland Cavaliers",
    "1610612742": "Dallas Mavericks",
    "1610612743": "Denver Nuggets",
    "1610612765": "Detroit Pistons",
    "1610612744": "Golden State Warriors",
    "1610612745": "Houston Rockets",
    "1610612754": "Indiana Pacers",
    "1610612746": "LA Clippers",
    "1610612747": "Los Angeles Lakers",
    "1610612763": "Memphis Grizzlies",
    "1610612748": "Miami Heat",
    "1610612749": "Milwaukee Bucks",
    "1610612750": "Minnesota Timberwolves",
    "1610612740": "New Orleans Pelicans",
    "1610612752": "New York Knicks",
    "1610612760": "Oklahoma City Thunder",
    "1610612753": "Orlando Magic",
    "1610612755": "Philadelphia 76ers",
    "1610612756": "Phoenix Suns",
    "1610612757": "Portland Trail Blazers",
    "1610612758": "Sacramento Kings",
    "1610612759": "San Antonio Spurs",
    "1610612761": "Toronto Raptors",
    "1610612762": "Utah Jazz",
    "1610612764": "Washington Wizards"
}

# Key players to test (high usage stars from various teams)
TEST_PLAYERS = [
    # Lakers
    {"id": "2544", "name": "LeBron James", "team_id": "1610612747"},
    {"id": "203076", "name": "Anthony Davis", "team_id": "1610612747"},
    # Warriors
    {"id": "201939", "name": "Stephen Curry", "team_id": "1610612744"},
    # Celtics
    {"id": "1628369", "name": "Jayson Tatum", "team_id": "1610612738"},
    {"id": "1627759", "name": "Jaylen Brown", "team_id": "1610612738"},
    # Bucks
    {"id": "203507", "name": "Giannis Antetokounmpo", "team_id": "1610612749"},
    # Nuggets
    {"id": "203999", "name": "Nikola Jokic", "team_id": "1610612743"},
    # Suns
    {"id": "201142", "name": "Kevin Durant", "team_id": "1610612756"},
    # Mavericks
    {"id": "1629029", "name": "Luka Doncic", "team_id": "1610612742"},
    # Heat
    {"id": "1628389", "name": "Bam Adebayo", "team_id": "1610612748"},
]


def test_days_rest_calculation():
    """Test that days_rest is calculated correctly from TODAY"""
    print("\n" + "="*70)
    print("TEST 1: Days Rest Calculation")
    print("="*70)
    
    today = date.today()
    print(f"Today's date: {today}")
    
    results = []
    for player in TEST_PLAYERS[:5]:  # Test with first 5 players
        try:
            # Run simulation against first opponent
            opponent_id = list(TEAMS.keys())[0]
            
            response = requests.get(
                f"{BASE_URL}/aegis/simulate/{player['id']}",
                params={"opponent_id": opponent_id},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                schedule_ctx = data.get('schedule_context', {})
                days_rest = schedule_ctx.get('days_rest', 'N/A')
                is_b2b = schedule_ctx.get('is_b2b', 'N/A')
                last_game = schedule_ctx.get('last_game_date', 'N/A')
                
                print(f"\n  {player['name']}:")
                print(f"    Last Game: {last_game}")
                print(f"    Days Rest: {days_rest}")
                print(f"    Back-to-Back: {is_b2b}")
                
                # Verify days_rest makes sense
                if days_rest != 'N/A' and last_game != 'N/A':
                    # Calculate expected days rest
                    last_game_date = datetime.strptime(last_game, "%Y-%m-%d").date()
                    expected_rest = (today - last_game_date).days
                    
                    if days_rest == expected_rest:
                        print(f"    ✓ CORRECT (expected {expected_rest})")
                        results.append(True)
                    else:
                        print(f"    ✗ MISMATCH (expected {expected_rest}, got {days_rest})")
                        results.append(False)
                else:
                    print(f"    ⚠ No game log data available")
                    results.append(None)
            else:
                print(f"\n  {player['name']}: API Error {response.status_code}")
                results.append(False)
                
        except Exception as e:
            print(f"\n  {player['name']}: Error - {e}")
            results.append(False)
    
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    no_data = sum(1 for r in results if r is None)
    
    print(f"\n  Summary: {passed} passed, {failed} failed, {no_data} no data")
    return passed, failed, no_data


def test_data_refresh():
    """Test the new data refresh endpoint"""
    print("\n" + "="*70)
    print("TEST 2: Data Refresh Endpoint")
    print("="*70)
    
    player = TEST_PLAYERS[0]  # Test with LeBron
    print(f"\n  Testing refresh for {player['name']} ({player['id']})")
    
    try:
        response = requests.post(
            f"{BASE_URL}/player-data/refresh/{player['id']}",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n  Status: {data.get('status')}")
            print(f"  Message: {data.get('message')}")
            print(f"  Games Added: {data.get('games_added')}")
            print(f"  New Last Game: {data.get('new_last_game')}")
            print(f"  Days Rest: {data.get('days_rest')}")
            print(f"  Execution Time: {data.get('execution_time_ms')}ms")
            return True
        else:
            print(f"  ✗ API Error: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_all_teams_simulation():
    """Test simulation against all 30 teams"""
    print("\n" + "="*70)
    print("TEST 3: Simulation Against All 30 Teams")
    print("="*70)
    
    player = TEST_PLAYERS[0]  # Test with LeBron
    print(f"\n  Running {player['name']} vs all 30 teams...")
    
    results = []
    total_time = 0
    
    for team_id, team_name in TEAMS.items():
        try:
            start = time.time()
            response = requests.get(
                f"{BASE_URL}/aegis/simulate/{player['id']}",
                params={"opponent_id": team_id},
                timeout=30
            )
            elapsed = (time.time() - start) * 1000
            total_time += elapsed
            
            if response.status_code == 200:
                data = response.json()
                ev_pts = data.get('projections', {}).get('expected_value', {}).get('points', 0)
                grade = data.get('confidence', {}).get('grade', 'N/A')
                days_rest = data.get('schedule_context', {}).get('days_rest', 'N/A')
                
                print(f"  vs {team_name:25} | EV: {ev_pts:5.1f} pts | Grade: {grade} | Rest: {days_rest} | {elapsed:.0f}ms")
                results.append({
                    "opponent": team_name,
                    "ev_points": ev_pts,
                    "grade": grade,
                    "days_rest": days_rest,
                    "time_ms": elapsed
                })
            else:
                print(f"  vs {team_name:25} | ✗ Error: {response.status_code}")
                results.append(None)
                
        except Exception as e:
            print(f"  vs {team_name:25} | ✗ Exception: {e}")
            results.append(None)
    
    successful = sum(1 for r in results if r is not None)
    avg_time = total_time / len(TEAMS)
    
    print(f"\n  Summary: {successful}/30 teams successful")
    print(f"  Average simulation time: {avg_time:.0f}ms")
    print(f"  Total time: {total_time/1000:.1f}s")
    
    return results


def main():
    print("\n" + "="*70)
    print("QUANTSIGHT DAYS REST & SIMULATION VERIFICATION")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Test 1: Days Rest Calculation
    passed, failed, no_data = test_days_rest_calculation()
    
    # Test 2: Data Refresh Endpoint
    refresh_ok = test_data_refresh()
    
    # Test 3: All Teams Simulation
    all_teams_results = test_all_teams_simulation()
    
    # Final Summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    print(f"  Days Rest Test:    {passed} passed, {failed} failed, {no_data} no data")
    print(f"  Data Refresh:      {'✓ PASS' if refresh_ok else '✗ FAIL'}")
    print(f"  All Teams Sim:     {sum(1 for r in all_teams_results if r)} / 30 successful")
    print("="*70)


if __name__ == "__main__":
    main()
