"""Test confluence engine"""
import sys
sys.path.insert(0, '.')

from services.multi_stat_confluence import MultiStatConfluence

engine = MultiStatConfluence()

# Test getting player stats
print("=== Test Tatum ===")
stats = engine.get_player_stats('1628369')  # Jayson Tatum
print(f"Stats: {stats}")

if stats:
    print(f"\nName: {stats['name']}")
    print(f"PTS: {stats['pts']}")
    print(f"REB: {stats['reb']}")
    print(f"AST: {stats['ast']}")
    print(f"3PM: {stats['3pm']}")
    print(f"Trend: {stats['trend']}")
