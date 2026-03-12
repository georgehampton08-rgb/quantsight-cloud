import sys
import os
import asyncio
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from main import app  # Assuming play_by_play_routes will be added to main.py

logging.basicConfig(level=logging.INFO)

def test_pbp_routes():
    # Wait, the route needs to be registered with main.py first. 
    # Let's import the router directly and test it on a dummy app instead if main.py is complicated.
    from fastapi import FastAPI
    from api.play_by_play_routes import router
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")

    client = TestClient(test_app)

    print("1. Testing GET /api/v1/games/live")
    res = client.get("/api/v1/games/live")
    print(f"Status: {res.status_code}")
    if res.status_code == 200:
        data = res.json()
        print(f"[PASS] Retrieved {len(data.get('games', []))} games from live route.")
    else:
        print(f"[FAIL] /live returned: {res.text}")

    game_id = "test_123"

    print("\n2. Testing POST /api/v1/games/{game_id}/start-tracking")
    res = client.post(f"/api/v1/games/{game_id}/start-tracking")
    if res.status_code == 200:
        print(f"[PASS] Tracking started: {res.json()}")
    else:
        print(f"[FAIL] start-tracking failed: {res.text}")

    print("\n3. Testing GET /api/v1/games/{game_id}/plays")
    # This queries Firestore cache
    res = client.get(f"/api/v1/games/{game_id}/plays")
    if res.status_code == 200:
        plays = res.json().get('plays', [])
        print(f"[PASS] Successfully fetched {len(plays)} cached plays from hydration endpoint.")
    else:
        print(f"[FAIL] /plays returned: {res.text}")

if __name__ == "__main__":
    test_pbp_routes()
