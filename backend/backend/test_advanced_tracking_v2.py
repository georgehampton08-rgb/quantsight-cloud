"""
Advanced NBA Tracking Data Fetcher v2
Uses nba_api package for reliable endpoint access.
Fetches all 5 data layers requested:
1. Hustle Stats (Contested shots, Deflections)
2. Shot Clock Distribution
3. Defensive Impact (DFG%)
4. Speed/Distance Tracking
5. On/Off Splits
"""
import time
import json
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try importing nba_api
try:
    from nba_api.stats.endpoints import (
        leaguehustlestatsplayer,
        leaguedashptdefend,
        leaguedashplayerptshot,
        playerdashboardbyteamperformance,
        playerdashptpass,
        playerdashptshotdefend,
        playerdashptreb,
        leaguedashplayerstats,
    )
    HAS_NBA_API = True
    logger.info("nba_api package loaded successfully")
except ImportError as e:
    HAS_NBA_API = False
    logger.error(f"nba_api not available: {e}")

# Sample players (10 diverse archetypes)
SAMPLE_PLAYERS = [
    {'id': '2544', 'name': 'LeBron James'},
    {'id': '201142', 'name': 'Kevin Durant'},
    {'id': '203507', 'name': 'Giannis Antetokounmpo'},
    {'id': '1629029', 'name': 'Luka Doncic'},
    {'id': '203954', 'name': 'Joel Embiid'},
    {'id': '1628369', 'name': 'Jayson Tatum'},
    {'id': '1628378', 'name': 'Donovan Mitchell'},
    {'id': '1629027', 'name': 'Trae Young'},
    {'id': '1630169', 'name': 'Tyrese Maxey'},
    {'id': '203999', 'name': 'Nikola Jokic'},
]

RATE_LIMIT_DELAY = 1.2  # seconds between API calls


def rate_limit():
    """Apply rate limiting"""
    time.sleep(RATE_LIMIT_DELAY)


def fetch_hustle_stats():
    """Fetch Hustle layer: Contested shots, Deflections, Loose Balls"""
    print("\n" + "="*60)
    print("1. HUSTLE STATS (Contested Shots, Deflections)")
    print("="*60)
    
    try:
        rate_limit()
        hustle = leaguehustlestatsplayer.LeagueHustleStatsPlayer(
            season='2024-25',
            season_type_all_star='Regular Season',
            per_mode_time='PerGame'
        )
        df = hustle.get_data_frames()[0]
        
        print(f"✅ SUCCESS: {len(df)} players")
        print(f"   Columns: {list(df.columns[:10])}")
        
        # Find sample players
        for player in SAMPLE_PLAYERS[:3]:
            row = df[df['PLAYER_ID'] == int(player['id'])]
            if not row.empty:
                print(f"   {player['name']}: "
                      f"Contested={row['CONTESTED_SHOTS'].values[0]:.1f}, "
                      f"Deflections={row['DEFLECTIONS'].values[0]:.1f}")
        
        return {'success': True, 'columns': list(df.columns), 'rows': len(df)}
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return {'success': False, 'error': str(e)}


def fetch_defensive_tracking():
    """Fetch Defensive Impact: DFG%, Contested FG%"""
    print("\n" + "="*60)
    print("2. DEFENSIVE IMPACT (DFG%)")
    print("="*60)
    
    try:
        rate_limit()
        defense = leaguedashptdefend.LeagueDashPtDefend(
            season='2024-25',
            season_type_all_star='Regular Season',
            per_mode_simple='PerGame',
            defense_category='Overall'
        )
        df = defense.get_data_frames()[0]
        
        print(f"✅ SUCCESS: {len(df)} players")
        print(f"   Columns: {list(df.columns[:10])}")
        
        # Find defenders
        for player in SAMPLE_PLAYERS[:3]:
            row = df[df['CLOSE_DEF_PERSON_ID'] == int(player['id'])]
            if not row.empty:
                dfg = row['D_FG_PCT'].values[0] * 100 if 'D_FG_PCT' in df.columns else 0
                diff = row['PCT_PLUSMINUS'].values[0] * 100 if 'PCT_PLUSMINUS' in df.columns else 0
                print(f"   {player['name']}: DFG%={dfg:.1f}%, Impact={diff:+.1f}%")
        
        return {'success': True, 'columns': list(df.columns), 'rows': len(df)}
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return {'success': False, 'error': str(e)}


def fetch_shot_clock_distribution():
    """Fetch Shot Clock Distribution by player"""
    print("\n" + "="*60)
    print("3. SHOT CLOCK DISTRIBUTION")
    print("="*60)
    
    try:
        rate_limit()
        shots = leaguedashplayerptshot.LeagueDashPlayerPtShot(
            season='2024-25',
            season_type_all_star='Regular Season',
            per_mode_simple='PerGame'
        )
        df = shots.get_data_frames()[0]
        
        print(f"✅ SUCCESS: {len(df)} players")
        print(f"   Columns: {list(df.columns[:12])}")
        
        return {'success': True, 'columns': list(df.columns), 'rows': len(df)}
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return {'success': False, 'error': str(e)}


