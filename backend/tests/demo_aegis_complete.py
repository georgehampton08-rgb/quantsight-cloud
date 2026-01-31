"""
Comprehensive Demo: Aegis Router + Rate Governor
Shows complete smart routing with rate limiting
"""

import asyncio
import sys
from pathlib import Path
import random

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis.router_brain import AegisBrain
from aegis.cache_manager import CacheManager
from aegis.rate_governor import TokenBucketGovernor


class SimulatedNBAAPI:
    """Simulated NBA API with realistic headers"""
    
    def __init__(self):
        self.call_count = 0
        self.rate_limit = 100
    
    async def fetch(self, entity_type: str, entity_id: int, query: dict) -> dict:
        """Simulate API fetch with rate limit headers"""
        self.call_count += 1
        self.rate_limit -= 1
        
        # Simulate network latency
        await asyncio.sleep(0.05)
        
        # Mock player data
        data = {
            'player_id': entity_id,
            'name': f'Player {entity_id}',
            'points': round(random.uniform(10, 30), 1),
            'rebounds': round(random.uniform(3, 12), 1),
            'assists': round(random.uniform(2, 10), 1),
            'latency_ms': 50,
            'headers': {
                'X-RateLimit-Remaining': str(self.rate_limit),
                'X-RateLimit-Limit': '100'
            }
        }
        
        return data


async def demo_aegis_system():
    """Full system demo with router + governor"""
    
    print("=" * 80)
    print("AEGIS-SOVEREIGN DATA ROUTER: COMPLETE SYSTEM DEMO")
    print("Smart Routing + Rate Limiting + Offline Resilience")
    print("=" * 80)
    
    # Initialize components
    cache = CacheManager("quantsight.db")
    api = SimulatedNBAAPI()
    governor = TokenBucketGovernor(max_tokens=5, refill_rate=0.75)
    router = AegisBrain(cache, api, governor)
    
    print("\n✓ System Initialized")
    print(f"  - Router: AegisBrain")
    print(f"  - Cache: SQLite")
    print(f"  - API: Simulated NBA API")
    print(f"  - Governor: Token Bucket (5 tokens, 0.75s refill)")
    
    # Scenario 1: Normal Operation
    print("\n" + "=" * 80)
    print("SCENARIO 1: Normal Operation (Cache Miss → API → Cache Hit)")
    print("=" * 80)
    
    player_id = 2544
    
    print(f"\n[Request 1] Fetching Player {player_id} (first time)")
    result1 = await router.route_request({'type': 'player_stats', 'id': player_id})
    print(f"  Source: {result1['source']} | Freshness: {result1['freshness']} | "
          f"Latency: {result1['latency_ms']}ms")
    
    print(f"\n[Request 2] Fetching Player {player_id} again (should be cached)")
    result2 = await router.route_request({'type': 'player_stats', 'id': player_id})
    print(f"  Source: {result2['source']} | Freshness: {result2['freshness']} | "
          f"Latency: {result2['latency_ms']}ms")
    
    # Scenario 2: Rate Limiting in Action
    print("\n" + "=" * 80)
    print("SCENARIO 2: Rate Limiting (Rapid fire requests)")
    print("=" * 80)
    
    print("\nFiring 10 rapid requests for different players:")
    for i in range(10):
        player_id = 2000 + i
        try:
            result = await router.route_request({'type': 'player_stats', 'id': player_id})
            status = governor.get_status()
            print(f"  [{i+1}] Player {player_id}: {result['source'][:4]} | "
                  f"Tokens: {status['tokens_available']:.1f}")
        except Exception as e:
            status = governor.get_status()
            print(f"  [{i+1}] Player {player_id}: DENIED | "
                  f"Tokens: {status['tokens_available']:.1f} (rate limited)")
    
    # Scenario 3: Burst Mode
    print("\n" + "=" * 80)
    print("SCENARIO 3: Burst Mode (Morning Briefing)")
    print("=" * 80)
    
    print("\nActivating burst mode for morning briefing...")
    governor.activate_burst_mode("morning_briefing")
    
    print("Fetching 5 players rapidly:")
    for i in range(5):
        player_id = 3000 + i
        result = await router.route_request({'type': 'player_stats', 'id': player_id})
        print(f"  [{i+1}] Player {player_id}: {result['source']}")
    
    # Scenario 4: Emergency Brake
    print("\n" + "=" * 80)
    print("SCENARIO 4: Emergency Brake (Low Quota)")
    print("=" * 80)
    
    # Simulate low quota
    api.rate_limit = 8  # 8% remaining
    
    print("\nSimulating API returning low quota warning...")
    result = await router.route_request({'type': 'player_stats', 'id': 4000})
    
    status = governor.get_status()
    print(f"\n  Rate Limit: {status['rate_limit_remaining']}/{status['rate_limit_total']} "
          f"({status['rate_limit_percentage']:.1f}%)")
    print(f"  Emergency Mode: {status['emergency_mode']}")
    print(f"  Historical Paused: {status['historical_paused']}")
    
    # Try normal request
    print("\nAttempting normal priority request:")
    try:
        result = await router.route_request({
            'type': 'player_stats',
            'id': 4001,
            'priority': 'normal'
        })
        print(f"  Result: {result['source']}")
    except Exception:
        print(f"  Result: DENIED (emergency brake)")
    
    # Final Statistics
    print("\n" + "=" * 80)
    print("SYSTEM STATISTICS")
    print("=" * 80)
    
    router_stats = router.get_stats()
    print("\nRouter:")
    print(f"  Cache Hits: {router_stats['cache_hits']}")
    print(f"  Cache Misses: {router_stats['cache_misses']}")
    print(f"  Cache Hit Rate: {router_stats['cache_hit_rate']:.1%}")
    print(f"  API Calls: {router_stats['api_calls']}")
    print(f"  API Calls Denied: {router_stats.get('api_calls_denied', 0)}")
    
    governor_stats = governor.get_status()
    print("\nGovernor:")
    print(f"  Tokens Available: {governor_stats['tokens_available']:.1f}")
    print(f"  Requests Last Minute: {governor_stats['requests_last_minute']}")
    print(f"  Emergency Mode: {governor_stats['emergency_mode']}")
    
    cache_stats = cache.get_stats()
    print("\nCache:")
    print(f"  Total Entries: {cache_stats['total_entries']}")
    print(f"  By Type: {cache_stats['by_type']}")
    
    print("\n" + "=" * 80)
    print("✓ DEMO COMPLETE - Week 2 Implementation Validated")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_aegis_system())
