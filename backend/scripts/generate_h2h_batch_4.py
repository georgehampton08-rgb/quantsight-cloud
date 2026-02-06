"""
H2H Data Generation - Batch 4 (Players 402-534)
==============================================
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import time
import logging
from services.h2h_fetcher import get_h2h_fetcher

logging.basicConfig(level=logging.INFO, format='[BATCH4] %(message)s')
logger = logging.getLogger(__name__)

BATCH_ID = 4
START_IDX = 402
END_IDX = 999  # Will stop at actual end
CLOUD_API = "https://quantsight-cloud-458498663186.us-central1.run.app"

def get_active_players():
    try:
        response = requests.get(f"{CLOUD_API}/players?is_active=true", timeout=30)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def main():
    logger.info(f"🚀 Starting BATCH {BATCH_ID} (players {START_IDX}+)")
    
    # Initialize Firebase for Firestore access
    import firebase_admin
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app()
            logger.info("✅ Firebase initialized")
        except Exception as e:
            logger.warning(f"Firebase init failed: {e}")
    
    fetcher = get_h2h_fetcher()
    
    all_players = get_active_players()
    if not all_players:
        logger.error("Failed to fetch players")
        return
    
    batch_players = all_players[START_IDX:]
    all_teams = sorted(list(set(p.get('team_abbreviation', '') for p in all_players if p.get('team_abbreviation'))))
    
    logger.info(f"Processing {len(batch_players)} players vs {len(all_teams)} teams")
    
    fetched = 0
    errors = 0
    start_time = time.time()
    
    for i, player in enumerate(batch_players, 1):
        player_id = str(player.get('player_id') or player.get('id'))
        player_team = player.get('team_abbreviation', '').upper()
        
        for opponent in all_teams:
            if opponent.upper() == player_team:
                continue
            
            try:
                result = fetcher.fetch_h2h(player_id, opponent)
                if result.get('success') and result.get('games_found', 0) > 0:
                    fetched += 1
            except Exception as e:
                errors += 1
            
            time.sleep(0.6)
        
        if i % 10 == 0:
            elapsed = time.time() - start_time
            logger.info(f"Progress: {i}/{len(batch_players)} | Fetched: {fetched} | Errors: {errors}")
    
    logger.info(f"✅ BATCH {BATCH_ID} COMPLETE - Fetched: {fetched}, Errors: {errors}")

if __name__ == "__main__":
    main()
