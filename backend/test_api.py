"""Test full API response"""
import requests
import json

r = requests.get('http://localhost:5000/matchup/analyze?home_team=CHA&away_team=SAS')
d = r.json()

print("Raw response structure:")
print(json.dumps(d, indent=2)[:3000])
