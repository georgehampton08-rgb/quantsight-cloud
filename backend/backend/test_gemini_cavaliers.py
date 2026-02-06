"""
Test Gemini Injury Fetcher - Cavaliers
=======================================
Test with team known to have injuries.
"""
import logging
from production_injury_fetcher import ProductionInjuryFetcher

logging.basicConfig(level=logging.INFO)

print("="*70)
print("GEMINI INJURY TEST - CAVALIERS")
print("="*70)

print("\n📰 Known injuries from web search (Jan 28, 2026):")
print("   - Darius Garland: OUT (right great toe sprain)")
print("   - Evan Mobley: OUT (left calf strain)")
print("   - Max Strus: OUT (left foot surgery)")

fetcher = ProductionInjuryFetcher()

print("\n🔎 Querying Gemini API...\n")
report = fetcher.get_team_injuries_today("Cleveland Cavaliers")

print("RAW GEMINI RESPONSE:")
print("-" * 70)
print(report)
print("-" * 70)

print("\n\nPARSED INJURIES:")
injuries = fetcher.parse_injury_report(report)

if injuries:
    print(f"\n✅ Found {len(injuries)} injuries:\n")
    for inj in injuries:
        print(f"   {inj['player_name']}")
        print(f"      Status: {inj['status']}")
        print(f"      Injury: {inj['injury_desc']}")
        print(f"      Performance Factor: {inj['performance_factor']*100}%")
        print()
    
    # Compare with known injuries
    print("\n📊 VALIDATION:")
    known_players = ["Darius Garland", "Evan Mobley", "Max Strus"]
    found_players = [inj['player_name'] for inj in injuries]
    
    for player in known_players:
        if any(player.split()[-1] in fp for fp in found_players):
            print(f"   ✅ {player} - FOUND")
        else:
            print(f"   ⚠️  {player} - NOT FOUND")
else:
    print("\n⚠️  No injuries detected by Gemini")
    print("   This could mean:")
    print("   1. Gemini's search didn't find today's injury report")
    print("   2. The injuries weren't in Gemini's search results")

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
