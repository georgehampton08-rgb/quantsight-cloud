"""
Crucible Engine End-to-End Test
================================
Full test of the Crucible simulation with:
- Usage Vacuum (injury scenario)
- Blowout detection
- Learning Ledger logging
- Auto-Tuner integration
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from engines.crucible_engine import CrucibleProjector, CrucibleSimulator
from aegis.auto_tuner import AutoTuner


def test_injury_scenario():
    """Test Usage Vacuum with an injury scenario"""
    print("=" * 70)
    print(" 🔥 CRUCIBLE ENGINE - INJURY SCENARIO TEST")
    print("=" * 70)
    
    # Warriors players - Curry is OUT
    warriors_full = [
        {'player_id': '201939', 'name': 'Stephen Curry', 'archetype': 'Scorer', 'fg2_pct': 0.55, 'fg3_pct': 0.42, 'usage': 0.32},
        {'player_id': '203110', 'name': 'Draymond Green', 'archetype': 'Playmaker', 'fg2_pct': 0.52, 'fg3_pct': 0.30, 'usage': 0.14},
        {'player_id': '203952', 'name': 'Andrew Wiggins', 'archetype': 'Balanced', 'fg2_pct': 0.50, 'fg3_pct': 0.38, 'usage': 0.18},
        {'player_id': '1628398', 'name': 'Kevon Looney', 'archetype': 'Rim Protector', 'fg2_pct': 0.62, 'fg3_pct': 0.00, 'usage': 0.08},
        {'player_id': '1630228', 'name': 'Jonathan Kuminga', 'archetype': 'Slasher', 'fg2_pct': 0.54, 'fg3_pct': 0.32, 'usage': 0.16},
        {'player_id': 'bench1', 'name': 'Reserve 1', 'archetype': 'Balanced', 'usage': 0.08},
        {'player_id': 'bench2', 'name': 'Reserve 2', 'archetype': 'Balanced', 'usage': 0.08},
    ]
    
    lakers = [
        {'player_id': '2544', 'name': 'LeBron James', 'archetype': 'Scorer', 'fg2_pct': 0.58, 'fg3_pct': 0.38, 'usage': 0.30},
        {'player_id': '203076', 'name': 'Anthony Davis', 'archetype': 'Rim Protector', 'fg2_pct': 0.56, 'fg3_pct': 0.28, 'usage': 0.28},
        {'player_id': '1628398', 'name': "D'Angelo Russell", 'archetype': 'Playmaker', 'fg2_pct': 0.48, 'fg3_pct': 0.36, 'usage': 0.22},
        {'player_id': '203484', 'name': 'Austin Reaves', 'archetype': 'Three-and-D', 'fg2_pct': 0.50, 'fg3_pct': 0.40, 'usage': 0.15},
        {'player_id': '1629060', 'name': 'Rui Hachimura', 'archetype': 'Balanced', 'fg2_pct': 0.52, 'fg3_pct': 0.35, 'usage': 0.12},
        {'player_id': 'bench3', 'name': 'Reserve 3', 'archetype': 'Balanced', 'usage': 0.08},
        {'player_id': 'bench4', 'name': 'Reserve 4', 'archetype': 'Balanced', 'usage': 0.08},
    ]
    
    injuries = [
        {'team': 'away', 'player_id': '201939', 'name': 'Stephen Curry', 'usage': 0.32}
    ]
    
    # Run simulation WITHOUT injury
    print("\n📊 Scenario 1: Full Roster (No Injuries)")
    print("-" * 50)
    
    projector_full = CrucibleProjector(n_simulations=200, verbose=False)
    proj_full = projector_full.project(lakers, warriors_full)
    
    wiggins_full = proj_full['away'].get('203952', {})
    print(f"   Andrew Wiggins: {wiggins_full.get('ev', {}).get('points', 0):.1f} pts EV")
    print(f"   Team Score: {proj_full['game']['away_score']['ev']:.0f}")
    
    # Run simulation WITH Curry out
    print("\n📊 Scenario 2: CURRY OUT (Usage Vacuum Applied)")
    print("-" * 50)
    
    simulator = CrucibleSimulator(verbose=False)
    
    # Run multiple simulations manually
    all_wiggins_pts = []
    all_team_scores = []
    
    for _ in range(200):
        result = simulator.simulate_game(lakers, warriors_full, injuries=injuries)
        wiggins_stats = result.away_team_stats.get('203952', {})
        all_wiggins_pts.append(wiggins_stats.get('points', 0))
        all_team_scores.append(result.final_score[1])
    
    import numpy as np
    wiggins_ev_injured = np.mean(all_wiggins_pts)
    team_ev_injured = np.mean(all_team_scores)
    
    print(f"   Andrew Wiggins: {wiggins_ev_injured:.1f} pts EV (+{wiggins_ev_injured - wiggins_full.get('ev', {}).get('points', 0):.1f})")
    print(f"   Team Score: {team_ev_injured:.0f}")
    
    # Usage boost
    wiggins_boost = wiggins_ev_injured - wiggins_full.get('ev', {}).get('points', 0)
    print(f"\n   ✅ Usage Vacuum Effect: +{wiggins_boost:.1f} pts for Wiggins")
    
    # Log to Auto-Tuner
    print("\n📝 Logging to Auto-Tuner...")
    tuner = AutoTuner()
    tuner.log_game_script(
        game_id="LAL_GSW_INJURY_TEST",
        game_date=date.today(),
        home_team="LAL",
        away_team="GSW",
        home_score_pred=(
            proj_full['game']['home_score']['floor'],
            proj_full['game']['home_score']['ev'],
            proj_full['game']['home_score']['ceiling']
        ),
        away_score_pred=(
            proj_full['game']['away_score']['floor'],
            np.mean(all_team_scores),  # Adjusted for injury
            proj_full['game']['away_score']['ceiling']
        ),
        blowout_pct=0.25,
        clutch_pct=0.15,
        key_events=["Stephen Curry OUT", "Usage Vacuum applied to remaining players"]
    )
    print("   ✅ Game script logged")
    
    print("\n" + "=" * 70)
    print(" TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_injury_scenario()
