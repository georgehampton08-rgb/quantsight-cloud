"""
Advanced NBA Tracking - Player Specific Fix
Fixes for PlayerDashPtPass (needs team_id) and On/Off splits
"""
import time
import json
from datetime import datetime
from pathlib import Path

from nba_api.stats.endpoints import (
    playerdashptpass,
    playerdashboardbyyearoveryear,
    commonplayerinfo,
)

# Players with their team IDs
SAMPLE_PLAYERS = [
    {'id': '2544', 'name': 'LeBron James', 'team_id': '1610612747'},  # LAL
    {'id': '201142', 'name': 'Kevin Durant', 'team_id': '1610612756'},  # PHX
    {'id': '203507', 'name': 'Giannis Antetokounmpo', 'team_id': '1610612749'},  # MIL
    {'id': '1629029', 'name': 'Luka Doncic', 'team_id': '1610612742'},  # DAL
    {'id': '203954', 'name': 'Joel Embiid', 'team_id': '1610612755'},  # PHI
    {'id': '1628369', 'name': 'Jayson Tatum', 'team_id': '1610612738'},  # BOS
    {'id': '1628378', 'name': 'Donovan Mitchell', 'team_id': '1610612739'},  # CLE
    {'id': '1629027', 'name': 'Trae Young', 'team_id': '1610612737'},  # ATL
    {'id': '1630169', 'name': 'Tyrese Maxey', 'team_id': '1610612755'},  # PHI
    {'id': '203999', 'name': 'Nikola Jokic', 'team_id': '1610612743'},  # DEN
]

RATE_LIMIT = 1.5


def fetch_passing_with_team(player_id, team_id, player_name):
    """Fetch passing stats with required team_id"""
    try:
        time.sleep(RATE_LIMIT)
        passing = playerdashptpass.PlayerDashPtPass(
            player_id=player_id,
            team_id=team_id,
            season='2024-25',
            season_type_all_star='Regular Season',
            per_mode_simple='PerGame'
        )
        dfs = passing.get_data_frames()
        
        if dfs and len(dfs) > 0:
            passes_made = dfs[0]
            if not passes_made.empty:
                return {
                    'success': True,
                    'rows': len(passes_made),
                    'columns': list(passes_made.columns)[:10],
                    'sample': passes_made.head(2).to_dict('records') if len(passes_made) > 0 else []
                }
        return {'success': True, 'rows': 0, 'message': 'No passing data'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fetch_on_off_splits(player_id, player_name):
    """Fetch On/Off splits using year-over-year dashboard"""
    try:
        time.sleep(RATE_LIMIT)
        yoy = playerdashboardbyyearoveryear.PlayerDashboardByYearOverYear(
            player_id=player_id,
            season='2024-25',
            season_type_playoffs='Regular Season',
            per_mode_detailed='PerGame'
        )
        dfs = yoy.get_data_frames()
        
        if dfs:
            return {
                'success': True,
                'tables': len(dfs),
                'columns': list(dfs[0].columns)[:10] if len(dfs) > 0 else []
            }
        return {'success': True, 'tables': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_test():
    """Run player-specific endpoint tests"""
    print("\n" + "="*70)
    print("PLAYER-SPECIFIC TRACKING DATA FIX")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    results = []
    
    for player in SAMPLE_PLAYERS[:5]:  # Test first 5
        print(f"\n🏀 {player['name']} (Team ID: {player['team_id']})")
        
        # Passing data
        pass_result = fetch_passing_with_team(player['id'], player['team_id'], player['name'])
        if pass_result['success']:
            print(f"   ✅ Passing: {pass_result.get('rows', 0)} records")
            if pass_result.get('columns'):
                print(f"   Columns: {pass_result['columns'][:5]}")
        else:
            print(f"   ❌ Passing: {pass_result.get('error')}")
        
        # On/Off splits
        onoff_result = fetch_on_off_splits(player['id'], player['name'])
        if onoff_result['success']:
            print(f"   ✅ On/Off: {onoff_result.get('tables', 0)} tables")
        else:
            print(f"   ❌ On/Off: {onoff_result.get('error')}")
        
        results.append({
            'player': player['name'],
            'passing': pass_result,
            'on_off': onoff_result
        })
    
    # Summary
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    passing_success = sum(1 for r in results if r['passing'].get('success'))
    onoff_success = sum(1 for r in results if r['on_off'].get('success'))
    
    print(f"\n✅ Passing data: {passing_success}/{len(results)} players")
    print(f"✅ On/Off data: {onoff_success}/{len(results)} players")
    
    # Save
    output = Path(__file__).parent / 'data' / 'player_specific_results.json'
    with open(output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📄 Saved to: {output}")


if __name__ == "__main__":
    run_test()
