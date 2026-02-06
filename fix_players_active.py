"""
Quick script to update all players with is_active field
"""
import sys
sys.path.insert(0, 'backend')
from firestore_db import get_firestore_db

db = get_firestore_db()
players_ref = db.collection('players')

print("Fetching all players...")
players = list(players_ref.stream())
print(f"Found {len(players)} players")

batch = db.batch()
count = 0
active_count = 0

for i, player in enumerate(players):
    data = player.to_dict()
    # Set is_active=True if player has a team_abbreviation
    has_team = bool(data.get('team_abbreviation'))
    
    batch.update(player.reference, {'is_active': has_team})
    count += 1
    if has_team:
        active_count += 1
    
    # Commit every 500 (Firestore limit)
    if count >= 500:
        batch.commit()
        print(f"  ✅ Committed batch {i//500 + 1} ({i+1}/{len(players)} players)")
        batch = db.batch()
        count = 0

# Commit remaining
if count > 0:
    batch.commit()
    print(f"  ✅ Committed final batch")

print(f"\n✅ Updated {len(players)} players")
print(f"   {active_count} marked as active (have team)")
print(f"   {len(players) - active_count} marked as inactive (no team)")
