"""
Test Vertex Matchup Engine
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis.vertex_matchup import VertexMatchupEngine, quick_player_score, compare_stats


async def test_vertex_engine():
    """Test Vertex Matchup Engine functionality"""
    
    print("=" * 60)
    print("VERTEX MATCHUP ENGINE TEST")
    print("=" * 60)
    
    # Initialize engine without router (standalone mode)
    engine = VertexMatchupEngine(
        aegis_router=None,
        health_monitor=None,
        dual_mode=None
    )
    
    print("\n[TEST 1] Quick Player Score")
    print("-" * 40)
    
    # Test stat scoring
    lebron_stats = {
        'points_avg': 25.5,
        'rebounds_avg': 8.2,
        'assists_avg': 7.1,
        'steals_avg': 1.2,
        'blocks_avg': 0.6,
        'fg_pct': 0.52,
        'three_p_pct': 0.38,
        'turnovers_avg': 3.5
    }
    
    curry_stats = {
        'points_avg': 26.8,
        'rebounds_avg': 4.5,
        'assists_avg': 6.1,
        'steals_avg': 0.9,
        'blocks_avg': 0.2,
        'fg_pct': 0.47,
        'three_p_pct': 0.41,
        'turnovers_avg': 3.2
    }
    
    lebron_score = quick_player_score(lebron_stats)
    curry_score = quick_player_score(curry_stats)
    
    print(f"  LeBron Score: {lebron_score}")
    print(f"  Curry Score: {curry_score}")
    
    # Test compare
    winner, ratio = compare_stats(lebron_stats, curry_stats)
    print(f"  Winner: {'LeBron' if winner == 'A' else 'Curry' if winner == 'B' else 'Even'}")
    print(f"  Advantage Ratio: {ratio:.3f}")
    
    print("\n[TEST 2] Category Comparison")
    print("-" * 40)
    
    for stat, weight in VertexMatchupEngine.STAT_WEIGHTS.items():
        if stat in lebron_stats and stat in curry_stats:
            val_l = lebron_stats.get(stat, 0)
            val_c = curry_stats.get(stat, 0)
            winner = 'LeBron' if val_l > val_c else 'Curry' if val_c > val_l else 'Even'
            print(f"  {stat:15s}: LeBron {val_l:5.1f} vs Curry {val_c:5.1f} → {winner}")
    
    print("\n[TEST 3] Engine Stats")
    print("-" * 40)
    
    stats = engine.get_stats()
    print(f"  Matchups Analyzed: {stats['matchups_analyzed']}")
    print(f"  Cache Hits: {stats['cache_hits']}")
    print(f"  Analysis Mode: {stats['analysis_mode']}")
    
    print("\n" + "=" * 60)
    print("✅ VERTEX ENGINE TESTS COMPLETE")
    print("=" * 60)
    
    print("\n[INFO] Note: Full matchup analysis requires active Aegis router")
    print("       Run server.py and test endpoints:")
    print("       - GET /aegis/matchup/player/{a}/vs/{b}")
    print("       - GET /aegis/matchup/team/{a}/vs/{b}")


if __name__ == "__main__":
    asyncio.run(test_vertex_engine())
