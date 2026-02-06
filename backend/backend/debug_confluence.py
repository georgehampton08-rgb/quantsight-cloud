"""Debug confluence deltas"""
from services.multi_stat_confluence import MultiStatConfluence
import json

engine = MultiStatConfluence()
result = engine.analyze_game('BOS', 'SAC')

print(f"Total players: {len(result['projections'])}")

# Count classifications
targets = [p for p in result['projections'] if p.get('classification') == 'TARGET']
fades = [p for p in result['projections'] if p.get('classification') == 'FADE']
neutrals = [p for p in result['projections'] if p.get('classification') == 'NEUTRAL']

print(f"TARGETs: {len(targets)}, FADEs: {len(fades)}, NEUTRALs: {len(neutrals)}")

# Show individual stat breakdowns
print("\n" + "="*60)
for player in result['projections'][:3]:
    print(f"\n{player['player_name']} | Overall: {player.get('classification')} | Grade: {player.get('overall_grade')}")
    
    for stat in ['pts', 'reb', 'ast', '3pm']:
        proj = player['projections'][stat]
        baseline = proj['baseline']
        delta = proj['delta'] 
        pct = (delta / baseline * 100) if baseline > 0 else 0
        print(f"  {stat.upper():4}: {baseline:5.1f} -> {proj['projected']:5.1f} delta={delta:+5.1f} ({pct:+5.1f}%) [{proj['grade']} - {proj['classification']}]")
