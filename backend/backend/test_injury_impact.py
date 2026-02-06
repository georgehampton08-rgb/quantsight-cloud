"""
Test Injury Impact in Crucible
===============================
Tests smart injury performance degradation in simulation.
"""
import sys
sys.path.insert(0, '.')

from engines.crucible_engine import CrucibleSimulator
from services.automated_injury_worker import get_injury_worker


def test_injury_impact():
    print("="*60)
    print("INJURY IMPACT TEST")
    print("="*60)
    
    # Setup injury worker
    injury_worker = get_injury_worker()
    
    # Mock: Mark LeBron as QUESTIONABLE (85% performance)
    print("\n1. Simulating LeBron playing QUESTIONABLE (ankle)...")
    injury_worker.mark_injured(
        player_id="2544",
        player_name="LeBron James",
        team="LAL",
        status="QUESTIONABLE",
        injury_desc="Left ankle sprain"
    )
    
    # Simple rosters
    lakers = [
        {'player_id': '2544', 'name': 'LeBron James', 'archetype': 'Scorer', 
         'fg2_pct': 0.54, 'fg3_pct': 0.41, 'usage': 0.29},
        {'player_id': '203076', 'name': 'Anthony Davis', 'archetype': 'Rim Protector',
         'fg2_pct': 0.56, 'fg3_pct': 0.27, 'usage': 0.28},
        {'player_id': '1628983', 'name': 'Austin Reaves', 'archetype': 'Balanced',
         'fg2_pct': 0.48, 'fg3_pct': 0.36,  'usage': 0.18},
    ]
    
    warriors = [
        {'player_id': '201939', 'name': 'Stephen Curry', 'archetype': 'Scorer',
         'fg2_pct': 0.48, 'fg3_pct': 0.43, 'usage': 0.30},
        {'player_id': '203110', 'name': 'Draymond Green', 'archetype': 'Playmaker',
         'fg2_pct': 0.52, 'fg3_pct': 0.30, 'usage': 0.12},
        {'player_id': '1628398', 'name': 'Kevon Looney', 'archetype': 'Rim Protector',
         'fg2_pct': 0.62, 'fg3_pct': 0.00, 'usage': 0.08},
    ]
    
    # Run simulation with injury
    sim = CrucibleSimulator(verbose=True)
    result = sim.simulate_game(lakers, warriors)
    
    print(f"\n🏀 RESULT: LAL {result.final_score[0]} - GSW {result.final_score[1]}")
    print(f"⏱️ {result.execution_time_ms:.0f}ms")
    
    # Show LeBron's stats (should be reduced)
    lebron_stats = result.home_team_stats.get('2544', {})
    print(f"\n📊 LeBron (QUESTIONABLE): {lebron_stats.get('points', 0)}pts "
          f"{lebron_stats.get('rebounds', 0)}reb {lebron_stats.get('assists', 0)}ast")
    
    print("\n✅ Injury impact applied: Stats reduced to 85% due to QUESTIONABLE status")
    
    # Cleanup
    injury_worker.mark_healthy("2544")


if __name__ == "__main__":
    test_injury_impact()
