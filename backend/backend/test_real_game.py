"""
REAL GAME MATCHUP TEST: LAL vs CLE (January 28, 2026)
======================================================
Full end-to-end test of all matchup engines with REAL data.
Simulates exactly what the app does from start to finish.
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime

# Setup paths
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from data_paths import get_db_path, get_data_health
from services.defense_matrix import DefenseMatrix
from services.nemesis_engine import NemesisEngine
from services.pace_engine import PaceEngine

# Test configuration
HOME_TEAM = "CLE"
AWAY_TEAM = "LAL"
GAME_DATE = "2026-01-28"

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(title):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")


def print_section(title):
    print(f"\n{Colors.BOLD}{Colors.BLUE}--- {title} ---{Colors.END}")


def print_pass(msg):
    print(f"{Colors.GREEN}✅ PASS:{Colors.END} {msg}")


def print_fail(msg):
    print(f"{Colors.RED}❌ FAIL:{Colors.END} {msg}")


def print_warn(msg):
    print(f"{Colors.YELLOW}⚠️  WARN:{Colors.END} {msg}")


def print_info(msg):
    print(f"{Colors.CYAN}ℹ️  INFO:{Colors.END} {msg}")


def test_data_health():
    """Test 1: Verify data layer health"""
    print_section("TEST 1: Data Layer Health")
    
    health = get_data_health()
    
    print(f"   Database: {health.get('database_path')}")
    print(f"   Status: {health.get('status')}")
    print(f"   Tables: {health.get('available_tables')}/{health.get('total_tables')}")
    
    if health.get('status') in ['healthy', 'partial']:
        print_pass(f"Data layer is {health.get('status')}")
        return True
    else:
        print_fail(f"Data layer status: {health.get('status')}")
        return False


def test_defense_matrix():
    """Test 2: Defense Matrix with real data"""
    print_section("TEST 2: Defense Matrix (REAL DATA)")
    
    results = {}
    for team in [HOME_TEAM, AWAY_TEAM]:
        profile = DefenseMatrix.get_profile(team)
        
        print(f"\n   {team} Defensive Profile:")
        print(f"      Source: {profile.get('source')}")
        print(f"      Available: {profile.get('available')}")
        
        if profile.get('available'):
            print(f"      OPP PTS: {profile.get('opp_pts')}")
            print(f"      DEF RATING: {profile.get('def_rating')}")
            print(f"      PACE: {profile.get('pace')}")
            print(f"      vs_PG: {profile.get('vs_PG')} (Points allowed over average)")
            print(f"      vs_C: {profile.get('vs_C')}")
            print_pass(f"{team} defense profile loaded from REAL data")
            results[team] = profile
        else:
            print_warn(f"{team} defense data unavailable - {profile.get('message', 'Unknown')}")
            results[team] = None
    
    return results


def test_pace_engine():
    """Test 3: Pace Engine matchup analysis"""
    print_section("TEST 3: Pace Engine (Matchup Analysis)")
    
    pace_info = PaceEngine.get_matchup_pace_info(HOME_TEAM, AWAY_TEAM)
    
    print(f"\n   {HOME_TEAM} vs {AWAY_TEAM} Pace Analysis:")
    print(f"      {HOME_TEAM} Pace: {pace_info.get('team1_pace')}")
    print(f"      {AWAY_TEAM} Pace: {pace_info.get('team2_pace')}")
    print(f"      Projected Pace: {pace_info.get('projected_pace')}")
    print(f"      Multiplier: {pace_info.get('multiplier')}")
    print(f"      Category: {pace_info.get('category')}")
    print(f"      Impact: {pace_info.get('impact_percent')}%")
    print(f"      Source: {pace_info.get('source')}")
    
    if pace_info.get('available'):
        print_pass("Pace analysis using REAL data")
    else:
        print_warn("Pace analysis unavailable")
    
    return pace_info


def get_team_rosters():
    """Get rosters for both teams from database"""
    print_section("TEST 4: Loading Team Rosters")
    
    db_path = get_db_path()
    if not db_path or not db_path.exists():
        print_fail("Database not found")
        return {}, {}
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    rosters = {}
    
    for team in [HOME_TEAM, AWAY_TEAM]:
        # Use player_rolling_averages which has the recent data
        cursor.execute("""
            SELECT DISTINCT pra.player_id, pra.player_name, pb.position,
                   pra.avg_points as ppg, pra.avg_rebounds as rpg, pra.avg_assists as apg,
                   pb.height, pb.weight, pra.trend
            FROM player_rolling_averages pra
            LEFT JOIN player_bio pb ON pra.player_id = pb.player_id
            WHERE pb.team = ?
            ORDER BY pra.avg_points DESC
            LIMIT 10
        """, (team,))
        
        players = [dict(row) for row in cursor.fetchall()]
        
        # If no players from rolling averages, try player_bio directly
        if not players:
            cursor.execute("""
                SELECT player_id, player_name, position, height, weight, team
                FROM player_bio
                WHERE team = ?
            """, (team,))
            players = [dict(row) for row in cursor.fetchall()]
        rosters[team] = players
        
        print(f"\n   {team} Roster ({len(players)} players):")
        for p in players[:5]:
            print(f"      {p['player_name']:20} {p.get('position', 'N/A'):3} {p.get('ppg', 0):.1f} PPG")
    
    conn.close()
    
    if rosters[HOME_TEAM] and rosters[AWAY_TEAM]:
        print_pass(f"Loaded {len(rosters[HOME_TEAM])} {HOME_TEAM} players, {len(rosters[AWAY_TEAM])} {AWAY_TEAM} players")
    else:
        print_warn("Some rosters may be incomplete")
    
    return rosters


def test_nemesis_engine(rosters, defense_profiles):
    """Test 5: Nemesis Engine for key players"""
    print_section("TEST 5: Nemesis Engine (Player vs Team History)")
    
    matchups = []
    
    for team, opponent in [(AWAY_TEAM, HOME_TEAM), (HOME_TEAM, AWAY_TEAM)]:
        print(f"\n   {team} players vs {opponent}:")
        
        players = rosters.get(team, [])[:5]  # Top 5 scorers
        
        for player in players:
            player_id = player['player_id']
            season_ppg = player.get('ppg', 15.0) or 15.0
            
            analysis = NemesisEngine.analyze_head_to_head(player_id, opponent, season_ppg)
            
            grade = analysis.get('grade', '?')
            status = analysis.get('status', 'Unknown')
            avg_vs = analysis.get('avg_vs_opponent')
            delta = analysis.get('delta_percent', 0)
            source = analysis.get('source', 'unknown')
            games = analysis.get('games_sampled', 0)
            
            if avg_vs:
                print(f"      {player['player_name']:20} Grade: {grade} ({status}) | {avg_vs:.1f} PPG vs {opponent} ({delta:+.1f}%) [{games}g]")
            else:
                print(f"      {player['player_name']:20} Grade: {grade} ({status}) | No history")
            
            # Calculate adjusted projection
            defense = defense_profiles.get(opponent, {})
            position = player.get('position', 'SF')
            
            if position and defense.get('available'):
                # Map position to vs_XX format
                pos_map = {'G': 'PG', 'F': 'SF', 'C': 'C', 'PG': 'PG', 'SG': 'SG', 'SF': 'SF', 'PF': 'PF'}
                pos_key = f"vs_{pos_map.get(position, 'SF')}"
                paoa = defense.get(pos_key, 0)
                
                matchups.append({
                    'player': player['player_name'],
                    'team': team,
                    'opponent': opponent,
                    'season_ppg': season_ppg,
                    'nemesis_grade': grade,
                    'nemesis_status': status,
                    'avg_vs_opponent': avg_vs,
                    'delta_percent': delta,
                    'defense_paoa': paoa,
                    'games_sampled': games,
                    'source': source
                })
    
    if matchups:
        print_pass(f"Analyzed {len(matchups)} player matchups")
    
    return matchups


def calculate_projections(matchups, pace_info):
    """Test 6: Calculate final projections"""
    print_section("TEST 6: Final Projections with All Factors")
    
    pace_mult = pace_info.get('multiplier', 1.0)
    
    print(f"\n   Pace Multiplier: {pace_mult} ({pace_info.get('category', 'Unknown')} pace)")
    print(f"\n   Player Projections:")
    print(f"   {'Player':<20} {'Team':<4} {'Base':>6} {'+Def':>6} {'*Pace':>6} {'Final':>7} {'Grade':>6}")
    print(f"   {'-'*65}")
    
    projections = []
    
    for m in matchups:
        base = m['season_ppg']
        paoa = m['defense_paoa']
        
        # If we have real vs-opponent data, weight it heavily
        if m['avg_vs_opponent'] and m['games_sampled'] >= 3:
            # Blend season average with historical performance
            blend_weight = min(m['games_sampled'] / 10, 0.5)  # Max 50% weight to history
            adjusted_base = base * (1 - blend_weight) + m['avg_vs_opponent'] * blend_weight
        else:
            adjusted_base = base
        
        # Apply defense adjustment
        defense_adjusted = adjusted_base + paoa
        
        # Apply pace multiplier
        final = defense_adjusted * pace_mult
        
        grade = m['nemesis_grade']
        
        print(f"   {m['player']:<20} {m['team']:<4} {base:>6.1f} {defense_adjusted:>6.1f} {pace_mult:>6.2f} {final:>7.1f} {grade:>6}")
        
        projections.append({
            **m,
            'base_ppg': base,
            'defense_adjusted': defense_adjusted,
            'pace_multiplied': final,
            'final_projection': round(final, 1)
        })
    
    # Find best matchups
    print(f"\n   {Colors.BOLD}🔥 BEST MATCHUP ADVANTAGES:{Colors.END}")
    
    sorted_by_advantage = sorted(projections, key=lambda x: x['final_projection'] - x['season_ppg'], reverse=True)
    
    for p in sorted_by_advantage[:3]:
        adv = p['final_projection'] - p['season_ppg']
        print(f"   {p['player']} ({p['team']}): {p['season_ppg']:.1f} → {p['final_projection']:.1f} ({adv:+.1f} PPG advantage)")
    
    print(f"\n   {Colors.BOLD}❄️ WORST MATCHUP DISADVANTAGES:{Colors.END}")
    
    for p in sorted_by_advantage[-3:]:
        adv = p['final_projection'] - p['season_ppg']
        print(f"   {p['player']} ({p['team']}): {p['season_ppg']:.1f} → {p['final_projection']:.1f} ({adv:+.1f} PPG)")
    
    print_pass(f"Generated {len(projections)} player projections")
    
    return projections


def test_api_endpoints():
    """Test 7: Verify API endpoints"""
    print_section("TEST 7: API Endpoint Verification")
    
    import requests
    
    endpoints = [
        ("Health", "http://localhost:5000/health"),
        ("Data Health", "http://localhost:5000/health/data"),
        ("Team Defense CLE", f"http://localhost:5000/data/team-defense/{HOME_TEAM}"),
        ("Team Defense LAL", f"http://localhost:5000/data/team-defense/{AWAY_TEAM}"),
    ]
    
    results = []
    for name, url in endpoints:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print_pass(f"{name}: {resp.status_code}")
                results.append((name, True, resp.json()))
            else:
                print_fail(f"{name}: {resp.status_code}")
                results.append((name, False, None))
        except requests.exceptions.ConnectionError:
            print_warn(f"{name}: Server not running")
            results.append((name, False, None))
        except Exception as e:
            print_fail(f"{name}: {e}")
            results.append((name, False, None))
    
    return results


def run_all_tests():
    """Run all tests in sequence"""
    print_header(f"REAL GAME MATCHUP TEST: {AWAY_TEAM} @ {HOME_TEAM}")
    print(f"   Date: {GAME_DATE}")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }
    
    # Test 1: Data Health
    if test_data_health():
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 2: Defense Matrix
    defense_profiles = test_defense_matrix()
    if defense_profiles.get(HOME_TEAM) and defense_profiles.get(AWAY_TEAM):
        results['passed'] += 1
    else:
        results['warnings'] += 1
    
    # Test 3: Pace Engine
    pace_info = test_pace_engine()
    if pace_info.get('available'):
        results['passed'] += 1
    else:
        results['warnings'] += 1
    
    # Test 4: Rosters
    rosters = get_team_rosters()
    if rosters.get(HOME_TEAM) and rosters.get(AWAY_TEAM):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 5: Nemesis Engine
    matchups = test_nemesis_engine(rosters, defense_profiles)
    if matchups:
        results['passed'] += 1
    else:
        results['warnings'] += 1
    
    # Test 6: Projections
    projections = calculate_projections(matchups, pace_info)
    if projections:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # Test 7: API Endpoints
    api_results = test_api_endpoints()
    api_passed = sum(1 for _, ok, _ in api_results if ok)
    if api_passed >= len(api_results) / 2:
        results['passed'] += 1
    else:
        results['warnings'] += 1
    
    # Summary
    print_header("TEST SUMMARY")
    print(f"\n   {Colors.GREEN}PASSED:{Colors.END} {results['passed']}")
    print(f"   {Colors.RED}FAILED:{Colors.END} {results['failed']}")
    print(f"   {Colors.YELLOW}WARNINGS:{Colors.END} {results['warnings']}")
    
    if results['failed'] == 0:
        print(f"\n   {Colors.GREEN}{Colors.BOLD}🎉 ALL CRITICAL TESTS PASSED!{Colors.END}")
        print(f"   The matchup engine is ready for {AWAY_TEAM} @ {HOME_TEAM}")
    else:
        print(f"\n   {Colors.RED}{Colors.BOLD}⚠️ SOME TESTS FAILED - Review above{Colors.END}")
    
    return results, projections


if __name__ == '__main__':
    results, projections = run_all_tests()
    
    # Save projections to file
    output_file = SCRIPT_DIR / 'data' / 'latest_projections.json'
    with open(output_file, 'w') as f:
        json.dump({
            'game': f"{AWAY_TEAM} @ {HOME_TEAM}",
            'date': GAME_DATE,
            'generated_at': datetime.now().isoformat(),
            'projections': projections
        }, f, indent=2)
    
    print(f"\n   📁 Projections saved to: {output_file}")
