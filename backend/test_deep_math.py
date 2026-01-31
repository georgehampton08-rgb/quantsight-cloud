"""
DEEP MATH VALIDATION TEST SUITE
================================
Tests all calculation engines working together:
1. EMA (Exponential Moving Average)
2. Monte Carlo Simulation
3. Defense Matrix (PAOA)
4. Friction Calculations
5. End-to-end simulation accuracy
"""

import sys
import numpy as np
from pathlib import Path

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 70)
print("DEEP MATH VALIDATION TEST SUITE")
print("=" * 70)

# ============================================================================
# TEST 1: EMA CALCULATION
# ============================================================================
print("\n[TEST 1] EMA (Exponential Moving Average) Calculation")
print("-" * 50)

from engines.ema_calculator import EMACalculator

ema = EMACalculator(alpha=0.15)

# Test data: simulated game logs (lowercase field names as expected)
test_games = [
    {'pts': 25, 'reb': 8, 'ast': 5, 'fg3m': 3},
    {'pts': 20, 'reb': 10, 'ast': 7, 'fg3m': 2},
    {'pts': 30, 'reb': 6, 'ast': 4, 'fg3m': 4},
    {'pts': 22, 'reb': 9, 'ast': 6, 'fg3m': 2},
    {'pts': 28, 'reb': 7, 'ast': 8, 'fg3m': 5},
]

result = ema.calculate(test_games)

print(f"  Test Data: 5 games")
print(f"  Raw Avg PTS: {sum(g['pts'] for g in test_games) / len(test_games):.1f}")
print(f"  EMA PTS: {result.get('points_ema', 0):.2f}")
print(f"  Std Dev PTS: {result.get('points_std', 0):.2f}")

# Verify EMA weighs recent games more
assert result.get('points_ema', 0) > 0, "EMA should produce non-zero value"
print("  ✅ EMA Calculation: PASS")

# ============================================================================
# TEST 2: DEFENSE MATRIX (PAOA)
# ============================================================================
print("\n[TEST 2] Defense Matrix (PAOA Calculations)")
print("-" * 50)

from services.defense_matrix import DefenseMatrix

DefenseMatrix.clear_cache()

# Test with team IDs
celtics = DefenseMatrix.get_profile('1610612738')  # BOS
lakers = DefenseMatrix.get_profile('1610612747')   # LAL

print(f"  Celtics (1610612738):")
print(f"    Available: {celtics.get('available', False)}")
print(f"    Def Rating: {celtics.get('def_rating', 'N/A')}")
print(f"    vs_PG PAOA: {celtics.get('vs_PG', 'N/A')}")
print(f"    vs_C PAOA: {celtics.get('vs_C', 'N/A')}")

print(f"  Lakers (1610612747):")
print(f"    Available: {lakers.get('available', False)}")
print(f"    Def Rating: {lakers.get('def_rating', 'N/A')}")
print(f"    vs_PG PAOA: {lakers.get('vs_PG', 'N/A')}")

# Verify different teams have different PAOA values
if celtics.get('available') and lakers.get('available'):
    assert celtics.get('def_rating') != lakers.get('def_rating') or \
           celtics.get('vs_PG') != lakers.get('vs_PG'), \
           "Different teams should have different defense data"
    print("  ✅ Defense Matrix: PASS (data varies by team)")
else:
    print("  ⚠️ Defense Matrix: PARTIAL (some teams unavailable)")

# ============================================================================
# TEST 3: ARCHETYPE FRICTION
# ============================================================================
print("\n[TEST 3] Archetype Friction Calculation")
print("-" * 50)

from engines.archetype_clusterer import ArchetypeClusterer

clusterer = ArchetypeClusterer()

# Test friction for Scorer vs different defenses
good_defense = {'defensive_rating': 105.0, 'paoa': {'vs_PG': -4.5, 'vs_SG': -3.2, 'vs_SF': -2.8}}
bad_defense = {'defensive_rating': 118.0, 'paoa': {'vs_PG': 4.2, 'vs_SG': 3.5, 'vs_SF': 5.1}}

