import requests
import time
import sys

BASE_URL = "http://localhost:5000"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_session():
    log("Starting End-to-End Session Simulation...", "INIT")

    try:
        # 1. Dashboard Load (with retry)
        log("Step 1: Dashboard Load...")
        max_retries = 10
        health = None
        for i in range(max_retries):
            try:
                health = requests.get(f"{BASE_URL}/health").json()
                if health: break
            except requests.exceptions.ConnectionError:
                log(f"   Waiting for backend... ({i+1}/{max_retries})")
                time.sleep(2)
        
        if not health:
            raise Exception("Backend unavailable after retries")

        # Assert 'database' key is healthy since there is no 'status' key
        assert health['database'] == 'healthy'
        
        schedule = requests.get(f"{BASE_URL}/schedule").json()
        assert 'games' in schedule
        log("✅ Dashboard operational.")

        # 2. Team Central Navigation - Dynamic Selection
        log("Step 2: Team Central Navigation...")
        teams = requests.get(f"{BASE_URL}/teams").json()
        assert 'teams' in teams
        
        target_team = None
        target_player = None
        
        # Find first team with a roster
        for team in teams['teams']:
            try:
                r_data = requests.get(f"{BASE_URL}/roster/{team['id']}").json()
                if 'roster' in r_data and len(r_data['roster']) > 0:
                    target_team = team
                    target_player = r_data['roster'][0]
                    break
            except:
                continue
                
        if not target_team or not target_player:
            raise Exception("No teams found with populated roster!")
            
        log(f"   Selected Team: {target_team['full_name']} (ID: {target_team['id']})")
        log(f"   Selected Player: {target_player['name']} (ID: {target_player['id']})")

        # 3. Validation
        log("Step 3: Roster Verified (Dynamic).")
        player_id = target_player['id']

        # 4. Player Profile Load
        log("Step 4: Viewing Player Profile...")
        profile = requests.get(f"{BASE_URL}/players/{player_id}").json()
        assert profile['name'] == lebron['name']
        log("✅ Profile Loaded.")

        # 5. Matchup Analysis
        log("Step 5: Running Matchup Analysis vs BOS...")
        analysis = requests.get(f"{BASE_URL}/matchup/analyze", params={"player_id": player_id, "opponent": "BOS"}).json()
        assert 'nemesis_vector' in analysis
        log("✅ Analysis Compute Complete.")

        log("🎉 E2E SESSION SIMULATION PASSED!", "SUCCESS")

    except Exception as e:
        log(f"Session Failed: {str(e)}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    test_session()
