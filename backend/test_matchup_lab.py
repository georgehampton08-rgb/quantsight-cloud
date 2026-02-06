import requests
import json

# Test matchup lab analysis
print("=" * 60)
print("MATCHUP LAB ANALYSIS TEST: CHI vs MIA")
print("=" * 60)

r = requests.get('http://localhost:5000/matchup-lab/analyze/CHI/MIA')
data = r.json()

print(f"\nStatus: {r.status_code}")
print(f"Success: {data.get('success')}")
print(f"AI Powered: {data.get('ai_powered')}")
print(f"Game: {data.get('game')}")

# Matchup context
ctx = data.get('matchup_context', {})
print(f"\n--- Matchup Context ---")
print(f"  Pace: {ctx.get('pace', 'N/A')}")
print(f"  Def Rating: {ctx.get('defensive_rating', 'N/A')}")

# Top projections
print(f"\n--- Top 5 Player Projections ---")
projections = data.get('projections', [])
for i, p in enumerate(projections[:5]):
    print(f"\n{i+1}. {p.get('player_name', 'Unknown')}")
    print(f"   PTS: {p.get('pts', {}).get('projection', 'N/A')}")
    print(f"   REB: {p.get('reb', {}).get('projection', 'N/A')}")
    print(f"   AST: {p.get('ast', {}).get('projection', 'N/A')}")

# Insights
insights = data.get('insights', {})
print(f"\n--- AI Insights ---")
print(f"  Summary: {insights.get('summary', 'N/A')[:200]}...")

print("\n" + "=" * 60)

# Check live scores
print("\nLIVE GAMES CHECK:")
r2 = requests.get('http://localhost:5000/matchup-lab/games')
games = r2.json().get('games', [])
for g in games[:3]:
    status = g.get('status', 'N/A')
    home = g.get('home_team', 'N/A')
    away = g.get('away_team', 'N/A')
    home_score = g.get('home_score', 'N/A')
    away_score = g.get('away_score', 'N/A')
    print(f"  {away} {away_score} @ {home} {home_score} - {status}")
