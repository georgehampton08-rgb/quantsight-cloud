"""Debug: Check what endpoint is actually being called"""
import requests

# Simulate the frontend call exactly as it would be made
game_data = {
    'game_id': '0022400690',  # Example game ID
    'home_team': 'WAS',
    'away_team': 'LAL'
}

params = {
    'game_id': game_data['game_id'],
    'home_team': game_data['home_team'],
    'away_team': game_data['away_team']
}

url = f"http://localhost:5000/matchup/analyze"
print(f"URL: {url}")
print(f"Params: {params}")
print(f"Full URL: {url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}")

# Make the request
try:
    response = requests.get(url, params=params, timeout=10)
    print(f"\nStatus: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
