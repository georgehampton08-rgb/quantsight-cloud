from firestore_db import get_firestore_db
db = get_firestore_db()
pbp_count = len(list(db.collection('pbp_events').limit(10).stream()))
pbp2_count = len(list(db.collection('pbp_events_v2').limit(10).stream()))
print(f"pbp_events: {pbp_count}, pbp_events_v2: {pbp2_count}")
