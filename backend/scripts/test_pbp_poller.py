import os
import sys
import asyncio
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.pbp_polling_service import pbp_polling_manager
import time

logging.basicConfig(level=logging.INFO)

async def test_poller():
    # Test tracking initialization
    game_id = "401810734" # the ESPN finished game we found earlier
    
    print("1. Starting tracker for game...")
    await pbp_polling_manager.start_tracking(game_id)
    
    print("2. Current tracked games:", pbp_polling_manager.get_tracked_games())
    
    print("3. Subscribing to SSE queue...")
    q = pbp_polling_manager.subscribe_sse(game_id)
    
    print("4. Waiting for first poll event...")
    try:
        # We wait up to 15 seconds for the queue to get populated by the poll loop
        new_plays = await asyncio.wait_for(q.get(), timeout=15.0)
        print(f"[PASS] SSE Queue received payload containing {len(new_plays)} plays.")
    except asyncio.TimeoutError:
        print("[FAIL] SSE Queue timed out waiting for payload.")
        
    print("5. Stopping tracker...")
    pbp_polling_manager.stop_tracking(game_id)
    print("Current tracked games after stop:", pbp_polling_manager.get_tracked_games())

if __name__ == "__main__":
    asyncio.run(test_poller())
