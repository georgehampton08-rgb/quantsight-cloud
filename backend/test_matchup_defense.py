"""Test analyze_game directly"""
import sys
sys.path.insert(0, 'backend')
from services.multi_stat_confluence import MultiStatConfluence

engine = MultiStatConfluence()
result = engine.analyze_game('BOS', 'MIA')

print("=" * 60)
print("Testing analyze_game(BOS, MIA)")
print("=" * 60)

# Check matchup_context
ctx = result.get('matchup_context', {})
print(f"\nMatchup Context Keys: {list(ctx.keys())}")

if ctx:
    pace = ctx.get('projected_pace')
    print(f"\nProjected Pace: {pace}")
    
    home_def = ctx.get('home_defense', {})
    print(f"\nHome Defense (BOS):")
    for k, v in home_def.items():
        print(f"  {k}: {v}")
    
    away_def = ctx.get('away_defense', {})
    print(f"\nAway Defense (MIA):")
    for k, v in away_def.items():
        print(f"  {k}: {v}")
    
    if pace and home_def.get('opp_pts') and away_def.get('opp_pts'):
        print(f"\n✅ All defense data present and should display in frontend!")
    else:
        print(f"\n❌ Missing data - pace:{pace}, home opp_pts:{home_def.get('opp_pts')}, away opp_pts:{away_def.get('opp_pts')}")
else:
    print("\n❌ No matchup_context returned")
