"""
Mark all non-active players as inactive in Firestore
This ensures only current 2024-25 roster players show as active
"""
import sys
sys.path.insert(0, 'backend')
from firestore_db import get_firestore_db

db = get_firestore_db()

print("🔄 Marking all players without teams as inactive...")

# Get all players
players_ref = db.collection('players')
all_players = list(players_ref.stream())

print(f"Found {len(all_players)} total players")

batch = db.batch()
count = 0
inactive_count = 0
active_count = 0

for player in all_players:
    data = player.to_dict()
    
    # If no team_abbreviation, mark as inactive
    if not data.get('team_abbreviation'):
        batch.update(player.reference, {'is_active': False})
        inactive_count += 1
        count += 1
    else:
        active_count += 1
    
    # Commit every 500
    if count >= 500:
        batch.commit()
        print(f"  ✅ Committed batch ({inactive_count} marked inactive so far)")
        batch = db.batch()
        count = 0

# Commit remaining
if count > 0:
    batch.commit()

print(f"\n✅ Complete!")
print(f"  Active players (with teams): {active_count}")
print(f"  Inactive players (no teams): {inactive_count}")
print(f"  Total players: {len(all_players)}")
