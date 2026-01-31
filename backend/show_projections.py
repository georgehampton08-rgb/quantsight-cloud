import json

data = json.load(open('data/confluence_projections.json'))

print("=" * 85)
print("CONFLUENCE PROJECTIONS - LAL @ CLE")
print("=" * 85)
print(f"{'PLAYER':<20} TEAM  BASE  PROJ   DELTA  FORM        H2H          CONF")
print("-" * 85)

for p in sorted(data['projections'], key=lambda x: x['projected'], reverse=True):
    name = p['player'][:18]
    form = p['form_label'].replace('\U0001f525', 'HOT').replace('\u2744\ufe0f', 'COLD').replace('\U0001f4c8', 'UP').replace('\U0001f4c9', 'DOWN').replace('\u2796', '')[:8]
    h2h = str(p['h2h_avg'])[:12]
    
    print(f"{name:<20} {p['team']:<4} {p['baseline']:>5.1f} {p['projected']:>5.1f} {p['delta']:>+6.1f}  {form:<10} {h2h:<12} {p['confidence']}%")

print("=" * 85)
print("\nBEST MATCHUPS (highest projected boost):")
for p in sorted(data['projections'], key=lambda x: x['delta'], reverse=True)[:5]:
    print(f"  {p['player']}: {p['baseline']:.1f} -> {p['projected']:.1f} ({p['delta']:+.1f})")

print("\nWORST MATCHUPS (lowest projected):")
for p in sorted(data['projections'], key=lambda x: x['delta'])[:5]:
    print(f"  {p['player']}: {p['baseline']:.1f} -> {p['projected']:.1f} ({p['delta']:+.1f})")
