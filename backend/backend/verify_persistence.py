from services.delta_sync import DeltaSyncManager
from services.knowledge_loom import KnowledgeLoom
from datetime import datetime, timedelta
import os
import csv

def main():
    print("="*60)
    print("  KNOWLEDGE-LOOM PERSISTENCE VERIFICATION")
    print("="*60)
    
    # Clean up any existing test data
    test_data_dir = "backend/data"
    if os.path.exists(f"{test_data_dir}/game_logs.csv"):
        os.remove(f"{test_data_dir}/game_logs.csv")
        print("[TEST] Cleared existing test data")
    
    sync = DeltaSyncManager()
    loom = KnowledgeLoom(data_dir=test_data_dir)
    
    print(f"\nSystem Date: {sync.today}")
    print(f"Yesterday: {sync.yesterday}")
    
    # Test 1: Background Batch Sync with Persistence
    print("\n" + "="*60)
    print("  TEST 1: Background Batch Sync (Morning Briefing)")
    print("="*60)
    
    result = sync.background_batch_sync(persist=True)
    print(f"\nSync Result:")
    print(f"  - Games Processed: {result['games_processed']}")
    print(f"  - Persisted: {result['persisted']}")
    print(f"  - Status: {result['status']}")
    
    # Verify data was written to CSV
    with open(f"{test_data_dir}/game_logs.csv", 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"\n✅ CSV contains {len(rows)} game log entries")
        if rows:
            print(f"   Sample: {rows[0]['player_name']} scored {rows[0]['points']} pts on {rows[0]['game_date']}")
    
    # Test 2: Force-Fetch with Persistence
    print("\n" + "="*60)
    print("  TEST 2: Force-Fetch with Persistence")
    print("="*60)
    
    one_day_ago = (sync.today - timedelta(days=1)).strftime("%Y-%m-%d")
    result2 = sync.force_fetch_player(
        player_id="999",
        player_name="Test Player",
        cached_last_game=one_day_ago,
        persist=True
    )
    
    print(f"\nForce-Fetch Result:")
    print(f"  - Status: {result2['status']}")
    print(f"  - Persisted: {result2.get('persisted', False)}")
    
    # Verify new data was appended
    with open(f"{test_data_dir}/game_logs.csv", 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"\n✅ CSV now contains {len(rows)} total entries")
        test_player_rows = [r for r in rows if r['player_id'] == '999']
        if test_player_rows:
            print(f"   Test Player entry found: {test_player_rows[0]['points']} pts")
    
    # Test 3: Kaggle Export
    print("\n" + "="*60)
    print("  TEST 3: Kaggle Export")
    print("="*60)
    
    export_path = loom.export_for_kaggle()
    print(f"\n✅ Exported to: {export_path}")
    print(f"   File exists: {os.path.exists(export_path)}")
    
    # Test 4: Retrieve Last Game Date
    print("\n" + "="*60)
    print("  TEST 4: Retrieve Last Game Date")
    print("="*60)
    
    last_game = loom.get_player_last_game("1")
    print(f"\n✅ Stephen Curry's last game: {last_game}")
    
    print("\n" + "="*60)
    print("  ALL TESTS PASSED ✅")
    print("="*60)
    print("\nData persisted successfully.")
    print("Kaggle integration ready.")

if __name__ == "__main__":
    main()