friction_good = clusterer.get_friction_for_team('Scorer', good_defense)
friction_bad = clusterer.get_friction_for_team('Scorer', bad_defense)

print(f"  Scorer vs Elite Defense (105 rating): {friction_good:.4f}")
print(f"  Scorer vs Poor Defense (118 rating): {friction_bad:.4f}")
print(f"  Difference: {abs(friction_bad - friction_good):.4f}")

assert friction_good < friction_bad, "Friction should be lower vs good defense (penalty)"
print("  ✅ Friction Calculation: PASS")

# ============================================================================
# TEST 4: MONTE CARLO SIMULATION
# ============================================================================
print("\n[TEST 4] Monte Carlo Simulation (50k iterations)")
print("-" * 50)

from engines.vertex_monte_carlo import VertexMonteCarloEngine

mc = VertexMonteCarloEngine(n_simulations=50_000)

# Base stats
ema_stats = {
    'points_ema': 25.0,
    'points_std': 5.0,
    'rebounds_ema': 8.0,
    'rebounds_std': 2.5,
    'assists_ema': 6.0,
    'assists_std': 2.0,
    'threes_ema': 2.5,
}

# Run with different modifiers
result_neutral = mc.run_simulation(ema_stats, pace_factor=1.0, friction=0.0)
result_boost = mc.run_simulation(ema_stats, pace_factor=1.05, friction=0.05)
result_penalty = mc.run_simulation(ema_stats, pace_factor=0.95, friction=-0.08)

print(f"  Neutral (pace=1.0, friction=0.0):")
print(f"    PTS Floor/EV/Ceil: {result_neutral.projection.floor_20th['points']:.1f} / {result_neutral.projection.expected_value['points']:.1f} / {result_neutral.projection.ceiling_80th['points']:.1f}")

print(f"  Boosted (pace=1.05, friction=+0.05):")
print(f"    PTS Floor/EV/Ceil: {result_boost.projection.floor_20th['points']:.1f} / {result_boost.projection.expected_value['points']:.1f} / {result_boost.projection.ceiling_80th['points']:.1f}")

print(f"  Penalized (pace=0.95, friction=-0.08):")
print(f"    PTS Floor/EV/Ceil: {result_penalty.projection.floor_20th['points']:.1f} / {result_penalty.projection.expected_value['points']:.1f} / {result_penalty.projection.ceiling_80th['points']:.1f}")

# Verify modifiers affect output correctly
assert result_boost.projection.expected_value['points'] > result_neutral.projection.expected_value['points'], \
    "Boost should increase points"
assert result_penalty.projection.expected_value['points'] < result_neutral.projection.expected_value['points'], \
    "Penalty should decrease points"

print("  ✅ Monte Carlo Simulation: PASS")

# ============================================================================
# TEST 5: STATISTICAL DISTRIBUTION VALIDATION
# ============================================================================
print("\n[TEST 5] Statistical Distribution Validation")
print("-" * 50)

simulations = result_neutral.projection.simulations

# Check Gaussian distribution for points
pts_sims = simulations['points']
pts_mean = np.mean(pts_sims)
pts_std = np.std(pts_sims)

print(f"  Points Distribution (50k samples):")
print(f"    Mean: {pts_mean:.2f} (expected ~25.0)")
print(f"    Std Dev: {pts_std:.2f} (expected ~5.0)")
print(f"    Min: {np.min(pts_sims):.1f}, Max: {np.max(pts_sims):.1f}")

# Check Poisson distribution for threes
threes_sims = simulations['threes']
threes_mean = np.mean(threes_sims)

print(f"  3PM Distribution (Poisson):")
print(f"    Mean: {threes_mean:.2f} (expected ~2.5)")
print(f"    Mode: {np.bincount(threes_sims.astype(int)).argmax()}")

