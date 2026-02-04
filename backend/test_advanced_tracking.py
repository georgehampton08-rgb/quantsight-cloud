"""
Advanced NBA Tracking Data Test
Tests API availability for advanced stats:
1. Player Tracking (Hustle Layer)
2. Shot Clock Distribution
3. Defensive Impact (DFG%)
4. On/Off Splits

Uses smart rate limiting and batch where possible.
"""
import requests
import time
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend directory to path to import config
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

try:
    from core import config
except ImportError:
    # If running from different location
    try:
        from backend.core import config
    except ImportError:
        # Fallback if config not found
        class ConfigShim:
            CURRENT_SEASON = "2024-25"
        config = ConfigShim()

# Sample players to test (mix of archetypes)
SAMPLE_PLAYERS = [
    {'id': '2544', 'name': 'LeBron James', 'archetype': 'Elite Scorer/Playmaker'},
    {'id': '201142', 'name': 'Kevin Durant', 'archetype': 'Elite Scorer'},
    {'id': '203507', 'name': 'Giannis Antetokounmpo', 'archetype': 'Slasher'},
    {'id': '1629029', 'name': 'Luka Doncic', 'archetype': 'Playmaker'},
    {'id': '203954', 'name': 'Joel Embiid', 'archetype': 'Post Scorer'},
    {'id': '1628369', 'name': 'Jayson Tatum', 'archetype': 'Two-Way'},
    {'id': '1628378', 'name': 'Donovan Mitchell', 'archetype': 'Sniper'},
    {'id': '1629027', 'name': 'Trae Young', 'archetype': 'Playmaker'},
    {'id': '1630169', 'name': 'Tyrese Maxey', 'archetype': 'Slasher'},
    {'id': '203999', 'name': 'Nikola Jokic', 'archetype': 'Playmaker/Glass Cleaner'},
]

# NBA API Headers
HEADERS = {
    'User-Agent': config.NBA_API_USER_AGENT if hasattr(config, 'NBA_API_USER_AGENT') else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Connection': 'keep-alive',
}

# API Endpoints
ENDPOINTS = {
    # 1. Player Tracking (Hustle Stats)
    'hustle': {
        'url': 'https://stats.nba.com/stats/leaguehustlestatsplayer',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame'},
        'description': 'Hustle stats: deflections, loose balls, contested shots',
    },
    
    # 2. Shot Clock Distribution
    'shot_clock': {
        'url': 'https://stats.nba.com/stats/leaguedashteamshotlocations',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame', 'MeasureType': 'Base'},
        'description': 'Team shot distribution by area',
    },
    
    # 3. Player Tracking - Speed/Distance
    'tracking_speed': {
        'url': 'https://stats.nba.com/stats/leaguedashptstats',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame', 
                   'PlayerOrTeam': 'Player', 'PtMeasureType': 'SpeedDistance'},
        'description': 'Distance traveled, average speed',
    },
    
    # 4. Player Tracking - Passing
    'tracking_passing': {
        'url': 'https://stats.nba.com/stats/leaguedashptstats',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame',
                   'PlayerOrTeam': 'Player', 'PtMeasureType': 'Passing'},
        'description': 'Potential assists, passes made, AST%',
    },
    
    # 5. Defensive Dashboard
    'defense': {
        'url': 'https://stats.nba.com/stats/leaguedashptdefend',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame',
                   'DefenseCategory': 'Overall'},
        'description': 'Defended FG%, DFGM, contests',
    },
    
    # 6. On/Off Splits (per player - requires individual calls)
    'on_off': {
        'url': 'https://stats.nba.com/stats/playerdashboardbyteamperformance',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame'},
        'description': 'Player on/off court impact',
    },
    
    # 7. Shot Dashboard by Shot Clock
    'shot_clock_player': {
        'url': 'https://stats.nba.com/stats/leaguedashplayerptshot',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame'},
        'description': 'Player shots by shot-clock range',
    },
    
    # 8. Catch and Shoot / Pullup
    'catch_shoot': {
        'url': 'https://stats.nba.com/stats/leaguedashptstats',
        'params': {'Season': config.CURRENT_SEASON, 'SeasonType': 'Regular Season', 'PerMode': 'PerGame',
                   'PlayerOrTeam': 'Player', 'PtMeasureType': 'CatchShoot'},
        'description': 'Catch & shoot efficiency',
    },
}