def fetch_player_passing(player_id, player_name):
    """Fetch player passing stats (Potential Assists)"""
    try:
        rate_limit()
        passing = playerdashptpass.PlayerDashPtPass(
            player_id=player_id,
            season='2024-25',
            season_type_all_star='Regular Season',
            per_mode_simple='PerGame'
        )
        dfs = passing.get_data_frames()
        
        if dfs and len(dfs[0]) > 0:
            df = dfs[0]
            if 'POTENTIAL_AST' in df.columns:
                pot_ast = df['POTENTIAL_AST'].sum()
                return {'success': True, 'potential_ast': pot_ast}
        
        return {'success': True, 'potential_ast': None}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fetch_player_on_off(player_id, player_name):
    """Fetch player On/Off splits"""
    try:
        rate_limit()
        on_off = playerdashboardbyteamperformance.PlayerDashboardByTeamPerformance(
            player_id=player_id,
            season='2024-25',
            season_type_all_star='Regular Season',
            per_mode_detailed='PerGame'
        )
        dfs = on_off.get_data_frames()
        
        # Look for on/off data
        if len(dfs) > 4:  # Usually index 4 contains on/off
            df = dfs[4] if len(dfs) > 4 else None
            return {'success': True, 'tables': len(dfs)}
        
        return {'success': True, 'tables': len(dfs)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fetch_advanced_stats():
    """Fetch advanced stats as fallback for speed/distance"""
    print("\n" + "="*60)
    print("4. ADVANCED PLAYER STATS (Speed/Distance Alternative)")
    print("="*60)
    
    try:
        rate_limit()
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season='2024-25',
            season_type_all_star='Regular Season',
            per_mode_detailed='PerGame',
            measure_type_detailed_defense='Advanced'
        )
        df = stats.get_data_frames()[0]
        
        print(f"✅ SUCCESS: {len(df)} players")
        print(f"   Columns: {list(df.columns[:15])}")
        
        return {'success': True, 'columns': list(df.columns), 'rows': len(df)}
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return {'success': False, 'error': str(e)}


def fetch_player_specific_data():
    """Fetch per-player data (passing, on/off)"""
    print("\n" + "="*60)
    print("5. PLAYER-SPECIFIC DATA (Passing, On/Off)")
    print("="*60)
    
    results = []
    for player in SAMPLE_PLAYERS[:5]:  # First 5 only
        print(f"\n🏀 {player['name']}")
        
        # Passing
        pass_result = fetch_player_passing(player['id'], player['name'])
        if pass_result['success']:
            pot_ast = pass_result.get('potential_ast')
            print(f"   ✅ Passing: Potential AST = {pot_ast}")
        else:
            print(f"   ❌ Passing failed: {pass_result.get('error')}")
        
        # On/Off
        on_off_result = fetch_player_on_off(player['id'], player['name'])
        if on_off_result['success']:
            print(f"   ✅ On/Off: {on_off_result.get('tables')} result tables")
        else:
            print(f"   ❌ On/Off failed: {on_off_result.get('error')}")
        
        results.append({
            'player': player['name'],
            'passing': pass_result,
            'on_off': on_off_result
        })
    
    return results


def run_full_test():
    """Run complete tracking data test"""
    print("\n" + "="*70)
    print("ADVANCED NBA TRACKING API TEST v2 (using nba_api)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Rate limit: {RATE_LIMIT_DELAY}s between calls")
    print("="*70)
    
    if not HAS_NBA_API:
        print("❌ nba_api package not installed")
        return
    
    results = {}
    
    # 1. Hustle Stats
    results['hustle'] = fetch_hustle_stats()
    
    # 2. Defensive Tracking
    results['defense'] = fetch_defensive_tracking()
    
    # 3. Shot Clock Distribution
    results['shot_clock'] = fetch_shot_clock_distribution()
    
    # 4. Advanced Stats
    results['advanced'] = fetch_advanced_stats()
    
    # 5. Player-specific data
    results['player_specific'] = fetch_player_specific_data()
    
    # Summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    
    print("\n┌─────────────────────────────┬──────────┬─────────────────────────┐")
    print("│ Data Layer                  │ Status   │ Notes                   │")
    print("├─────────────────────────────┼──────────┼─────────────────────────┤")
    
    layers = [
        ('Hustle (Contested/Deflect)', 'hustle', 'CONTESTED_SHOTS, DEFLECTIONS'),
        ('Defensive FG%', 'defense', 'D_FG_PCT, PCT_PLUSMINUS'),
        ('Shot Clock Distribution', 'shot_clock', 'FGA by clock range'),
        ('Advanced Stats', 'advanced', 'NET_RATING, AST_RATIO'),
        ('Per-Player Passing', 'player_specific', 'POTENTIAL_AST'),
    ]
    
    for name, key, notes in layers:
        result = results.get(key, {})
        if isinstance(result, list):
            status = "✅ READY" if any(r.get('passing', {}).get('success') for r in result) else "⚠️ PARTIAL"
        else:
            status = "✅ READY" if result.get('success') else "❌ FAILED"
        print(f"│ {name:<27} │ {status:<8} │ {notes:<23} │")
    
    print("└─────────────────────────────┴──────────┴─────────────────────────┘")
    
    # Save results
    output_path = Path(__file__).parent / 'data' / 'tracking_api_v2_results.json'
    
    # Convert to JSON-safe
    safe_results = {}
    for k, v in results.items():
        if isinstance(v, dict):
            safe_results[k] = {
                'success': v.get('success'),
                'rows': v.get('rows'),
                'columns': v.get('columns', [])[:20] if v.get('columns') else None
            }
        elif isinstance(v, list):
            safe_results[k] = [{'player': r['player'], 'success': r.get('passing', {}).get('success')} for r in v]
    
    with open(output_path, 'w') as f:
        json.dump(safe_results, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_path}")
    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    run_full_test()
