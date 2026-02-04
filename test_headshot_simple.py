"""
Quick headshot CDN test - simplified version
"""
import sqlite3
import requests
import json
from pathlib import Path

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Get 5 sample players
c.execute("SELECT player_id, name FROM players LIMIT 5")
players = c.fetchall()
conn.close()

results = []

for player_id, name in players:
    url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"
    
    try:
        response = requests.head(url, timeout=3)
        status = "SUCCESS" if response.status_code == 200 else f"FAILED_{response.status_code}"
    except Exception as e:
        status = f"ERROR_{str(e)[:30]}"
    
    results.append({
        "player_id": player_id,
        "name": name,
        "url": url,
        "status": status
    })
    
    print(f"{name}: {status}")

# Save to JSON
with open('headshot_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to headshot_results.json")
