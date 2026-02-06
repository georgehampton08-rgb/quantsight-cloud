"""Test new game_id endpoint"""
import requests
import time

# Wait for server
print("Waiting for server...")
for i in range(10):
    try:
        requests.get('http://localhost:5000/health', timeout=1)
        print("✅ Server is up!")
        break
    except:
        time.sleep(1)
        if i == 9:
            print("❌ Server not responding")
            exit(1)

# Test new endpoint
print("\n" + "="*60)
print("Testing /matchup/analyze endpoint")
print("="*60)

params = {
    'game_id': 'test_game_123',
    'home_team': 'BOS',
    'away_team': 'MIA'
}

response = requests.get('http://localhost:5000/matchup/analyze', params=params, timeout=15)

print(f"\nStatus Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"✅ Success!")
    print(f"  game_id in response: {data.get('game_id')}")
    print(f"  game: {data.get('game')}")
    print(f"  Has matchup_context: {'matchup_context' in data}")
    print(f"  Has projections: {'projections' in data}")
    print(f"  AI powered: {data.get('ai_powered')}")
else:
    print(f"❌ Error: {response.text}")
