"""
Test Aegis Simulation with 5 Real NBA Players
==============================================
Verifies that projections are calculated using real player data
and produces unique results for each player.
"""
import asyncio
import sqlite3
from datetime import date
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from aegis.orchestrator import AegisOrchestrator, OrchestratorConfig


def get_test_players():
    """Get 5 diverse players from the database"""
    db_path = Path(__file__).parent / 'data' / 'nba_data.db'
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get 5 players with game data - diverse positions
    cursor.execute("""
        SELECT DISTINCT p.player_id, p.name, p.team_id, p.position
        FROM players p
        JOIN game_logs g ON p.player_id = g.player_id
        WHERE p.name IN ('LeBron James', 'Stephen Curry', 'Nikola Jokic', 'Jayson Tatum', 'Anthony Edwards')
        LIMIT 5
    """)
    
    players = cursor.fetchall()
    conn.close()
    
    if len(players) < 5:
        # Fallback: get any 5 players with game logs
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT p.player_id, p.name, p.team_id, p.position
            FROM players p
            JOIN game_logs g ON p.player_id = g.player_id
            LIMIT 5
        """)
        players = cursor.fetchall()
        conn.close()
    
    return [dict(p) for p in players]


def get_player_recent_stats(player_id: str):
    """Get player's recent game averages for comparison"""
    db_path = Path(__file__).parent / 'data' / 'nba_data.db'
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            AVG(pts) as avg_pts,
            AVG(reb) as avg_reb,
            AVG(ast) as avg_ast,
            AVG(fg3m) as avg_threes,
            COUNT(*) as games
        FROM game_logs
        WHERE player_id = ?
        ORDER BY game_date DESC
        LIMIT 10
    """, (str(player_id),))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'avg_pts': round(row['avg_pts'] or 0, 1),
            'avg_reb': round(row['avg_reb'] or 0, 1),
            'avg_ast': round(row['avg_ast'] or 0, 1),
            'avg_threes': round(row['avg_threes'] or 0, 1),
            'games': row['games'] or 0
        }
    return None


async def run_simulation_test():
    """Run simulation test for 5 players"""
    print("=" * 80)
    print("AEGIS SIMULATION TEST - 5 REAL NBA PLAYERS")
    print("=" * 80)
    
    # Get test players
    players = get_test_players()
    if not players:
        print("[ERROR] No players found in database!")
        return
    
    print(f"\nFound {len(players)} players to test:\n")
    for p in players:
        print(f"  - {p['name']} ({p['position']}) - ID: {p['player_id']}")
    
    # Initialize orchestrator with small simulation count for speed
    config = OrchestratorConfig(
        n_simulations=1000,  # Fewer for test speed
        cache_enabled=False   # Fresh calculations
    )
    orchestrator = AegisOrchestrator(config)
    
    # Use Boston Celtics as opponent for all tests
    opponent_id = "1610612738"  # Boston
    game_date = date.today()
    
    print(f"\nOpponent: Boston Celtics ({opponent_id})")
    print(f"Game Date: {game_date}")
    print("\n" + "=" * 80)
    
    results = []
    
    for player in players:
        player_id = str(player['player_id'])
        player_name = player['name']
        
        print(f"\n[TESTING] {player_name}")
        print("-" * 40)
        
        # Get actual recent stats
        recent = get_player_recent_stats(player_id)
        if recent:
            print(f"  Recent L10 Averages: {recent['avg_pts']} pts, "
                  f"{recent['avg_reb']} reb, {recent['avg_ast']} ast, "
                  f"{recent['avg_threes']} 3PM ({recent['games']} games)")
        
        try:
            # Run simulation
            result = await orchestrator.run_simulation(
                player_id=player_id,
                opponent_id=opponent_id,
                game_date=game_date
            )
            
            # Display projections
            print(f"\n  SIMULATION RESULTS:")
            print(f"    Floor (20th):     PTS={result.floor.get('points', 0):.1f}, "
                  f"REB={result.floor.get('rebounds', 0):.1f}, "
                  f"AST={result.floor.get('assists', 0):.1f}, "
                  f"3PM={result.floor.get('threes', 0):.1f}")
            print(f"    Expected Value:   PTS={result.expected_value.get('points', 0):.1f}, "
                  f"REB={result.expected_value.get('rebounds', 0):.1f}, "
                  f"AST={result.expected_value.get('assists', 0):.1f}, "
                  f"3PM={result.expected_value.get('threes', 0):.1f}")
            print(f"    Ceiling (80th):   PTS={result.ceiling.get('points', 0):.1f}, "
                  f"REB={result.ceiling.get('rebounds', 0):.1f}, "
                  f"AST={result.ceiling.get('assists', 0):.1f}, "
                  f"3PM={result.ceiling.get('threes', 0):.1f}")
            
            print(f"\n  MODIFIERS:")
            print(f"    Archetype: {result.archetype}")
            print(f"    Fatigue Modifier: {result.fatigue_modifier:.2f}")
            print(f"    Usage Boost: {result.usage_boost:.3f}")
            
            print(f"\n  CONFIDENCE:")
            print(f"    Score: {result.confluence_score:.1f}%")
            print(f"    Grade: {result.confluence_grade}")
            
            print(f"\n  Execution Time: {result.execution_time_ms:.0f}ms")
            
            results.append({
                'name': player_name,
                'floor_pts': result.floor.get('points', 0),
                'ev_pts': result.expected_value.get('points', 0),
                'ceiling_pts': result.ceiling.get('points', 0),
                'confluence': result.confluence_score,
                'archetype': result.archetype
            })
            
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            results.append({'name': player_name, 'error': str(e)})
    
    # Summary comparison
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print(f"\n{'Player':<25} {'Floor':<8} {'EV':<8} {'Ceiling':<8} {'Confluence':<12} {'Archetype':<15}")
    print("-" * 80)
    
    for r in results:
        if 'error' in r:
            print(f"{r['name']:<25} ERROR: {r['error'][:40]}")
        else:
            print(f"{r['name']:<25} {r['floor_pts']:<8.1f} {r['ev_pts']:<8.1f} "
                  f"{r['ceiling_pts']:<8.1f} {r['confluence']:<12.1f} {r['archetype']:<15}")
    
    # Verify results are different
    ev_pts_values = [r.get('ev_pts', 0) for r in results if 'error' not in r]
    if len(set(ev_pts_values)) == len(ev_pts_values):
        print("\n[OK] All players have UNIQUE projections - simulation is using player-specific data!")
    else:
        print("\n[WARN] Some players have identical projections - check data sources")
    
    print("\n" + "=" * 80)
    print("WHERE TO VIEW PROJECTIONS IN THE APP:")
    print("=" * 80)
    print("""
1. PLAYER LAB (Player Profile Page)
   - Select any player via Omni-Search
   - Click 'Run Simulation' button or go to Monte Carlo tab
   - Shows Floor/EV/Ceiling for all stats
   
2. MATCHUP LAB
   - Select player and opponent team
   - Click 'Simulate Matchup' 
   - Shows head-to-head adjusted projections

3. API ENDPOINT
   - GET /aegis/simulate/{player_id}?opponent_id={team_id}
   - Returns full projection JSON with all modifiers
   
4. TEAM CENTRAL (Coming)
   - Full roster projections for today's games
""")


if __name__ == "__main__":
    asyncio.run(run_simulation_test())
