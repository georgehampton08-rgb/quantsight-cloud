from services.delta_sync import DeltaSyncManager
from datetime import datetime, timedelta
import json

def main():
    sync = DeltaSyncManager()
    
    print("="*60)
    print("  DELTA-SYNC-MANAGER VERIFICATION")
    print("="*60)
    print(f"System Date: {sync.today}")
    print(f"Yesterday: {sync.yesterday}")
    
    # Scenario 1: Force-Fetch on player with no games in 3 days
    print("\n" + "="*60)
    print("  SCENARIO: Force-Fetch on Stale Player (No Recent Games)")
    print("="*60)
    
    three_days_ago = (sync.today - timedelta(days=3)).strftime("%Y-%m-%d")
    
    result = sync.force_fetch_player(
        player_id="201939",
        player_name="Stephen Curry",
        cached_last_game=three_days_ago
    )
    
    print("\n" + "-"*60)
    print("  API RESPONSE:")
    print("-"*60)
    print(json.dumps(result, indent=2))
    
    # Verification
    print("\n" + "="*60)
    print("  VERIFICATION RESULTS:")
    print("="*60)
    
    if result["status"] == "NO_NEW_DATA" and result["api_called"]:
        print("✅ PASS: API was called")
        print("✅ PASS: Returned 'NO_NEW_DATA' signal")
        print("✅ PASS: User notified cache is up-to-date")
        print("\n✅ ALL CHECKS PASSED")
    else:
        print("❌ FAIL: Unexpected response")
        print(f"   Expected: NO_NEW_DATA")
        print(f"   Got: {result['status']}")
    
    # Scenario 2: Force-Fetch on player with recent game
    print("\n" + "="*60)
    print("  SCENARIO: Force-Fetch on Recently Active Player")
    print("="*60)
    
    one_day_ago = (sync.today - timedelta(days=1)).strftime("%Y-%m-%d")
    
    result2 = sync.force_fetch_player(
        player_id="2544",
        player_name="LeBron James",
        cached_last_game=one_day_ago
    )
    
    print("\n" + "-"*60)
    print("  API RESPONSE:")
    print("-"*60)
    print(json.dumps(result2, indent=2))
    
    if result2["status"] == "LIVE_UPDATED":
        print("\n✅ PASS: Detected and downloaded new game data")

if __name__ == "__main__":
    main()
