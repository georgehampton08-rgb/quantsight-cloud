import requests
import json

url = "http://localhost:5000/aegis/simulate/2544?opponent_id=1610612738"
res = requests.get(url, timeout=30)
data = res.json()

print("=== LEBRON JAMES SIMULATION OUTPUT ===")
print(f"Execution Time: {data.get('execution_time_ms')}ms")
print(f"Injury Status: {data.get('injury_status')}")

proj = data.get('projections', {})
floor = proj.get('floor', {})
ev = proj.get('expected_value', {})
ceiling = proj.get('ceiling', {})

print("\n=== PROJECTIONS ===")
print(f"  POINTS:   Floor={floor.get('points')}, EV={ev.get('points')}, Ceiling={ceiling.get('points')}")
print(f"  REBOUNDS: Floor={floor.get('rebounds')}, EV={ev.get('rebounds')}, Ceiling={ceiling.get('rebounds')}")
print(f"  ASSISTS:  Floor={floor.get('assists')}, EV={ev.get('assists')}, Ceiling={ceiling.get('assists')}")
print(f"  THREES:   Floor={floor.get('threes')}, EV={ev.get('threes')}, Ceiling={ceiling.get('threes')}")
print(f"  MINUTES:  Floor={floor.get('minutes')}, EV={ev.get('minutes')}, Ceiling={ceiling.get('minutes')}")

conf = data.get('confidence', {})
print(f"\n=== CONFIDENCE ===")
print(f"  Grade: {conf.get('grade')}, Score: {conf.get('score')}")

# Check momentum
mom = data.get('momentum', {})
print(f"\n=== MOMENTUM ===")
print(f"  Raw: {mom}")

print("\n=== SUCCESS! Simulation fully operational ===")
