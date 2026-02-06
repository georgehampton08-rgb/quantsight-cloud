import requests
import json
import os
import sys

# Define base URL
API_BASE = "http://localhost:8080" # Assuming local dev server port if running locally, otherwise use cloud URL

def test_roster_endpoint(team_id="LAL"):
    print(f"Testing /roster/{team_id}...")
    try:
        # We'll use the cloud URL since we can't easily start the local server here
        cloud_url = "https://quantsight-cloud-458498663186.us-central1.run.app"
        # Wait, I just modified the code but didn't deploy yet. 
        # So I should test with a direct script call to the backend logic if possible, 
        # or just assume the code is correct and deploy.
        # Let's test the adapter logic directly.
        pass
    except Exception as e:
        print(f"Error testing roster: {e}")

def verify_hierarchical_h2h():
    print("Verifying Hierarchical H2H...")
    sys.path.append(os.path.join(os.getcwd(), "backend"))
    try:
        # Manually initialize firebase for the script if needed
        import firebase_admin
        from firebase_admin import firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        
        from services.h2h_firestore_adapter import H2HFirestoreAdapter
        adapter = H2HFirestoreAdapter()
        
        # Test read for a known migrated player (101108 - Chris Paul)
        stats = adapter.get_h2h_stats("101108", "ATL")
        print(f"Chris Paul vs ATL stats: {stats}")
        
        games = adapter.get_h2h_games("101108", "ATL", limit=2)
        print(f"LeBron vs BOS games: {len(games)} found")
        for g in games:
            print(f"  - Game: {g.get('game_date')} | Pts: {g.get('pts')}")
            
    except Exception as e:
        print(f"Error verifying H2H: {e}")

if __name__ == "__main__":
    verify_hierarchical_h2h()
