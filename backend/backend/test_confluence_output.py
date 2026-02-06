"""Test enhanced confluence output"""
from services.multi_stat_confluence import MultiStatConfluence
import json

engine = MultiStatConfluence()
result = engine.analyze_game('BOS', 'SAC')

print("="*80)
print(f"ENHANCED CONFLUENCE TEST: {result['game']}")
print("="*80)

# Matchup Context
ctx = result['matchup_context']
print(f"\nMATCHUP CONTEXT:")
print(f"  Projected Pace: {ctx['projected_pace']}")
print(f"  BOS DEF: {ctx['home_defense'].get('opp_pts', 'N/A')} PPG, RTG={ctx['home_defense'].get('def_rating', 'N/A')}")
print(f"  SAC DEF: {ctx['away_defense'].get('opp_pts', 'N/A')} PPG, RTG={ctx['away_defense'].get('def_rating', 'N/A')}")

# Find TARGETS and FADES
targets = [p for p in result['projections'] if p.get('classification') == 'TARGET']
fades = [p for p in result['projections'] if p.get('classification') == 'FADE']

print(f"\n{'='*40}")
print(f"TARGETS ({len(targets)} players)")
print(f"{'='*40}")
for p in targets[:5]:
    pts = p['projections']['pts']
    print(f"  {p['player_name']:20} ({p.get('position', '?'):2}) | {p['team']} | {p['overall_grade']} | PTS: {pts['baseline']:.1f} -> {pts['projected']:.1f} ({pts['delta']:+.1f}) | {pts['grade']}")

print(f"\n{'='*40}")
print(f"FADES ({len(fades)} players)")
print(f"{'='*40}")
for p in fades[:5]:
    pts = p['projections']['pts']
    print(f"  {p['player_name']:20} ({p.get('position', '?'):2}) | {p['team']} | {p['overall_grade']} | PTS: {pts['baseline']:.1f} -> {pts['projected']:.1f} ({pts['delta']:+.1f}) | {pts['grade']}")

print(f"\n{'='*40}")
print("SAMPLE FULL PLAYER OUTPUT:")
print(f"{'='*40}")
if result['projections']:
    player = result['projections'][0]
    print(json.dumps(player, indent=2))
