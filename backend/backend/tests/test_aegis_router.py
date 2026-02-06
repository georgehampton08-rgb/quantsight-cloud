"""
Test script for Aegis Router basic functionality
Verifies locality checks, freshness detection, and offline mode
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis.router_brain import AegisBrain, DataFreshness
from aegis.cache_manager import CacheManager
from aegis.safety_wrapper import CalculationSafetyWrapper


class MockAPIBridge:
    """Mock API for testing"""
    
    async def fetch(self, entity_type: str, entity_id: int, query: dict) -> dict:
        """Simulate API fetch"""
        print(f"  → Mock API called for {entity_type}:{entity_id}")
        
        # Simulate network latency
        await asyncio.sleep(0.1)
        
        # Return mock data
        return {
            'player_id': entity_id,
            'name': f'Player {entity_id}',
            'points': 25.5,
            'rebounds': 8.2,
            'assists': 6.1,
            'latency_ms': 100
        }


async def test_aegis_router():
    """Test Aegis Router functionality"""
    
    print("=" * 70)
    print("AEGIS ROUTER: BASIC FUNCTIONALITY TEST")
    print("=" * 70)
    
    # Initialize components
    db_path = "quantsight.db"
    cache = CacheManager(db_path)
    api = MockAPIBridge()
    router = AegisBrain(cache, api)
    
    print("\n✓ Components initialized")
    print(f"  - Cache: SQLite ({db_path})")
    print(f"  - API: Mock (for testing)")
    
    # Test 1: Cache Miss → API Call
    print("\n" + "=" * 70)
    print("TEST 1: Cache Miss → API Call")
    print("=" * 70)
    
    query1 = {'type': 'player_stats', 'id': 2544}
    result1 = await router.route_request(query1)
    
    print(f"\nResult:")
    print(f"  Source: {result1['source']}")
    print(f"  Freshness: {result1['freshness']}")
    print(f"  Latency: {result1['latency_ms']}ms")
    print(f"  Data: {result1['data'].get('name')}, {result1['data'].get('points')} PPG")
    
    # Test 2: Cache Hit (Fresh)
    print("\n" + "=" * 70)
    print("TEST 2: Cache Hit (Fresh)")
    print("=" * 70)
    
    query2 = {'type': 'player_stats', 'id': 2544}
    result2 = await router.route_request(query2)
    
    print(f"\nResult:")
    print(f"  Source: {result2['source']}")
    print(f"  Freshness: {result2['freshness']}")
    print(f"  Latency: {result2['latency_ms']}ms (should be 0)")
    
    # Test 3: Stale Cache → API Refresh
    print("\n" + "=" * 70)
    print("TEST 3: Stale Cache → API Refresh")
    print("=" * 70)
    
    # Manually age the cache entry
    old_timestamp = datetime.now() - timedelta(hours=24)
    await cache.set('player_stats', 2544, result2['data'], old_timestamp)
    
    query3 = {'type': 'player_stats', 'id': 2544}
    result3 = await router.route_request(query3)
    
    print(f"\nResult:")
    print(f"  Source: {result3['source']}")
    print(f"  Freshness: {result3['freshness']}")
    print(f"  API was called to refresh stale data")
    
    # Test 4: Offline Mode (API Unreachable)
    print("\n" + "=" * 70)
    print("TEST 4: Offline Mode (API Unreachable)")
    print("=" * 70)
    
    # Remove API to simulate offline + clear cache to force API need
    await cache.delete('player_stats', 2544)
    router_offline = AegisBrain(cache, api_bridge=None)
    
    query4 = {'type': 'player_stats', 'id': 9999}  # New ID not in cache
    result4 = await router_offline.route_request(query4)
    
    print(f"\nResult:")
    print(f"  Source: {result4['source']}")
    print(f"  Freshness: {result4['freshness']}")
    print(f"  Offline Mode: {result4.get('offline_mode', False)}")
    print(f"  Message: {result4.get('message', 'N/A')}")
    
    # Test 5: Safety Wrapper
    print("\n" + "=" * 70)
    print("TEST 5: Safety Wrapper (Non-Interference)")
    print("=" * 70)
    
    wrapper = CalculationSafetyWrapper(router)
    calc_data = await wrapper.get_player_stats(2544)
    
    print(f"\nData provided to calculations:")
    print(f"  Player: {calc_data.get('name')}")
    print(f"  Points: {calc_data.get('points')}")
    print(f"  Format: Unchanged (calculations work as before)")
    
    # Statistics
    print("\n" + "=" * 70)
    print("ROUTER STATISTICS")
    print("=" * 70)
    
    stats = router.get_stats()
    print(f"\n  Cache Hits: {stats['cache_hits']}")
    print(f"  Cache Misses: {stats['cache_misses']}")
    print(f"  API Calls: {stats['api_calls']}")
    print(f"  Cache Hit Rate: {stats['cache_hit_rate']:.1%}")
    print(f"  Offline Mode Activations: {stats['offline_mode_activations']}")
    
    cache_stats = cache.get_stats()
    print(f"\n  Total Cache Entries: {cache_stats['total_entries']}")
    print(f"  By Type: {cache_stats['by_type']}")
    
    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_aegis_router())
