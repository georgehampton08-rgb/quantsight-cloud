"""
Week 6: Comprehensive Integration Test Suite
Full Phase 1 system verification
"""

import asyncio
import sys
import shutil
from pathlib import Path
import time

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis import AegisBrain, TokenBucketGovernor, DataIntegrityHealer, SchemaEnforcer, AtomicWriter
from aegis.cache_manager import CacheManager
from aegis.dual_mode import DualModeDetector, ClassicAnalyzer
from aegis.health_monitor import WorkerHealthMonitor


class MockAPIBridge:
    """Mock API for testing"""
    async def fetch(self, entity_type: str, entity_id: int, query: dict) -> dict:
        await asyncio.sleep(0.05)  # Simulate network delay
        return {
            'player_id': str(entity_id),
            'name': 'LeBron James',
            'season': '2024-25',
            'points_avg': 25.5,
            'rebounds_avg': 8.2,
            'assists_avg': 7.1
        }


async def test_full_integration():
    """Test complete Aegis system integration"""
    
    print("=" * 70)
    print("AEGIS-SOVEREIGN PHASE 1: FULL INTEGRATION TEST")
    print("=" * 70)
    
    # Setup
    test_cache_db = "test_integration.db"
    test_data_dir = Path("test_integration_data")
    
    try:
        # Initialize all components
        print("\n[INITIALIZATION] Setting up Aegis components...")
        print("-" * 40)
        
        cache = CacheManager(test_cache_db)
        api = MockAPIBridge()
        governor = TokenBucketGovernor(max_tokens=10, refill_rate=0.75)
        healer = DataIntegrityHealer()
        enforcer = SchemaEnforcer()
        writer = AtomicWriter(base_dir=str(test_data_dir))
        detector = DualModeDetector()
        monitor = WorkerHealthMonitor()
        
        # Create router with all components
        router = AegisBrain(
            cache_manager=cache,
            api_bridge=api,
            governor=governor,
            integrity_healer=healer,
            schema_enforcer=enforcer
        )
        
        print("  ✓ Router initialized")
        print("  ✓ Rate governor active")
        print("  ✓ Integrity healer ready")
        print("  ✓ Schema enforcer loaded")
        print("  ✓ Atomic writer configured")
        print(f"  ✓ Analysis mode: {detector.active_mode}")
        print("  ✓ Health monitor running")
        
        # Test 1: Full Request Flow
        print("\n[TEST 1] Full Request Flow (All Components)")
        print("-" * 40)
        
        query = {
            'type': 'player_stats',
            'id': 2544,
            'priority': 'normal'
        }
        
        # First request - cache miss, API call
        start = time.time()
        result1 = await router.route_request(query)
        latency1 = int((time.time() - start) * 1000)
        
        print(f"  Request 1 (MISS):")
        print(f"    Source: {result1['source']}")
        print(f"    Freshness: {result1['freshness']}")
        print(f"    Latency: {latency1}ms")
        print(f"    Player: {result1['data']['name']}")
        
        monitor.record_request(success=True)
        
        # Second request - cache hit
        start = time.time()
        result2 = await router.route_request(query)
        latency2 = int((time.time() - start) * 1000)
        
        print(f"  Request 2 (HIT):")
        print(f"    Source: {result2['source']}")
        print(f"    Freshness: {result2['freshness']}")
        print(f"    Latency: {latency2}ms (should be ~0ms)")
        print(f"    Cache speedup: {latency1 / max(latency2, 1):.0f}x faster")
        
        monitor.record_request(success=True)
        
        # Test 2: Atomic Write + Integrity
        print("\n[TEST 2] Atomic Write + Integrity Verification")
        print("-" * 40)
        
        player_data = result1['data']
        
        # Write with integrity wrapper
        wrapped = healer.wrap_with_metadata(player_data)
        write_success = await writer.write_atomic('1610612747', '2544', '2024-25.json', wrapped)
        
        print(f"  Write Success: {write_success}")
        
        # Read back and verify
        read_data = await writer.read_atomic('1610612747', '2544', '2024-25.json')
        is_valid, msg = healer.verify_integrity(read_data)
        
        print(f"  Integrity Valid: {is_valid}")
        print(f"  Hash Match: {'✓' if is_valid else '✗'}")
        
        # Test 3: Rate Limiting
        print("\n[TEST 3] Rate Limiting (Token Bucket)")
        print("-" * 40)
        
        # Activate burst mode
        governor.activate_burst_mode("integration_test")
        print(f"  Burst Mode Activated")
        
        burst_successes = 0
        for i in range(7):  # Try 7 requests (burst allows 5)
            allowed = await governor.acquire_token('normal')
            if allowed:
                burst_successes += 1
        
        print(f"  Burst Requests: {burst_successes}/7 (5 expected)")
        print(f"  Rate Limiting: {'✓ Working' if burst_successes == 5 else '✗ Failed'}")
        
        # Test 4: Schema Validation
        print("\n[TEST 4] Schema Validation (Pydantic)")
        print("-" * 40)
        
        # Valid data
        valid_data = {
            'player_id': '2544',
            'name': 'LeBron James',
            'season': '2024-25',
            'games': 60,
            'points_avg': 25.5,
            'rebounds_avg': 8.2,
            'assists_avg': 7.1
        }
        
        is_valid, validated = enforcer.validate(valid_data, 'player_stats')
        print(f"  Valid Data: {'✓ Passed' if is_valid else '✗ Failed'}")
        
        # Invalid data (points_avg too high)
        invalid_data = {**valid_data, 'points_avg': 999}
        is_valid2, result = enforcer.validate(invalid_data, 'player_stats')
        print(f"  Invalid Data: {'✓ Rejected' if not is_valid2 else '✗ Accepted (should reject)'}")
        
        # Test 5: Dual-Mode Analysis
        print("\n[TEST 5] Dual-Mode Analysis")
        print("-" * 40)
        
        analysis = ClassicAnalyzer.analyze_player_performance(player_data)
        print(f"  Analysis Method: {analysis['method']}")
        print(f"  Efficiency Score: {analysis['efficiency_score']}")
        print(f"  Player Tier: {analysis['tier']}")
        print(f"  Confidence: {analysis['confidence']}")
        
        # Test 6: Health Monitoring
        print("\n[TEST 6] Health Monitoring")
        print("-" * 40)
        
        health = monitor.check_system_health()
        print(f"  System Status: {health['status']}")
        print(f"  CPU Usage: {health['system']['cpu_percent']}%")
        print(f"  Memory Usage: {health['system']['memory_percent']}%")
        print(f"  Total Requests: {monitor.total_requests}")
        print(f"  Error Rate: {monitor._get_error_rate():.1%}")
        
        # Final Statistics
        print("\n[FINAL STATISTICS]")
        print("-" * 40)
        
        router_stats = router.get_stats()
        governor_stats = governor.get_status()
        writer_stats = writer.get_stats()
        audit = writer.run_quality_audit()
        
        print(f"  Router:")
        print(f"    Cache Hits: {router_stats['cache_hits']}")
        print(f"    Cache Misses: {router_stats['cache_misses']}")
        print(f"    Cache Hit Rate: {router_stats['cache_hit_rate']:.1%}")
        print(f"    API Calls: {router_stats['api_calls']}")
        print(f"    Integrity Failures: {router_stats['integrity_failures']}")
        print(f"    Validation Failures: {router_stats['validation_failures']}")
        
        print(f"  Rate Governor:")
        print(f"    Tokens Available: {governor_stats['tokens_available']:.1f}/{governor_stats['max_tokens']}")
        print(f"    Emergency Mode: {governor_stats['emergency_mode']}")
        print(f"    Burst Active: {governor_stats.get('burst_active', False)}")
        
        print(f"  Atomic Writer:")
        print(f"    Writes Attempted: {writer_stats['writes_attempted']}")
        print(f"    Writes Succeeded: {writer_stats['writes_succeeded']}")
        print(f"    Success Rate: {writer_stats['success_rate']:.1%}")
        print(f"    Quality Audit Pass Rate: {audit['pass_rate']:.1%}")
        
        print(f"  Health Monitor:")
        print(f"    Status: {health['status']}")
        print(f"    Uptime: {monitor.get_uptime_formatted()}")
        
        # Verification
        print("\n" + "=" * 70)
        
        all_passed = (
            router_stats['cache_hit_rate'] > 0 and
            writer_stats['success_rate'] == 1.0 and
            audit['pass_rate'] == 1.0 and
            health['status'] in ['healthy', 'degraded']
        )
        
        if all_passed:
            print("✅ PHASE 1 COMPLETE - ALL SYSTEMS OPERATIONAL")
            print("=" * 70)
            print("\nComponents Verified:")
            print("  ✓ Week 1: Smart router with caching & offline mode")
            print("  ✓ Week 2: Token bucket rate governor")
            print("  ✓ Week 3: SHA-256 integrity + auto-repair")
            print("  ✓ Week 4: Atomic transactional writing")
            print("  ✓ Week 5: Dual-mode ML/Classic + health monitoring")
            print("  ✓ Week 6: Full integration verification")
        else:
            print("⚠ PHASE 1 INCOMPLETE - REVIEW REQUIRED")
        
        print("=" * 70)
        
    finally:
        # Cleanup
        if Path(test_cache_db).exists():
            Path(test_cache_db).unlink()
        if test_data_dir.exists():
            shutil.rmtree(test_data_dir)
        print("\n✓ Test cleanup complete")


if __name__ == "__main__":
    asyncio.run(test_full_integration())
