"""Multi-player accuracy test"""
import sys
sys.path.insert(0, '.')
import sqlite3

from engines.ema_calculator import EMACalculator
from engines.vertex_monte_carlo import VertexMonteCarloEngine

conn = sqlite3.connect('data/nba_data.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get players with most game logs
cursor.execute("""
    SELECT player_id, COUNT(*) as games 
    FROM player_game_logs 
    GROUP BY player_id 
    HAVING games >= 10 
    ORDER BY games DESC 
    LIMIT 10
""")
players = cursor.fetchall()

print("Multi-Player Accuracy Test")
print("=" * 60)

ema = EMACalculator(alpha=0.15)
mc = VertexMonteCarloEngine(n_simulations=25_000)

results = []

for p in players:
    player_id = p['player_id']
    
    cursor.execute("""
        SELECT 
            player_id, game_date,
            points as pts, rebounds as reb, assists as ast, minutes as min
        FROM player_game_logs 
        WHERE player_id = ?
        ORDER BY game_date DESC
        LIMIT 15
    """, (player_id,))
    game_logs = [dict(row) for row in cursor.fetchall()]
    
    if len(game_logs) < 5:
        continue
    
    # Calculate EMA
    ema_result = ema.calculate(game_logs)
    
    # Calculate volatility
    pts_values = [g.get('pts') or 0 for g in game_logs]
    pts_mean = sum(pts_values) / len(pts_values) if pts_values else 1
    if pts_mean == 0:
        pts_mean = 1
    pts_std = (sum((x - pts_mean) ** 2 for x in pts_values) / len(pts_values)) ** 0.5
    cv = pts_std / pts_mean
    volatility_factor = 0.8 + (cv * 1.2)
    volatility_factor = max(0.7, min(1.5, volatility_factor))
    
    # Minutes modifier
    minutes_ema = ema_result.get('minutes_ema', 32) or 32
    minutes_modifier = minutes_ema / 32.0
    minutes_modifier = max(0.5, min(1.3, minutes_modifier))
    
    # OLD simulation
    result_old = mc.run_simulation(ema_result)
    floor_old = result_old.projection.floor_20th['points']
    ceil_old = result_old.projection.ceiling_80th['points']
    
    # NEW simulation
    result_new = mc.run_simulation(
        ema_result,
        volatility_factor=volatility_factor,
        minutes_modifier=minutes_modifier
    )
    floor_new = result_new.projection.floor_20th['points']
    ceil_new = result_new.projection.ceiling_80th['points']
    
    # Check accuracy
    within_old = sum(1 for g in game_logs if floor_old <= (g.get('pts') or 0) <= ceil_old)
    within_new = sum(1 for g in game_logs if floor_new <= (g.get('pts') or 0) <= ceil_new)
    
    acc_old = (within_old / len(game_logs)) * 100
    acc_new = (within_new / len(game_logs)) * 100
    
    results.append({
        'player_id': player_id,
        'games': len(game_logs),
        'cv': cv,
        'vol_factor': volatility_factor,
        'acc_old': acc_old,
        'acc_new': acc_new,
        'improvement': acc_new - acc_old
    })
    
    print(f"Player {player_id}: CV={cv:.2f}, Vol={volatility_factor:.2f}, OLD={acc_old:.0f}%, NEW={acc_new:.0f}%")

conn.close()

# Summary
print("\n" + "=" * 60)
avg_old = sum(r['acc_old'] for r in results) / len(results)
avg_new = sum(r['acc_new'] for r in results) / len(results)
avg_improvement = sum(r['improvement'] for r in results) / len(results)

print(f"Average OLD accuracy: {avg_old:.1f}%")
print(f"Average NEW accuracy: {avg_new:.1f}%")
print(f"Average IMPROVEMENT: {avg_improvement:.1f}%")
