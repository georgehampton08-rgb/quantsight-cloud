"""Test AI insights with defense data"""
import sys
sys.path.insert(0, 'backend')
from services.multi_stat_confluence import MultiStatConfluence
from services.ai_insights import GeminiInsights

# Generate confluence data
engine = MultiStatConfluence()
confluence_data = engine.analyze_game('BOS', 'MIA')

print("=" * 60)
print("Testing AI Insights with Defense Data")
print("=" * 60)

# Check matchup_context
ctx = confluence_data.get('matchup_context', {})
print(f"\nMatchup Context:")
print(f"  Projected Pace: {ctx.get('projected_pace')}")
print(f"  Home Defense (BOS): {ctx.get('home_defense', {}).get('opp_pts')} PPG, DEF RTG: {ctx.get('home_defense', {}).get('def_rating')}")
print(f"  Away Defense (MIA): {ctx.get('away_defense', {}).get('opp_pts')} PPG, DEF RTG: {ctx.get('away_defense', {}).get('def_rating')}")

# Generate AI insights
ai_engine = GeminiInsights()
insights = ai_engine.generate_insights(confluence_data)

print(f"\n{'='*60}")
print("AI Insights Generated:")
print(f"{'='*60}")
print(f"\n{insights.get('summary')}")
print(f"\nAI Powered: {insights.get('ai_powered')}")

# Check if it mentions defense
if 'defense' in insights.get('summary', '').lower() or 'def' in insights.get('summary', '').lower():
    print("\n✅ AI insights now reference defense data!")
else:
    print("\n⚠️  AI summary doesn't mention defense (may be focusing on other factors)")
