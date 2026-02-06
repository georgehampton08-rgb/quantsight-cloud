import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from firestore_db import get_firestore_db

db = get_firestore_db()

# Check matchups collection
matchups = list(db.collection('matchups').stream())
print(f"Matchups dates found: {len(matchups)}")

if matchups:
    for date_doc in matchups[:3]:
        print(f"\nDate: {date_doc.id}")
        games = list(db.collection('matchups').document(date_doc.id).collection('games').stream())
        print(f"  Games: {len(games)}")
        for game in games[:2]:
            gdata = game.to_dict()
            print(f"    {gdata.get('matchup')}: H={gdata.get('home_player_count')} A={gdata.get('away_player_count')}")
else:
    print("\n❌ NO DATA IN MATCHUPS COLLECTION")
    
    # Debug: check game_logs
    logs = list(db.collection('game_logs').limit(5).stream())
    print(f"\nDebug: game_logs has {len(logs)} docs")
    if logs:
        sample = logs[0].to_dict()
        print(f"Sample log fields: {list(sample.keys())}")
        print(f"Sample game_date: '{sample.get('game_date', 'MISSING')}'")
        print(f"Sample game_id: '{sample.get('game_id', 'MISSING')}'")
