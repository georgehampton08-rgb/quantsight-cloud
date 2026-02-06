"""
Logic Confluence Trace - Verification Script
=============================================
Validates the full Aegis simulation pipeline step-by-step.

This script traces data flow through each engine to verify:
1. EMA calculation correctness
2. Archetype classification
3. Schedule fatigue modifiers
4. Usage vacuum adjustments
5. Monte Carlo distribution parameters
6. Confluence score calculation
"""

import sys
import os
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)


def print_step(step: int, name: str):
    print(f"\n[Step {step}] {name}")
    print("-" * 40)


def run_confluence_trace():
    """Run full data flow trace through all engines"""
    
    print_section("LOGIC CONFLUENCE TRACE")
    print("Tracing data flow through Aegis Intelligence Layer v3.1")
    
    # Import all engines
    print_step(1, "Importing Engines")
    try:
        from engines.ema_calculator import EMACalculator
        from engines.archetype_clusterer import ArchetypeClusterer
        from engines.schedule_fatigue import ScheduleFatigueEngine, FatigueResult
        from engines.usage_vacuum import UsageVacuumEngine
        from engines.vertex_monte_carlo import VertexMonteCarloEngine
        from aegis.confluence_scorer import ConfluenceScorer
        print("   ✅ All engines imported successfully")
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False
    
    # Test data - Stephen Curry-like stats
    print_step(2, "Setting Up Test Data")
    test_game_logs = [
        {'pts': 32, 'reb': 5, 'ast': 6, 'min': 35, 'fga': 22, 'fg3a': 12, 'fta': 4, 'stl': 1, 'blk': 0, 'tov': 3},
        {'pts': 28, 'reb': 4, 'ast': 8, 'min': 34, 'fga': 20, 'fg3a': 10, 'fta': 6, 'stl': 2, 'blk': 0, 'tov': 2},
        {'pts': 35, 'reb': 6, 'ast': 5, 'min': 36, 'fga': 24, 'fg3a': 14, 'fta': 3, 'stl': 1, 'blk': 1, 'tov': 4},
        {'pts': 25, 'reb': 3, 'ast': 7, 'min': 32, 'fga': 18, 'fg3a': 9, 'fta': 5, 'stl': 0, 'blk': 0, 'tov': 2},
        {'pts': 30, 'reb': 5, 'ast': 6, 'min': 35, 'fga': 21, 'fg3a': 11, 'fta': 4, 'stl': 1, 'blk': 0, 'tov': 3},
    ]
    print(f"   Sample size: {len(test_game_logs)} games")
    print(f"   Raw PPG average: {sum(g['pts'] for g in test_game_logs)/len(test_game_logs):.1f}")
    
    # EMA Calculation
    print_step(3, "EMA Calculator (α=0.15)")
    ema_calc = EMACalculator(alpha=0.15)
    ema_stats = ema_calc.calculate(test_game_logs)
    print(f"   Points EMA: {ema_stats['points_ema']:.2f}")
    print(f"   Points STD: {ema_stats['points_std']:.2f}")
    print(f"   Rebounds EMA: {ema_stats['rebounds_ema']:.2f}")
    print(f"   Assists EMA: {ema_stats['assists_ema']:.2f}")
    print("   ✅ EMA calculation complete")
    
    # Archetype Classification
    print_step(4, "Archetype Clusterer")
    clusterer = ArchetypeClusterer()
    player_profile = {
        'ppg': ema_stats['points_ema'],
        'apg': ema_stats['assists_ema'],
        'rpg': ema_stats['rebounds_ema'],
        'fg3a': sum(g['fg3a'] for g in test_game_logs) / len(test_game_logs),
        'fta': sum(g['fta'] for g in test_game_logs) / len(test_game_logs),
        'stl': 1.0,
        'blk': 0.2,
    }
    archetype = clusterer.classify(player_profile)
    print(f"   Archetype: {archetype.archetype}")
    print(f"   Confidence: {archetype.confidence:.0%}")
    print(f"   Friction vs Rim Protector: {clusterer.get_friction(archetype.archetype, 'Rim Protector'):.2f}")
    print("   ✅ Archetype classification complete")
    
    # Schedule Fatigue
    print_step(5, "Schedule Fatigue Engine")
    fatigue_engine = ScheduleFatigueEngine()
    
    # Create recent games with dates (B2B road scenario)
    recent_games = [
        {'date': date.today() - timedelta(days=1)},  # Yesterday
        {'date': date.today() - timedelta(days=3)},
        {'date': date.today() - timedelta(days=5)},
    ]
    fatigue_result = fatigue_engine.calculate_fatigue(
        game_date=date.today(),
        is_road=True,
        recent_games=recent_games
    )
    print(f"   Scenario: Back-to-Back Road")
    print(f"   Days Rest: {fatigue_result.days_rest}")
    print(f"   Fatigue Modifier: {fatigue_result.modifier:.2%}")
    print(f"   Reason: {fatigue_result.reason}")
    print("   ✅ Schedule fatigue calculated")
    
    # Usage Vacuum (mock injured teammate)
    print_step(6, "Usage Vacuum Engine")
    vacuum = UsageVacuumEngine()
    # Calculate a mock redistribution
    injured_player_id = '12345'
    injured_usage = 0.22  # 22% usage rate
    active_roster = ['201939', '202691', '203507']  # Active players
    
    redistribution = vacuum.calculate_redistribution(
        injured_player_id=injured_player_id,
        injured_player_usage=injured_usage,
        active_roster=active_roster
    )
    
    # Get boost for our target player
    usage_boost = redistribution.redistribution.get('201939', 0.0)
    stat_boost = usage_boost * vacuum.USAGE_TO_STAT_FACTOR
    
    print(f"   Injured player USG: {injured_usage:.0%}")
    print(f"   Usage redistribution: {redistribution.total_redistributed:.1%}")
    print(f"   Player usage boost: +{usage_boost:.1%}")
    print(f"   Stat adjustment factor: +{stat_boost:.1%}")
    print("   ✅ Usage vacuum calculated")
    
    # Apply modifiers to EMA stats
    print_step(7, "Applying Modifiers")
    modified_stats = {
        'points_ema': ema_stats['points_ema'] * (1 + fatigue_result.modifier) * (1 + usage_boost * 0.5),
        'points_std': ema_stats['points_std'],
        'rebounds_ema': ema_stats['rebounds_ema'] * (1 + fatigue_result.modifier),
        'rebounds_std': ema_stats['rebounds_std'],
        'assists_ema': ema_stats['assists_ema'] * (1 + fatigue_result.modifier),
        'assists_std': ema_stats['assists_std'],
        'threes_ema': 3.5,
        'steals_ema': 1.0,
        'blocks_ema': 0.2,
        'turnovers_ema': 2.8,
    }
    print(f"   Base Points: {ema_stats['points_ema']:.2f}")
    print(f"   After Fatigue ({fatigue_result.modifier:+.1%}): {ema_stats['points_ema'] * (1 + fatigue_result.modifier):.2f}")
    print(f"   After Usage (+{usage_boost:.1%}): {modified_stats['points_ema']:.2f}")
    print("   ✅ Modifiers applied")
    
    # Monte Carlo Simulation
    print_step(8, "Monte Carlo Simulation (10K)")
    mc_engine = VertexMonteCarloEngine(n_simulations=10_000)
    start_time = time.perf_counter()
    sim_result = mc_engine.run_simulation(modified_stats)
    execution_ms = (time.perf_counter() - start_time) * 1000
    
    print(f"   Execution Time: {execution_ms:.1f}ms")
    print(f"   Floor (20th): {sim_result.projection.floor_20th}")
    print(f"   Expected Value: {sim_result.projection.expected_value}")
    print(f"   Ceiling (80th): {sim_result.projection.ceiling_80th}")
    print("   ✅ Monte Carlo simulation complete")
    
    # Confluence Score
    print_step(9, "Confluence Scorer")
    scorer = ConfluenceScorer()
    
    # Mock model predictions (agreement test)
    model_predictions = {
        'linear_regression': 29.5,
        'random_forest': 30.2,
        'xgboost': 28.8,
    }
    
    confluence = scorer.calculate(
        model_predictions=model_predictions,
        sample_size=len(test_game_logs),
    )
    print(f"   Model Agreement: {confluence.components['model_agreement']:.1f}")
    print(f"   Sample Weight: {confluence.components['sample_size']:.1f}")
    print(f"   Historical Accuracy: {confluence.components['historical_accuracy']:.1f}")
    print(f"   Final Score: {confluence.score:.1f}")
    print(f"   Grade: {confluence.grade}")
    print("   ✅ Confluence score calculated")
    
    # Final Summary
    print_section("TRACE COMPLETE")
    print("\n📊 Final Projection Summary:")
    print(f"   Player Archetype: {archetype.archetype}")
    print(f"   Schedule Impact: {fatigue_result.modifier:+.1%}")
    print(f"   Usage Adjustment: +{usage_boost:.1%}")
    print(f"   Points: {sim_result.projection.floor_20th['points']:.1f} / {sim_result.projection.expected_value['points']:.1f} / {sim_result.projection.ceiling_80th['points']:.1f}")
    print(f"   Confidence: {confluence.grade} ({confluence.score:.0f})")
    print(f"   Execution: {execution_ms:.1f}ms")
    
    # Validation checks
    print("\n✅ VALIDATION CHECKS:")
    checks_passed = 0
    
    if execution_ms < 500:
        print(f"   ✅ Performance: {execution_ms:.1f}ms < 500ms target")
        checks_passed += 1
    else:
        print(f"   ❌ Performance: {execution_ms:.1f}ms > 500ms target")
    
    if sim_result.projection.floor_20th['points'] < sim_result.projection.expected_value['points'] < sim_result.projection.ceiling_80th['points']:
        print("   ✅ Percentiles: Floor < EV < Ceiling (correct ordering)")
        checks_passed += 1
    else:
        print("   ❌ Percentiles: Incorrect ordering")
    
    if 0 <= confluence.score <= 100:
        print(f"   ✅ Confluence: Score in valid range (0-100)")
        checks_passed += 1
    else:
        print(f"   ❌ Confluence: Score out of range")
    
    if fatigue_result.modifier < 0:
        print(f"   ✅ Fatigue: B2B road correctly negative ({fatigue_result.modifier:+.1%})")
        checks_passed += 1
    else:
        print(f"   ❌ Fatigue: B2B road should be negative")
    
    print(f"\n{'=' * 60}")
    print(f" RESULT: {checks_passed}/4 checks passed")
    print('=' * 60)
    
    return checks_passed == 4


if __name__ == "__main__":
    success = run_confluence_trace()
    sys.exit(0 if success else 1)
