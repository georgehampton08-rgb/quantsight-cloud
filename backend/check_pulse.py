import json
from firestore_db import get_firestore_db
db = get_firestore_db()

docs = list(db.collection('pulse_stats').document('2026-03-11').collection('games').stream())
if docs:
    d = docs[0].to_dict()
    # convert datetime to string
    for k, v in d.items():
        d[k] = str(v)
    print("PULSE STATS DOC:")
    print(json.dumps(d, indent=2))
else:
    print("No pulse stats")
    
# Check pbp_events to see what IDs they use
docs = list(db.collection("pbp_events").limit(3).stream())
print("PBP_EVENTS IDs:", [d.id for d in docs])
