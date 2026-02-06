"""
Compare 10k vs 50k Monte Carlo simulations.
Shows difference in projection accuracy and execution time.
"""
import sys
import time
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "aegis"))
sys.path.insert(0, str(Path(__file__).parent / "engines"))

import asyncio

def run_comparison():
    from aegis.orchestrator import AegisOrchestrator, OrchestratorConfig
    
    # Players to test (correct IDs with game log data)
    test_players = [
        ("1628389", "1610612741", "Bam Adebayo vs CHI"),
        ("1629632", "1610612748", "Coby White vs MIA"),
    ]
    
    print("=" * 70)
    print("MONTE CARLO SIMULATION COMPARISON: 10k vs 50k")
    print("=" * 70)
    
    for player_id, opponent_id, label in test_players:
        print(f"\n{'=' * 70}")
        print(f"Player: {label}")
        print("=" * 70)
        
        results = {}
        
        for n_sims in [10_000, 50_000]:
            print(f"\n--- {n_sims:,} Simulations ---")
            
            # Create orchestrator with specific sim count
            config = OrchestratorConfig(n_simulations=n_sims)
            orchestrator = AegisOrchestrator(config)
            
            # Run simulation
            start = time.time()
            result = asyncio.run(orchestrator.run_simulation(player_id, opponent_id))
            elapsed = time.time() - start
            
            # Result is a FullSimulationResult dataclass
            floor = result.floor
            ev = result.expected_value
            ceiling = result.ceiling
            
            results[n_sims] = {
                'pts_floor': floor.get('points', 0),
                'pts_ev': ev.get('points', 0),
                'pts_ceiling': ceiling.get('points', 0),
                'reb_ev': ev.get('rebounds', 0),
                'ast_ev': ev.get('assists', 0),
                'time': elapsed
            }
            
            print(f"  Time: {elapsed:.2f}s")
            print(f"  PTS: {floor.get('points', 0):.1f} / {ev.get('points', 0):.1f} / {ceiling.get('points', 0):.1f}")
            print(f"  REB: {floor.get('rebounds', 0):.1f} / {ev.get('rebounds', 0):.1f} / {ceiling.get('rebounds', 0):.1f}")
            print(f"  AST: {floor.get('assists', 0):.1f} / {ev.get('assists', 0):.1f} / {ceiling.get('assists', 0):.1f}")
        
        # Show difference
        r10k = results[10_000]
        r50k = results[50_000]
        
        print(f"\n--- DIFFERENCE (50k - 10k) ---")
        print(f"  PTS Floor:   {r50k['pts_floor'] - r10k['pts_floor']:+.2f}")
        print(f"  PTS EV:      {r50k['pts_ev'] - r10k['pts_ev']:+.2f}")
        print(f"  PTS Ceiling: {r50k['pts_ceiling'] - r10k['pts_ceiling']:+.2f}")
        print(f"  REB EV:      {r50k['reb_ev'] - r10k['reb_ev']:+.2f}")
        print(f"  AST EV:      {r50k['ast_ev'] - r10k['ast_ev']:+.2f}")
        print(f"  Time:        {r50k['time'] - r10k['time']:+.2f}s (10k: {r10k['time']:.2f}s, 50k: {r50k['time']:.2f}s)")
    
    print("\n" + "=" * 70)
    print("COMPARISON COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_comparison()
