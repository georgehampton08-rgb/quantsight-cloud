"""Check game ID format from schedule"""
import requests
import json

response = requests.get('http://localhost:5000/schedule', timeout=10)
data = response.json()
games = data.get('games', [])

print("=" * 60)
print("Current Game ID Structure")
print("=" * 60)

for i, game in enumerate(games[:5]):
    print(f"\nGame {i+1}:")
    print(f"  game_id: {game.get('game_id', 'MISSING')}")
    print(f"  {game.get('away_team')} @ {game.get('home_team')}")
    print(f"  status: {game.get('status')}")
    print(f"  All keys: {list(game.keys())}")

# Check if game_id exists and what format it's in
has_game_ids = all(g.get('game_id') for g in games)
print(f"\n{'✅' if has_game_ids else '❌'} All games have game_id: {has_game_ids}")

if games:
    sample_id = games[0].get('game_id', '')
    print(f"\nSample game_id: '{sample_id}'")
    print(f"  Type: {type(sample_id)}")
    print(f"  Length: {len(str(sample_id))}")
