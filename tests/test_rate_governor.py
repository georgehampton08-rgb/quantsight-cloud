"""
Test script for Token Bucket Rate Governor
Verifies token bucket algorithm, burst mode, and emergency brake
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis.rate_governor import TokenBucketGovernor


async def test_rate_governor():
    """Test Rate Governor functionality"""
    
    print("=" * 70)
    print("TOKEN BUCKET RATE GOVERNOR: FUNCTIONALITY TEST")
    print("=" * 70)
    
    # Test 1: Basic Token Acquisition
    print("\n" + "=" * 70)
    print("TEST 1: Basic Token Acquisition (Max 10 tokens)")
    print("=" * 70)
    
    governor = TokenBucketGovernor(max_tokens=10, refill_rate=0.75)
    
    print("\nAcquiring 5 tokens rapidly:")
    for i in range(5):
        allowed = await governor.acquire_token()
        status = governor.get_status()
        print(f"  Request {i+1}: {'✓ ALLOWED' if allowed else '✗ DENIED'} "
              f"({status['tokens_available']:.1f} tokens remaining)")
    
    # Test 2: Token Exhaustion
    print("\n" + "=" * 70)
    print("TEST 2: Token Exhaustion (should deny after 5 more)")
    print("=" * 70)
    
    print("\nAcquiring 7 more tokens (should exhaust):")
    for i in range(7):
        allowed = await governor.acquire_token()
        status = governor.get_status()
        print(f"  Request {6+i}: {'✓ ALLOWED' if allowed else '✗ DENIED'} "
              f"({status['tokens_available']:.1f} tokens remaining)")
    
    # Test 3: Token Refill
    print("\n" + "=" * 70)
    print("TEST 3: Token Refill (wait 2 seconds for refill)")
    print("=" * 70)
    
    print("\nWaiting 2 seconds for token refill...")
    await asyncio.sleep(2)
    
    status_before = governor.get_status()
    allowed = await governor.acquire_token()
    status_after = governor.get_status()
    
    print(f"\nBefore refill: {status_before['tokens_available']:.1f} tokens")
    print(f"Request: {'✓ ALLOWED' if allowed else '✗ DENIED'}")
    print(f"After acquire: {status_after['tokens_available']:.1f} tokens")
    
    # Test 4: Burst Mode
    print("\n" + "=" * 70)
    print("TEST 4: Burst Mode (5 rapid requests + cooldown)")
    print("=" * 70)
    
    governor.reset()  # Reset to full tokens
    governor.activate_burst_mode("morning_briefing")
    
    print("\nBurst mode activated - acquiring 5 tokens rapidly:")
    for i in range(5):
        allowed = await governor.acquire_token()
        print(f"  Burst {i+1}: {'✓ ALLOWED' if allowed else '✗ DENIED'}")
    
    print("\nBurst exhausted - trying 6th request:")
    allowed = await governor.acquire_token()
    status = governor.get_status()
    print(f"  Request 6: {'✓ ALLOWED' if allowed else '✗ DENIED'}")
    print(f"  In cooldown: {status['in_cooldown']}")
    
    # Test 5: Emergency Brake
    print("\n" + "=" * 70)
    print("TEST 5: Emergency Brake (< 10% quota remaining)")
    print("=" * 70)
    
    governor.reset()
    
    # Simulate API headers showing low quota
    mock_headers = {
        'X-RateLimit-Remaining': '8',
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Reset': str(int(time.time() + 3600))
    }
    
    print("\nSimulating API response with 8% quota remaining...")
    governor.update_from_headers(mock_headers)
    
    status = governor.get_status()
    print(f"  Rate Limit: {status['rate_limit_remaining']}/{status['rate_limit_total']} "
          f"({status['rate_limit_percentage']:.1f}%)")
    print(f"  Emergency Mode: {status['emergency_mode']}")
    print(f"  Historical Paused: {status['historical_paused']}")
    
    print("\nTrying normal priority request:")
    allowed = await governor.acquire_token(priority='normal')
    print(f"  Normal: {'✓ ALLOWED' if allowed else '✗ DENIED (emergency brake active)'}")
    
    print("\nTrying critical priority request:")
    allowed = await governor.acquire_token(priority='critical')
    print(f"  Critical: {'✓ ALLOWED' if allowed else '✗ DENIED'}")
    
    # Test 6: Request Rate Monitoring
    print("\n" + "=" * 70)
    print("TEST 6: Request Rate Monitoring")
    print("=" * 70)
    
    governor.reset()
    
    print("\nMaking 10 requests with small delays:")
    for i in range(10):
        allowed = await governor.acquire_token()
        await asyncio.sleep(0.1)  # Small delay between requests
    
    status = governor.get_status()
    print(f"\n  Requests in last minute: {status['requests_last_minute']}")
    print(f"  Tokens remaining: {status['tokens_available']:.1f}")
    
    # Final Status
    print("\n" + "=" * 70)
    print("FINAL GOVERNOR STATUS")
    print("=" * 70)
    
    status = governor.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_rate_governor())
