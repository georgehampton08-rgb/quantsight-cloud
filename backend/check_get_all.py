from firestore_db import get_firestore_db
db = get_firestore_db()
doc = db.collection('game_id_map').document('0022500947').get()
if doc.exists:
    d = doc.to_dict()
    print("NBA ID DOC:", d)
else:
    print("NO NBA ID DOC")

doc = db.collection('game_id_map').document('401810802').get()
if doc.exists:
    d = doc.to_dict()
    print("ESPN ID DOC:", d)
else:
    print("NO ESPN DOC")
    
# Let's see pulse stats for 03-11
pulse_docs = list(db.collection('pulse_stats').document('2026-03-11').collection('games').stream())
for d in pulse_docs:
    print("PULSE STATS GAME:", d.id, d.to_dict().get('away_team'), d.to_dict().get('home_team'))
