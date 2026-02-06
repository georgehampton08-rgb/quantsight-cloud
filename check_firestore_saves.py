"""
Firestore Game Persistence Verification
======================================
Checks if game stats are being saved incrementally to Firestore.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from firestore_db import get_firestore_db
from datetime import datetime, timedelta

print("\n" + "="*70)
print("🔍 FIRESTORE GAME PERSISTENCE VERIFICATION")
print("="*70 + "\n")

db = get_firestore_db()

# Check 1: Recent Game Logs (Finished Games)
print("📊 Checking game_logs collection (finished games)...")
found_logs = False

for days_ago in range(7):
    check_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    
    try:
        # Direct query on game_logs collection
        logs_ref = db.collection('game_logs')
        query = logs_ref.where('date', '==', check_date).limit(10)
        docs = list(query.stream())
        
        if docs:
            print(f"\n✅ {check_date}: Found {len(docs)} game log(s)")
            found_logs = True
            
            # Show sample
            sample = docs[0].to_dict()
            print(f"   Example: {sample.get('game_id', 'N/A')}")
            print(f"   Teams: {sample.get('home_team', '?')} vs {sample.get('away_team', '?')}")
            print(f"   Score: {sample.get('home_score', 0)}-{sample.get('away_score', 0)}")
            break
    except Exception as e:
        print(f"   Error for {check_date}: {e}")

if not found_logs:
    print("\n⚠️  No game logs found in past 7 days")
    print("   (Normal if no games have finished recently)\n")

# Check 2: Quarter Archives (Incremental)
print("\n📸 Checking pulse_stats collection (quarter archives)...")
found_archives = False

for days_ago in range(3):
    check_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    
    try:
        # Check pulse_stats/{date}/games structure
        date_doc = db.collection('pulse_stats').document(check_date)
        
        if date_doc.get().exists:
            games_ref = date_doc.collection('games')
            games = list(games_ref.limit(5).stream())
            
            if games:
                print(f"\n✅ {check_date}: Found {len(games)} archived game(s)")
                found_archives = True
                
                # Show sample quarter
                sample_game = games[0]
                quarters_ref = sample_game.reference.collection('quarters')
                quarters = list(quarters_ref.stream())
                
                print(f"   Game: {sample_game.id}")
                print(f"   Quarters: {', '.join([q.id for q in quarters])}")
                break
    except Exception as e:
        print(f"   Error for {check_date}: {e}")

if not found_archives:
    print("\n⚠️  No quarter archives found in past 3 days")
    print("   (Normal if no live games had quarter transitions)\n")

# Check 3: Live Games Collection
print("\n🔴 Checking live_games collection (current state)...")

try:
    live_ref = db.collection('live_games')
    live_games = list(live_ref.limit(5).stream())
    
    if live_games:
        print(f"\n✅ Found {len(live_games)} live game(s) in Firestore")
        
        for game_doc in live_games[:2]:
            game = game_doc.to_dict()
            print(f"\n   {game.get('game_id', 'N/A')}: {game.get('home_team', '?')} vs {game.get('away_team', '?')}")
            print(f"   Score: {game.get('home_score', 0)}-{game.get('away_score', 0)} | Q{game.get('period', 0)} | {game.get('status', 'N/A')}")
    else:
        print("   ⚠️  No live games (normal if no NBA games in progress)")
except Exception as e:
    print(f"   Error: {e}")

# Summary
print("\n" + "="*70)
print("📋 SUMMARY")
print("="*70)
print(f"Game Logs (Finished): {'✅ Found' if found_logs else '⚠️  Not found'}")
print(f"Quarter Archives:     {'✅ Found' if found_archives else '⚠️  Not found'}")
print("\n💡 Run during live NBA games to see real-time incremental saves")
print("="*70 + "\n")
