"""Test direct stats fetching"""
import sys
sys.path.insert(0, '.')
from services.multi_stat_confluence import MultiStatConfluence

engine = MultiStatConfluence()

# Test with a known SAS player - Victor Wembanyama
# Get his player_id first
import sqlite3
conn = sqlite3.connect('data/nba_data.db')
cursor = conn.cursor()
cursor.execute("SELECT player_id, player_name FROM player_bio WHERE player_name LIKE '%Wembanyama%'")
row = cursor.fetchone()
print(f"Player: {row}")
player_id = row[0] if row else None

if player_id:
    stats = engine.get_player_stats(player_id)
    print(f"\nStats for {player_id}:")
    print(stats)
    
    # Test full projection
    opp_def = engine.get_team_defense('CHA')
    print(f"\nOpp defense: {opp_def}")
    
    proj = engine.project_player(player_id, 'CHA', opp_def, 1.0)
    print(f"\nProjection:")
    if proj:
        for key, val in proj.items():
            if key != 'projections':
                print(f"  {key}: {val}")
        print("\n  Projections:")
        for stat, p in proj.get('projections', {}).items():
            print(f"    {stat}: {p}")
    else:
        print("  NONE - projection failed!")
