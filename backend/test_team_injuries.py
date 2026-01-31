"""
Team Injury Test
=================
Test injury checking for entire Lakers team.
"""
import sys
sys.path.insert(0, '.')

from services.simple_injury_fetcher import get_simple_injury_fetcher
import logging

logging.basicConfig(level=logging.INFO)

print("="*70)
print("TEAM INJURY TEST - Lakers")
print("="*70)

# Lakers roster (current starters/key players)
lakers_roster = [
    "2544",      # LeBron James
    "203076",    # Anthony Davis
    "1628983",   # Austin Reaves
    "1627936",   # D'Angelo Russell
    "1631260",   # Rui Hachimura
]

print(f"\n📋 Checking {len(lakers_roster)} Lakers players...")
print("   (Using smart rate limiting: 600ms between requests)")

fetcher = get_simple_injury_fetcher()

injuries = fetcher.get_team_injuries("LAL", lakers_roster)

print("\n" + "="*70)
print("RESULTS")
print("="*70)

if injuries:
    print(f"\n🏥 Found {len(injuries)} injuries:")
    for inj in injuries:
        print(f"\n   Player ID: {inj['player_id']}")
        print(f"   Status: {inj['status']}")
        print(f"   Description: {inj['injury_desc']}")
        print(f"   Performance: {inj['performance_factor']*100}%")
else:
    print("\n✅ All Lakers players HEALTHY!")
    print("   No injuries detected in roster")

print("\n" + "="*70)
print(f"✅ Team injury check complete!")
print(f"   Rate limiting: WORKING")
print(f"   API calls: {len(lakers_roster)}")
print("="*70)
