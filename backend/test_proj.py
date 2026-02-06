"""Test script to check matchup projections"""
import requests

r = requests.get('http://localhost:5000/matchup/analyze?home_team=CHA&away_team=SAS')
d = r.json()
p = d.get('projections', [])
print(f'Total projections: {len(p)}')
print()

for x in p[:5]:
    print(f"Player: {x.get('player_name')}")
    print(f"  PTS: base={x.get('pts',{}).get('base')}, projected={x.get('pts',{}).get('projected')}, delta={x.get('pts',{}).get('delta')}")
    print(f"  REB: base={x.get('reb',{}).get('base')}, projected={x.get('reb',{}).get('projected')}")
    print(f"  3PM: base={x.get('3pm',{}).get('base')}, projected={x.get('3pm',{}).get('projected')}")
    print(f"  Form: {x.get('form')}, H2H PTS: {x.get('h2h_pts')}")
    print(f"  Classification: {x.get('classification')}, Grade: {x.get('grade')}")
    print()
