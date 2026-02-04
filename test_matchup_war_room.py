"""
Test Matchup War Room Endpoints
================================
Verifies the new Matchup War Room API endpoints.
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_validate_lineup():
    """Test roster validation endpoint."""
    print("\n" + "="*60)
    print("TEST 1: Validate Lineup (Cleveland Cavaliers)")
    print("="*60)
    
    url = f"{BASE_URL}/aegis/validate-lineup/1610612739"
    
    try:
        start = time.time()
        response = requests.get(url, timeout=30)
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"⏱️  Time: {elapsed:.0f}ms")
            print(f"\n📋 Team: {data.get('team_name', 'Unknown')}")
            print(f"   Active: {data['summary']['active']}")
            print(f"   Out: {data['summary']['out']}")
            print(f"   Questionable: {data['summary']['questionable']}")
            print(f"   Vacuum Triggered: {data.get('vacuum_triggered', False)}")
            
            if data.get('active_players'):
                print(f"\n   Sample Active Players:")
                for p in data['active_players'][:3]:
                    print(f"      🟢 {p['name']} ({p.get('position', 'N/A')})")
            
            if data.get('out_players'):
                print(f"\n   Out Players:")
                for p in data['out_players']:
                    print(f"      🔴 {p['name']}: {p.get('injury_desc', 'N/A')}")
            
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_team_archetype():
    """Test team archetype aggregation endpoint."""
    print("\n" + "="*60)
    print("TEST 2: Team Archetype (Boston Celtics)")
    print("="*60)
    
    url = f"{BASE_URL}/aegis/team-archetype/1610612738"
    
    try:
        start = time.time()
        response = requests.get(url, timeout=30)
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"⏱️  Time: {elapsed:.0f}ms")
            print(f"\n📊 Team: {data.get('team_name', 'Unknown')}")
            print(f"   Offensive Archetype: {data.get('offensive_archetype', 'Unknown')}")
            print(f"   Defensive Profile: {data.get('defensive_profile', 'Unknown')}")
            print(f"   Active Players: {data.get('active_player_count', 0)}")
            
            if data.get('archetype_distribution'):
                print(f"\n   Archetype Distribution:")
                for arch, count in data['archetype_distribution'].items():
                    print(f"      {arch}: {count}")
            
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_full_matchup():
    """Test full matchup analysis endpoint."""
    print("\n" + "="*60)
    print("TEST 3: Full Matchup Analysis (CLE vs BOS)")
    print("="*60)
    
    url = f"{BASE_URL}/aegis/matchup?home_team_id=1610612739&away_team_id=1610612738"
    
    try:
        start = time.time()
        response = requests.get(url, timeout=120)  # Longer timeout for batch processing
        elapsed = (time.time() - start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {response.status_code}")
            print(f"⏱️  Backend Time: {data.get('execution_time_ms', 0):.0f}ms")
            print(f"⏱️  Total Time: {elapsed:.0f}ms")
            
            print(f"\n🎯 MATCHUP EDGE: {data.get('matchup_edge', 'Unknown').upper()}")
            print(f"   Reason: {data.get('edge_reason', 'N/A')}")
            
            # Home Team
            home = data.get('home_team', {})
            print(f"\n🏠 HOME: {home.get('team_name', 'Unknown')}")
            print(f"   Offense: {home.get('offensive_archetype', 'Unknown')}")
            print(f"   Defense: {home.get('defensive_profile', 'Unknown')}")
            print(f"   Active: {home.get('active_count', 0)}, Out: {home.get('out_count', 0)}")
            
            if home.get('players'):
                print(f"\n   Top 5 Projections:")
                for p in home['players'][:5]:
                    status = "🟢" if p['health_status'] == "green" else "🟡" if p['health_status'] == "yellow" else "🔴"
                    adv = "⬆️" if p['matchup_advantage'] == "advantaged" else "⬇️" if p['matchup_advantage'] == "countered" else "➡️"
                    print(f"      {status} {p['player_name']}: {p['ev_points']}pts {adv} [{p['efficiency_grade']}]")
            
            # Away Team
            away = data.get('away_team', {})
            print(f"\n🚗 AWAY: {away.get('team_name', 'Unknown')}")
            print(f"   Offense: {away.get('offensive_archetype', 'Unknown')}")
            print(f"   Defense: {away.get('defensive_profile', 'Unknown')}")
            
            if away.get('players'):
                print(f"\n   Top 5 Projections:")
                for p in away['players'][:5]:
                    status = "🟢" if p['health_status'] == "green" else "🟡" if p['health_status'] == "yellow" else "🔴"
                    adv = "⬆️" if p['matchup_advantage'] == "advantaged" else "⬇️" if p['matchup_advantage'] == "countered" else "➡️"
                    print(f"      {status} {p['player_name']}: {p['ev_points']}pts {adv} [{p['efficiency_grade']}]")
            
            # Vacuum
            if data.get('usage_vacuum_applied'):
                print(f"\n⚡ Usage Vacuum Applied: {len(data['usage_vacuum_applied'])} players")
            
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text[:500])
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("MATCHUP WAR ROOM API TEST SUITE")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Validate Lineup", test_validate_lineup()))
    results.append(("Team Archetype", test_team_archetype()))
    results.append(("Full Matchup", test_full_matchup()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
    
    print(f"\n   Total: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    main()
