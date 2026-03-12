from firestore_db import get_firestore_db
from google.cloud.firestore_v1.base_query import FieldFilter
db = get_firestore_db()

def check_date(date_str):
    cal = list(db.collection('calendar').document(date_str).collection('games').stream())
    dmap = list(db.collection('game_id_map').where(filter=FieldFilter('date', '==', date_str)).stream())
    pstats = list(db.collection('pulse_stats').document(date_str).collection('games').stream())
    print(f"{date_str}: {len(cal)} calendar, {len(dmap)} map, {len(pstats)} pulse_stats")
    
    # Also check what /dates/ endpoint sees
    from api.play_by_play_routes import get_games_for_date_direct
    import asyncio
    try:
        res = asyncio.run(get_games_for_date_direct(date_str))
        print(f"API /dates/{date_str}: {res['count']} games returned")
    except Exception as e:
        print(f"API error: {e}")

check_date('2026-03-10')
check_date('2026-03-11')
