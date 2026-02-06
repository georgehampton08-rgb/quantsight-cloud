"""Test both teams are returned"""
from services.multi_stat_confluence import MultiStatConfluence

engine = MultiStatConfluence()
result = engine.analyze_game('BOS', 'MIA')

print("="*70)
print(f"Game: {result['game']}")
print("="*70)

# Group by team
bos_players = [p for p in result['projections'] if p.get('team') == 'BOS']
mia_players = [p for p in result['projections'] if p.get('team') == 'MIA']

print(f"\nBOS players: {len(bos_players)}")
print(f"MIA players: {len(mia_players)}")
print(f"Total: {len(result['projections'])}")

print("\nBOS Sample:")
for p in bos_players[:3]:
    print(f"  {p['player_name']}: {p.get('classification', '?')}")

print("\nMIA Sample:")
for p in mia_players[:3]:
    print(f"  {p['player_name']}: {p.get('classification', '?')}")

# Check math - verify delta calculation
if result['projections']:
    p = result['projections'][0]
    pts = p['projections']['pts']
    calc_delta = pts['projected'] - pts['baseline']
    actual_delta = pts['delta']
    print(f"\nMath Check ({p['player_name']}):")
    print(f"  Baseline: {pts['baseline']}")
    print(f"  Projected: {pts['projected']}")
    print(f"  Calculated Delta: {calc_delta:.2f}")
    print(f"  Actual Delta: {actual_delta}")
    print(f"  ✅ Match" if abs(calc_delta - actual_delta) < 0.01 else f"  ❌ MISMATCH")
