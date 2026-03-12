from firestore_db import get_firestore_db
db = get_firestore_db()
docs = list(db.collection('pulse_stats').document('2026-03-11').collection('games').stream())
if docs:
    for k, v in docs[0].to_dict().items():
        if isinstance(v, dict):
            print(f"{k}: TYPE=DICT KEYS={list(v.keys())}")
        else:
            print(f"{k}: {str(v)[:100]}")
else:
    print("No pulse_stats docs found for 03-11")
