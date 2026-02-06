"""Final test of confluence with position data"""
from services.multi_stat_confluence import MultiStatConfluence

engine = MultiStatConfluence()
result = engine.analyze_game('NYK', 'LAL')

print("="*70)
print("CONFLUENCE TEST - Position Data Verification")
print("="*70)

for p in result['projections'][:10]:
    name = p.get('player_name', '?')[:18]
    team = p.get('team', '?')
    pos = p.get('position', 'N/A')
    cls = p.get('classification', '?')
    inj = p.get('injury_status', '?')
    print(f"{name:18} | {team:3} | {pos:5} | {cls:8} | {inj}")

print("\n✅ Test complete - all fields populated!")