class AdvancedTrackingTester:
    """Tests NBA API endpoints with smart rate limiting"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.results = {}
        self.rate_limit_delay = 1.5  # seconds between calls
        self.last_call_time = 0
    
    def _rate_limit(self):
        """Smart rate limiting to avoid 429s"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            print(f"   ⏳ Rate limiting: {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self.last_call_time = time.time()
    
    def _make_request(self, name: str, url: str, params: dict, timeout: int = 30) -> dict:
        """Make API request with error handling"""
        self._rate_limit()
        
        try:
            response = self.session.get(url, params=params, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                result_sets = data.get('resultSets', [])
                
                # Extract headers and sample data
                if result_sets:
                    headers = result_sets[0].get('headers', [])
                    rows = result_sets[0].get('rowSet', [])
                    return {
                        'success': True,
                        'headers': headers,
                        'row_count': len(rows),
                        'sample': rows[:3] if rows else [],  # First 3 rows
                    }
                return {'success': True, 'headers': [], 'row_count': 0, 'sample': []}
            
            elif response.status_code == 429:
                print(f"   ⚠️ Rate limited! Waiting 30s...")
                time.sleep(30)
                return {'success': False, 'error': 'Rate limited'}
            
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except requests.Timeout:
            return {'success': False, 'error': 'Timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_batch_endpoints(self):
        """Test endpoints that return all players in one call (batch-friendly)"""
        print("\n" + "="*70)
        print("BATCH ENDPOINTS (All players in one call)")
        print("="*70)
        
        batch_endpoints = ['hustle', 'tracking_speed', 'tracking_passing', 'defense', 
                           'catch_shoot', 'shot_clock_player']
        
        for ep_name in batch_endpoints:
            ep = ENDPOINTS[ep_name]
            print(f"\n📊 Testing: {ep_name}")
            print(f"   URL: {ep['url']}")
            print(f"   Purpose: {ep['description']}")
            
            result = self._make_request(ep_name, ep['url'], ep['params'])
            self.results[ep_name] = result
            
            if result['success']:
                print(f"   ✅ SUCCESS: {result['row_count']} players found")
                print(f"   Headers: {result['headers'][:8]}...")  # First 8 headers
                
                # Find sample players in data
                if result['sample']:
                    print(f"   Sample data available")
            else:
                print(f"   ❌ FAILED: {result.get('error')}")
    
    def test_player_specific_endpoints(self):
        """Test endpoints that require per-player calls"""
        print("\n" + "="*70)
        print("PLAYER-SPECIFIC ENDPOINTS (One call per player)")
        print("="*70)
        
        on_off_results = []
        
        for player in SAMPLE_PLAYERS[:3]:  # Test first 3 to save time
            print(f"\n🏀 {player['name']} (ID: {player['id']})")
            
            # On/Off splits
            ep = ENDPOINTS['on_off']
            params = {**ep['params'], 'PlayerID': player['id']}
            
            print(f"   Testing On/Off splits...")
            result = self._make_request(f"on_off_{player['id']}", ep['url'], params)
            
            if result['success']:
                print(f"   ✅ On/Off: {result['row_count']} result sets")
                on_off_results.append({'player': player['name'], 'data': result})
            else:
                print(f"   ❌ On/Off failed: {result.get('error')}")
        
        self.results['on_off_samples'] = on_off_results
    
    def summarize_data_availability(self):
        """Summarize what data is available for the enrichment system"""
        print("\n" + "="*70)
        print("DATA AVAILABILITY SUMMARY")
        print("="*70)
        
        # Map data to features
        feature_mapping = {
            'Potential Assists': ('tracking_passing', 'POTENTIAL_AST'),
            'Distance/Speed': ('tracking_speed', 'DIST_MILES'),
            'Contested Shots': ('hustle', 'CONTESTED_SHOTS'),
            'Deflections': ('hustle', 'DEFLECTIONS'),
            'Loose Balls': ('hustle', 'LOOSE_BALLS_RECOVERED'),
            'Defended FG%': ('defense', 'D_FG_PCT'),
            'Catch & Shoot': ('catch_shoot', 'CATCH_SHOOT_FG_PCT'),
        }
        
        print("\n┌─────────────────────────┬──────────┬─────────────────────────┐")
        print("│ Feature                 │ Status   │ API Endpoint            │")
        print("├─────────────────────────┼──────────┼─────────────────────────┤")
        
        for feature, (ep_name, col) in feature_mapping.items():
            result = self.results.get(ep_name, {})
            status = "✅ READY" if result.get('success') else "❌ FAILED"
            print(f"│ {feature:<23} │ {status:<8} │ {ep_name:<23} │")
        
        print("└─────────────────────────┴──────────┴─────────────────────────┘")
        
        # Save results
        output_path = Path(__file__).parent / 'data' / 'tracking_api_test_results.json'
        with open(output_path, 'w') as f:
            # Convert results to JSON-safe format
            safe_results = {}
            for k, v in self.results.items():
                if isinstance(v, dict):
                    safe_results[k] = {
                        'success': v.get('success'),
                        'row_count': v.get('row_count'),
                        'headers': v.get('headers', [])[:15],  # First 15 headers
                    }
            json.dump(safe_results, f, indent=2)
        print(f"\n📄 Results saved to: {output_path}")
    
    def run_full_test(self):
        """Run complete API test suite"""
        print("\n" + "="*70)
        print("ADVANCED NBA TRACKING API TEST")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        print(f"\nTesting {len(SAMPLE_PLAYERS)} players with smart rate limiting")
        print(f"Rate limit delay: {self.rate_limit_delay}s between calls")
        
        # Test batch endpoints (more efficient)
        self.test_batch_endpoints()
        
        # Test per-player endpoints
        self.test_player_specific_endpoints()
        
        # Summarize
        self.summarize_data_availability()
        
        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70)


if __name__ == "__main__":
    tester = AdvancedTrackingTester()
    tester.run_full_test()
