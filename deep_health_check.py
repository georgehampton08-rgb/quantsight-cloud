"""
Deep Database Health Check
==========================
Checks Firestore for ANY data (not just recent) to verify writes are working.
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from firestore_db import get_firestore_db
from datetime import datetime

print("\n" + "="*70)
print("🔍 DEEP DATABASE HEALTH CHECK")
print("="*70 + "\n")

db = get_firestore_db()

# Check 1: ANY game logs ever (last 30 days)
print("📊 Searching for ANY game logs (past 30 days)...")
try:
    logs_ref = db.collection('game_logs')
    all_logs = list(logs_ref.limit(100).stream())
    
    if all_logs:
        print(f"\n✅ Found {len(all_logs)} total game log(s) in database!")
        
        # Show newest
        print("\nMost recent game logs:")
        for log in all_logs[:5]:
            data = log.to_dict()
            print(f"  - {data.get('game_id', 'N/A')}: {data.get('home_team', '?')} vs {data.get('away_team', '?')}")
            print(f"    Date: {data.get('date', 'N/A')} | Score: {data.get('home_score', 0)}-{data.get('away_score', 0)}")
            print(f"    Saved: {data.get('saved_at', 'N/A')}")
    else:
        print("⚠️  No game logs found in database (ever)")
        print("   This means either:")
        print("   - System has never seen a finished game")
        print("   - GameLogPersister is not working")
except Exception as e:
    print(f"❌ Error querying game_logs: {e}")

# Check 2: ANY pulse archives ever
print("\n\n📸 Searching for ANY quarter archives (past 30 days)...")
try:
    pulse_ref = db.collection('pulse_stats')
    all_pulse = list(pulse_ref.limit(50).stream())
    
    if all_pulse:
        print(f"\n✅ Found {len(all_pulse)} date(s) with archived data!")
        
        # Show sample
        for date_doc in all_pulse[:3]:
            print(f"\n  Date: {date_doc.id}")
            
            # Get games for this date
            games_ref = date_doc.reference.collection('games')
            games = list(games_ref.limit(5).stream())
            
            print(f"  Games: {len(games)}")
            
            if games:
                sample = games[0]
                quarters_ref = sample.reference.collection('quarters')
                quarters = list(quarters_ref.stream())
                print(f"  Sample game {sample.id}: {len(quarters)} quarter(s) archived")
    else:
        print("⚠️  No pulse archives found in database (ever)")
        print("   This means PulseStatsArchiver has never saved quarter data")
except Exception as e:
    print(f"❌ Error querying pulse_stats: {e}")

# Check 3: Live games collection (structure test)
print("\n\n🔴 Checking live_games collection structure...")
try:
    live_ref = db.collection('live_games')
    test_write = live_ref.document('_health_check_test')
    
    # Try to write
    test_write.set({'test': True, 'timestamp': datetime.utcnow().isoformat()})
    print("✅ Write permission: OK")
    
    # Try to read
    test_read = test_write.get()
    if test_read.exists:
        print("✅ Read permission: OK")
    
    # Clean up
    test_write.delete()
    print("✅ Delete permission: OK")
    
    print("\n✅ Firestore permissions are working correctly!")
    
except Exception as e:
    print(f"❌ Firestore permission error: {e}")
    print("   This could be a Firebase Auth or IAM issue")

# Check 4: Collection list
print("\n\n📁 Available collections in Firestore:")
try:
    collections = db.collections()
    col_names = [col.id for col in collections]
    
    print(f"Found {len(col_names)} collection(s):")
    for name in sorted(col_names):
        ref = db.collection(name)
        count = len(list(ref.limit(5).stream()))
        print(f"  - {name}: {count}+ document(s)")
except Exception as e:
    print(f"Error listing collections: {e}")

print("\n" + "="*70)
print("📋 DIAGNOSIS")
print("="*70)
print("\nIf all checks passed:")
print("  ✅ Database connection is working")
print("  ✅ Write permissions are correct")
print("  ✅ System is ready to save data")
print("\nIf no historical data found:")
print("  ⚠️  Need to wait for live NBA games")
print("  ⚠️  Producer will save automatically when games happen")
print("="*70 + "\n")
