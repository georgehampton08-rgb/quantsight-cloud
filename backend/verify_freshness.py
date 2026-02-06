from services.schedule_scout import ScheduleScout
from datetime import datetime, timedelta
import json
import sys

def main():
    scout = ScheduleScout()
    
    # Setup Dates
    yesterday_str = scout.yesterday.strftime("%Y-%m-%d")
    three_days_ago_str = (scout.yesterday - timedelta(days=3)).strftime("%Y-%m-%d")
    
    print(f"[TEST] System Date: {scout.today}")
    print(f"[TEST] Target Freshness Date (Yesterday): {yesterday_str}")
    
    # Mock Players with "Expected" Dates (Simulating Schedule API knowledge)
    dummy_players = [
        {
            "id": "2544", 
            "name": "LeBron James", 
            "last_game_date": yesterday_str,
            "expected_active_date": yesterday_str
        },
        {
            "id": "201939", 
            "name": "Stephen Curry", 
            "last_game_date": three_days_ago_str,
            "expected_active_date": three_days_ago_str # Matches stored, so should be FRESH (even if old)
        },
        {
            "id": "12345",
            "name": "Missing Player",
            "last_game_date": three_days_ago_str,
            "expected_active_date": yesterday_str # Stored is older than expected -> STALE
        }
    ]
    
    print("\n[TEST] Running Audit (Smart Mode)...")
    manifest = scout.generate_manifest(dummy_players)
    
    print("\n" + "="*40)
    print("       STATUS MANIFEST (PREVIEW)       ")
    print("="*40)
    print(json.dumps(manifest, indent=2))
    print("="*40)
    
    # Verification Assertions
    lebron = next(p for p in manifest['freshness_audit'] if p['name'] == "LeBron James")
    curry = next(p for p in manifest['freshness_audit'] if p['name'] == "Stephen Curry")
    missing = next(p for p in manifest['freshness_audit'] if p['name'] == "Missing Player")
    
    # Logic: 
    # LeBron: Stored(Yest) == Expected(Yest) -> FRESH
    # Curry: Stored(3 Days Info) == Expected(Last Game was 3 Days Ago) -> FRESH (Correct User Logic)
    # Missing: Stored(3 Days) < Expected(Yest) -> STALE
    
    if lebron['status'] == "FRESH" and curry['status'] == "FRESH" and "STALE" in missing['status']:
        print("\n✅ VERIFICATION PASSED: Smart Logic holds.")
    else:
        print("\n❌ VERIFICATION FAILED: Logic Error detected.")
        print(f"LeBron: {lebron['status']}")
        print(f"Curry: {curry['status']}")
        print(f"Missing: {missing['status']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
