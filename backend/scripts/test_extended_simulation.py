"""
Extended Deep Simulation - 2-3 minute runtime target
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from engines.deep_monte_carlo import DeepMonteCarloEngine
import numpy as np
import time

print("=" * 70)
print(" 🎯 EXTENDED DEEP MONTE CARLO SIMULATION")
print(" Target runtime: 2-3 minutes")
print("=" * 70)

# 500,000 games with extra processing
N_GAMES = 500_000
POSSESSIONS = 100

print(f"\n🏀 Simulating LeBron James projection...")
print(f"   Games: {N_GAMES:,}")
print(f"   Possessions/game: {POSSESSIONS}")
print(f"   Total decisions: {N_GAMES * POSSESSIONS:,}")
print()

# Run simulation manually for more control
start = time.perf_counter()

# Initialize stats arrays
points = np.zeros(N_GAMES)
rebounds = np.zeros(N_GAMES)
assists = np.zeros(N_GAMES)
threes = np.zeros(N_GAMES)

# Base rates
pts_mean, pts_std = 28.0, 5.0
reb_mean, reb_std = 8.0, 2.0
ast_mean, ast_std = 8.0, 2.5
fg3_mean = 2.5

# Progress tracking
checkpoints = [N_GAMES // 10 * i for i in range(1, 11)]

for i in range(N_GAMES):
    # Simulate game with per-possession variance
    game_pts = 0
    game_reb = 0
    game_ast = 0
    game_3pm = 0
    
    for poss in range(POSSESSIONS):
        # Each possession has outcomes
        if np.random.random() < 0.15:  # FG attempt
            if np.random.random() < 0.52:  # Made
                game_pts += 2
        elif np.random.random() < 0.10:  # 3pt attempt
            if np.random.random() < 0.38:
                game_pts += 3
                game_3pm += 1
        if np.random.random() < 0.08:  # FT
            game_pts += 1
        if np.random.random() < 0.12:
            game_reb += 1
        if np.random.random() < 0.06:
            game_ast += 1
    
    points[i] = game_pts
    rebounds[i] = game_reb
    assists[i] = game_ast
    threes[i] = game_3pm
    
    # Progress update
    if i + 1 in checkpoints:
        elapsed = time.perf_counter() - start
        pct = (i + 1) / N_GAMES * 100
        remaining = elapsed / (i + 1) * (N_GAMES - i - 1)
        print(f"   {pct:.0f}% complete ({elapsed:.1f}s elapsed, ~{remaining:.1f}s remaining)")

total_time = time.perf_counter() - start

print(f"\n{'=' * 70}")
print(" EXTENDED SIMULATION COMPLETE")
print('=' * 70)

print("\n📊 LeBron James Projection (500,000 simulated games):")
print(f"   {'Stat':<12} {'10th':>8} {'20th':>8} {'EV':>8} {'80th':>8} {'90th':>8}")
print(f"   {'-'*52}")

for stat_name, stat_arr in [('Points', points), ('Rebounds', rebounds), 
                             ('Assists', assists), ('Threes', threes)]:
    print(f"   {stat_name:<12} "
          f"{np.percentile(stat_arr, 10):>8.1f} "
          f"{np.percentile(stat_arr, 20):>8.1f} "
          f"{np.mean(stat_arr):>8.1f} "
          f"{np.percentile(stat_arr, 80):>8.1f} "
          f"{np.percentile(stat_arr, 90):>8.1f}")

print(f"\n⏱️  Total Execution Time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
print("=" * 70)

print(f"\n⏱️  Total Execution Time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
print("=" * 70)
