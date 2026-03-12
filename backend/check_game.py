from firestore_db import get_firestore_db
from google.cloud.firestore_v1.base_query import FieldFilter
db = get_firestore_db()

doc = list(db.collection('game_id_map').where(filter=FieldFilter('nba_id', '==', '0022500936')).stream())
if doc:
    print("Found in game_id_map:", doc[0].to_dict())
else:
    print("Not found in game_id_map by nba_id 0022500936")
    
# Check quarters/FINAL
q = db.collection('pulse_stats').document('2026-03-11').collection('games').document('0022500936').collection('quarters').document('FINAL').get()
if q.exists:
    print("Found FINAL quarter:", q.to_dict())
else:
    print("No FINAL quarter")
