import logging
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.nba_pbp_service import NBAPlayByPlayClient

logging.basicConfig(level=logging.INFO)

def test_pbp_service():
    client = NBAPlayByPlayClient()
    
    print("1. Fetching live game IDs from ESPN...")
    games = client.fetch_live_game_ids()
    print(f"Found {len(games)} games: {[g.get('game_id') for g in games]}")
    
    espn_id = games[0]['game_id'] if games else '401810734'
    print(f"\n2. Fetching Unified Plays for ESPN Game ID: {espn_id}...")
    try:
        plays = client.fetch_espn_plays(espn_id)
        if len(plays) > 0:
            print(f"[PASS] Successfully mapped {len(plays)} ESPN plays.")
            print(f"Sample Unified Play 1:\n{plays[0].model_dump_json(indent=2)}")
            print(f"Sample Unified Play Last:\n{plays[-1].model_dump_json(indent=2)}")
        else:
            print(f"[FAIL] 0 plays found for ESPN game {espn_id}")
    except Exception as e:
        print(f"[FAIL] ESPN mapping threw error: {e}")
        
    print("\n3. Testing NBA CDN Fallback mapping (Hardcoded ID 0022500858)...")
    try:
        cdn_plays = client.fetch_nba_cdn_plays("0022500858")
        if len(cdn_plays) > 0:
            print(f"[PASS] Successfully mapped {len(cdn_plays)} NBA CDN plays.")
            print(f"Sample Unified Play Last:\n{cdn_plays[-1].model_dump_json(indent=2)}")
        else:
            print("[FAIL] 0 plays found for NBA CDN")
    except Exception as e:
        print(f"[FAIL] NBA CDN mapping threw error: {e}")

if __name__ == "__main__":
    test_pbp_service()
