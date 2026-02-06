"""
Benchmark simulation times at different scales
"""
import numpy as np
import time

print("=" * 50)
print("MONTE CARLO SIMULATION BENCHMARK")
print("=" * 50)

for n in [10_000, 100_000, 1_000_000, 10_000_000, 50_000_000]:
    start = time.perf_counter()
    
    # Simulate points
    pts = np.random.normal(25, 5, size=n)
    reb = np.random.normal(8, 2, size=n)
    ast = np.random.normal(6, 2, size=n)
    
    # Calculate percentiles
    p20_pts = np.percentile(pts, 20)
    p50_pts = np.percentile(pts, 50)
    p80_pts = np.percentile(pts, 80)
    
    elapsed = (time.perf_counter() - start) * 1000
    
    print(f"{n:>15,} sims: {elapsed:>8.1f}ms")

print("=" * 50)
