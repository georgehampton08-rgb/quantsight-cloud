"""Quick accuracy comparison test"""
import sys
sys.path.insert(0, '.')
import sqlite3

# Load game logs from production database
conn = sqlite3.connect('data/nba_data.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT 
        player_id, game_date,
        points as pts, rebounds as reb, assists as ast, minutes as min
    FROM player_game_logs 
    WHERE player_id = '2544'
    ORDER BY game_date DESC
    LIMIT 15
""")
game_logs = [dict(row) for row in cursor.fetchall()]
conn.close()

print(f"Testing with LeBron's last {len(game_logs)} games")

# Calculate EMA
from engines.ema_calculator import EMACalculator
ema = EMACalculator(alpha=0.15)
ema_result = ema.calculate(game_logs)

print(f"EMA PTS: {ema_result.get('points_ema', 0):.1f}")
print(f"EMA MIN: {ema_result.get('minutes_ema', 0):.1f}")

# Calculate volatility (CV)
pts_values = [g.get('pts') or 0 for g in game_logs]
pts_mean = sum(pts_values) / len(pts_values)
pts_std = (sum((x - pts_mean) ** 2 for x in pts_values) / len(pts_values)) ** 0.5
cv = pts_std / pts_mean
volatility_factor = 0.8 + (cv * 1.2)
volatility_factor = max(0.7, min(1.5, volatility_factor))

print(f"CV: {cv:.3f}, Volatility Factor: {volatility_factor:.2f}")

# Minutes modifier
minutes_ema = ema_result.get('minutes_ema', 32)
minutes_modifier = minutes_ema / 32.0
minutes_modifier = max(0.5, min(1.3, minutes_modifier))
print(f"Minutes Modifier: {minutes_modifier:.2f}")

# Run simulation with new modifiers
from engines.vertex_monte_carlo import VertexMonteCarloEngine
mc = VertexMonteCarloEngine(n_simulations=50_000)

# OLD way (no volatility/minutes)
result_old = mc.run_simulation(ema_result, pace_factor=1.0, friction=0.0)

# NEW way (with volatility/minutes)  
result_new = mc.run_simulation(
    ema_result, 
    pace_factor=1.0, 
    friction=0.0,
    volatility_factor=volatility_factor,
    minutes_modifier=minutes_modifier
)

floor_old = result_old.projection.floor_20th['points']
ceil_old = result_old.projection.ceiling_80th['points']
floor_new = result_new.projection.floor_20th['points']
ceil_new = result_new.projection.ceiling_80th['points']

print(f"\n--- COMPARISON ---")
print(f"OLD range: {floor_old:.1f} - {ceil_old:.1f} (width: {ceil_old-floor_old:.1f})")
print(f"NEW range: {floor_new:.1f} - {ceil_new:.1f} (width: {ceil_new-floor_new:.1f})")

# Check accuracy for both
within_old = sum(1 for g in game_logs if floor_old <= (g.get('pts') or 0) <= ceil_old)
within_new = sum(1 for g in game_logs if floor_new <= (g.get('pts') or 0) <= ceil_new)

acc_old = (within_old / len(game_logs)) * 100
acc_new = (within_new / len(game_logs)) * 100

print(f"\n--- ACCURACY ---")
print(f"OLD: {within_old}/{len(game_logs)} games ({acc_old:.0f}%)")
print(f"NEW: {within_new}/{len(game_logs)} games ({acc_new:.0f}%)")
print(f"IMPROVEMENT: {acc_new - acc_old:.0f}%")
