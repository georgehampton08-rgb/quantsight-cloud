"""Debug defense data and deltas"""
from services.multi_stat_confluence import MultiStatConfluence
import json

engine = MultiStatConfluence()

# Check defense data
print("="*60)
print("DEFENSE DATA CHECK")
print("="*60)

bos_def = engine.get_team_defense('BOS')
sac_def = engine.get_team_defense('SAC')

print(f"BOS Defense: {json.dumps(bos_def, indent=2)}")
print(f"\nSAC Defense: {json.dumps(sac_def, indent=2)}")

# Check a matchup
result = engine.analyze_game('BOS', 'SAC')

print(f"\n{'='*60}")
print("PLAYER AGGREGATE SCORES")
print("="*60)

for player in result['projections']:
    agg = player.get('aggregate_score', 'N/A')
    print(f"{player['player_name']:20} | Agg: {agg:+5.1f}% | Class: {player.get('classification')} | Grade: {player.get('overall_grade')}")
