import logging
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.nba_pbp_service import NBAPlayByPlayClient
from services.firebase_pbp_service import FirebasePBPService

logging.basicConfig(level=logging.INFO)

def test_firebase_pbp():
    print("Testing Firebase PBP Service...")
    game_id = "test_game_999"
    
    metadata = {
        "status": "scheduled",
        "homeTeam": {"name": "Test Home"},
        "awayTeam": {"name": "Test Away"}
    }
    
    print("1. Saving metadata...")
    FirebasePBPService.save_game_metadata(game_id, metadata)
    print("[PASS] Saved metadata")
    
    # We need some dummy plays. Let's create two minimal PlayEvents
    from services.nba_pbp_service import PlayEvent
    plays = [
        PlayEvent(
            playId="999_1",
            sequenceNumber=1,
            eventType="test",
            description="Test play 1",
            period=1,
            clock="12:00",
            homeScore=0,
            awayScore=0,
            source="test"
        ),
        PlayEvent(
            playId="999_2",
            sequenceNumber=2,
            eventType="test",
            description="Test play 2",
            period=1,
            clock="11:45",
            homeScore=2,
            awayScore=0,
            source="test"
        )
    ]
    
    print("2. Batch saving plays...")
    FirebasePBPService.save_plays_batch(game_id, plays)
    print("[PASS] Batch saved plays")
    
    print("3. Fetching cached plays...")
    fetched_plays = FirebasePBPService.get_cached_plays(game_id)
    print(f"[PASS] Fetched {len(fetched_plays)} plays. Sequence check: {[p.get('sequenceNumber') for p in fetched_plays]}")
    
    print("4. Updating cache snapshot...")
    FirebasePBPService.update_cache_snapshot(game_id, len(fetched_plays), "2026-03-03T12:00:00Z")
    print("[PASS] snapshot updated")

if __name__ == "__main__":
    test_firebase_pbp()