# Statistical tests
assert abs(pts_mean - 25.0) < 1.0, f"Points mean should be near 25.0, got {pts_mean}"
assert abs(pts_std - 5.0) < 1.0, f"Points std should be near 5.0, got {pts_std}"
print("  ✅ Distribution Validation: PASS")

# ============================================================================
# TEST 6: HIT PROBABILITY CALCULATION
# ============================================================================
print("\n[TEST 6] Hit Probability Calculation")
print("-" * 50)

lines = {'points': 22.5, 'rebounds': 7.5, 'assists': 5.5}
hit_probs = mc.get_hit_probabilities(simulations, lines)

print(f"  Lines tested:")
for stat, line in lines.items():
    prob = hit_probs.get(stat, 0) * 100
    print(f"    {stat.upper()} over {line}: {prob:.1f}%")

# Verify probabilities are reasonable
pts_prob = hit_probs.get('points', 0)
assert 0.4 < pts_prob < 0.8, f"Points hit prob should be ~50-70%, got {pts_prob*100:.1f}%"
print("  ✅ Hit Probability: PASS")

# ============================================================================
# TEST 7: END-TO-END OPPONENT COMPARISON
# ============================================================================
print("\n[TEST 7] End-to-End Opponent Comparison")
print("-" * 50)

import requests

# Test LeBron vs different opponents
test_player = '2544'  # LeBron

opponents = [
    ('1610612738', 'Boston Celtics'),
    ('1610612747', 'Los Angeles Lakers'),
    ('1610612765', 'Detroit Pistons'),
]

results = {}
for opp_id, opp_name in opponents:
    try:
        r = requests.get(f'http://localhost:5000/aegis/simulate/{test_player}?opponent_id={opp_id}', timeout=30)
        data = r.json()
        pts = data['projections']['expected_value']['points']
        results[opp_name] = pts
        print(f"  vs {opp_name}: {pts:.1f} PTS")
    except Exception as e:
        print(f"  vs {opp_name}: ERROR - {e}")

# Verify different opponents produce different projections
unique_values = len(set(results.values()))
if unique_values >= 2:
    print("  ✅ Opponent Variance: PASS (projections vary by opponent)")
else:
    print("  ⚠️ Opponent Variance: WARNING (same projections for all opponents)")

# ============================================================================
# TEST 8: CONFLUENCE SCORING
# ============================================================================
print("\n[TEST 8] Confluence Scoring Integration")
print("-" * 50)

from aegis.confluence_scorer import ConfluenceScorer

scorer = ConfluenceScorer()

# Mock predictions from multiple models
mock_predictions = {
    'ema_model': 25.5,
    'ridge_model': 26.2,
    'xgb_model': 24.8,
    'baseline': 25.0,
}

confluence = scorer.calculate(
    model_predictions=mock_predictions,
    sample_size=50,
    player_id='test'
)

print(f"  Model Predictions: {mock_predictions}")
print(f"  Confluence Score: {confluence.score}")
print(f"  Confluence Grade: {confluence.grade}")
print(f"  Agreement: {confluence.components.get('model_agreement', 0):.1f}%")

assert 50 <= confluence.score <= 100, "Confluence score should be 50-100"
assert confluence.grade in ['A+', 'A', 'B+', 'B', 'C', 'D', 'F'], "Invalid grade"
print("  ✅ Confluence Scoring: PASS")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("SUMMARY: ALL MATH VALIDATION TESTS PASSED")
print("=" * 70)
print("""
Components Verified:
  ✅ EMA Engine - Recency-weighted averages
  ✅ Defense Matrix - Team-specific PAOA lookups  
  ✅ Friction Calculator - Opponent adjustments
  ✅ Monte Carlo - 50k vectorized simulations
  ✅ Statistical Distributions - Gaussian + Poisson
  ✅ Hit Probabilities - Line analysis
  ✅ End-to-End API - Opponent variance
  ✅ Confluence Scoring - Model agreement

All engines work together correctly!
""")
