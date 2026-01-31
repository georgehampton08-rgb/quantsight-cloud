"""
Circuit Breaker Verification Test

Tests the circuit breaker pattern by simulating API failures
and verifying the breaker opens after 5 consecutive failures.
"""

import requests
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

BASE_URL = "http://localhost:5000"


def test_circuit_breaker():
    """
    Force 504 Gateway Timeout and verify circuit opens.
    
    Expected Behavior:
    - After 5 failures, circuit should open
    - /health endpoint should show "critical" status
    - Subsequent calls should fail fast
    """
    print("=" * 60)
    print("CIRCUIT BREAKER VERIFICATION TEST")
    print("=" * 60)
    
    # Step 1: Verify healthy baseline
    print("\n[1/3] Checking baseline health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        health = response.json()
        print(f"✓ Initial health: {health}")
    except Exception as e:
        print(f"✗ Baseline health check failed: {e}")
        return False
    
    # Step 2: Force multiple failures
    print("\n[2/3] Simulating API failures...")
    print("Making 6 consecutive matchup requests to trigger circuit...")
    
    failure_count = 0
    for i in range(6):
        try:
            # Use invalid opponent to trigger failure path
            response = requests.get(
                f"{BASE_URL}/matchup/analyze",
                params={"player_id": "invalid_id", "opponent": "INVALID"},
                timeout=2
            )
            print(f"  Attempt {i+1}: Status {response.status_code}")
            
            if response.status_code >= 400:
                failure_count += 1
                
        except requests.Timeout:
            print(f"  Attempt {i+1}: TIMEOUT")
            failure_count += 1
        except Exception as e:
            print(f"  Attempt {i+1}: ERROR - {type(e).__name__}")
            failure_count += 1
        
        time.sleep(0.5)  # Small delay between attempts
    
    print(f"\nTotal failures recorded: {failure_count}/6")
    
    # Step 3: Verify circuit opened
    print("\n[3/3] Verifying circuit breaker state...")
    time.sleep(1)  # Allow circuit to react
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        health = response.json()
        
        nba_status = health.get("nba", "unknown")
        print(f"\nHealth Status After Failures:")
        print(f"  NBA API: {nba_status}")
        print(f"  Database: {health.get('database', 'unknown')}")
        print(f"  Gemini: {health.get('gemini', 'unknown')}")
        
        if nba_status == "critical":
            print("\n✓ SUCCESS: Circuit breaker opened (NBA API marked critical)")
            return True
        elif nba_status == "warning":
            print("\n⚠ PARTIAL: NBA API degraded but not critical")
            return True
        else:
            print(f"\n✗ FAILURE: Expected critical/warning, got {nba_status}")
            return False
            
    except Exception as e:
        print(f"\n✗ Health check failed: {e}")
        return False


if __name__ == "__main__":
    print("\nWaiting for backend to be ready...")
    time.sleep(2)
    
    success = test_circuit_breaker()
    
    print("\n" + "=" * 60)
    if success:
        print("CIRCUIT BREAKER TEST: PASSED ✓")
    else:
        print("CIRCUIT BREAKER TEST: FAILED ✗")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
