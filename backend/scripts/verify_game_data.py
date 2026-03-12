import argparse
import sys
import logging
from datetime import datetime, timedelta

# Import Cloud infrastructure functions
import os
import sys

# Add the backend directory to sys.path so we can import firestore_db
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

try:
    from firestore_db import get_firestore_db
except ImportError:
    print("Fatal: Could not import get_firestore_db. Ensure you run this from the backend directory.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def verify_date(db, date_str: str) -> bool:
    """Verifies game data integrity for a single date."""
    logger.info(f"--- Verifying Data Integrity for Date: {date_str} ---")
    
    issues_found = False
    
    from google.cloud.firestore_v1.base_query import FieldFilter
    
    # 1. Fetch game_id_map for this date
    mapped_nba_ids = {}
    mapped_espn_ids = set()
    map_docs = db.collection("game_id_map").where(filter=FieldFilter("date", "==", date_str)).stream()
    for doc in map_docs:
        d = doc.to_dict()
        nba_id = d.get("nba_id")
        espn_id = d.get("espn_id")
        if nba_id:
            mapped_nba_ids[nba_id] = espn_id
        if espn_id:
            mapped_espn_ids.add(espn_id)
            
    logger.info(f"Indices: Found {len(mapped_nba_ids)} NBA IDs and {len(mapped_espn_ids)} ESPN IDs mapped strictly to {date_str}.")

    # 2. Check pulse_stats timezone bleed
    pulse_docs = list(db.collection("pulse_stats").document(date_str).collection("games").stream())
    pulse_nba_ids = [doc.id for doc in pulse_docs]
    
    logger.info(f"Raw Pulse Data: Found {len(pulse_nba_ids)} games recorded in pulse_stats on {date_str} (UTC).")
    
    bled_games = []
    for nba_id in pulse_nba_ids:
        # Check where this game is ACtUALLY mapped
        doc = db.collection("game_id_map").document(nba_id).get()
        if doc.exists:
            actual_date = doc.to_dict().get("date")
            if actual_date and actual_date != date_str:
                bled_games.append((nba_id, actual_date))
                
    if bled_games:
        logger.warning(f"TIMEZONE BLEED DETECTED: {len(bled_games)} games found in {date_str} pulse_stats but actually belong to previous/next days via game_id_map.")
        for bg in bled_games:
            logger.warning(f"  - NBA ID {bg[0]} belongs to {bg[1]}")
            
    # 3. Check for unmapped games (Missing ESPN IDs)
    unmapped = []
    for nba_id in pulse_nba_ids:
        if nba_id not in mapped_nba_ids and not db.collection("game_id_map").document(nba_id).get().exists:
             unmapped.append(nba_id)
             
    if unmapped:
         logger.warning(f"UNMAPPED GAMES DETECTED: {len(unmapped)} games in pulse_stats have no entry in game_id_map.")
         # Not strictly a failure if polling just started, but worth flagging
         issues_found = True
         
    # 4. Verify PBP data actually exists for matched ESPN IDs
    pbp_missing = []
    for espn_id in mapped_espn_ids:
        if not espn_id: continue
        events_ref = list(db.collection("pbp_events").document(espn_id).collection("events").limit(1).stream())
        if not events_ref:
            pbp_missing.append(espn_id)
            
    if pbp_missing:
        logger.error(f"PBP DATA MISSING: {len(pbp_missing)} ESPN games are mapped but possess ZERO play-by-play events.")
        for pid in pbp_missing:
            logger.error(f"  - Missing PBP for regular game: {pid}")
        issues_found = True
        
    return not issues_found

def main():
    parser = argparse.ArgumentParser(description="Verify QuantSight game data integrity (mappings, timezone bleed, PBP consistency).")
    parser.add_argument("--date", type=str, help="Specific date to check (YYYY-MM-DD). Defaults to yesterday.")
    parser.add_argument("--days", type=int, default=1, help="Number of previous days to check if --date is omitted.")
    args = parser.parse_args()
    
    db = get_firestore_db()
    
    dates_to_check = []
    if args.date:
        dates_to_check.append(args.date)
    else:
        # Default to checking recent history
        today = datetime.now()
        for i in range(1, args.days + 1):
            d = today - timedelta(days=i)
            dates_to_check.append(d.strftime("%Y-%m-%d"))
            
    all_passed = True
    for d in dates_to_check:
        passed = verify_date(db, d)
        if not passed:
             logger.error(f"Verification FAILED for {d}")
             all_passed = False
        else:
             logger.info(f"Verification PASSED for {d}\n")
             
    if not all_passed:
        logger.error("One or more dates failed data integrity checks.")
        sys.exit(1)
    else:
        logger.info("All selected dates passed data integrity verification cleanly.")
        sys.exit(0)

if __name__ == "__main__":
    main()
