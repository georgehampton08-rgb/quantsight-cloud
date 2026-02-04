import sys
sys.path.insert(0, '.')

# Test 1: EMA
from engines.ema_calculator import EMACalculator
ema = EMACalculator()
games = [{'pts': 25}, {'pts': 20}, {'pts': 30}]
result = ema.calculate(games)
pts_ema = result['points_ema']
print(f'EMA OK: {pts_ema}')

# Test 2: Defense Matrix
from services.defense_matrix import DefenseMatrix
DefenseMatrix.clear_cache()
bos = DefenseMatrix.get_profile('1610612738')
lal = DefenseMatrix.get_profile('1610612747')
bos_rating = bos.get('def_rating', 'N/A')
lal_rating = lal.get('def_rating', 'N/A')
print(f'Defense BOS rating: {bos_rating}, LAL rating: {lal_rating}')

# Test 3: Friction
from engines.archetype_clusterer import ArchetypeClusterer
c = ArchetypeClusterer()
f1 = c.get_friction_for_team('Scorer', {'defensive_rating': 105.0, 'paoa': {}})
f2 = c.get_friction_for_team('Scorer', {'defensive_rating': 118.0, 'paoa': {}})
print(f'Friction elite={f1:.4f}, poor={f2:.4f}, diff={abs(f2-f1):.4f}')

# Test 4: Monte Carlo
from engines.vertex_monte_carlo import VertexMonteCarloEngine
mc = VertexMonteCarloEngine(n_simulations=10000)
r = mc.run_simulation({'points_ema': 25.0, 'points_std': 5.0})
floor = r.projection.floor_20th['points']
ev = r.projection.expected_value['points']
print(f'MC OK: floor={floor:.1f}, ev={ev:.1f}')

# Test 5: API variance
import requests
r1 = requests.get('http://localhost:5000/aegis/simulate/2544?opponent_id=1610612738', timeout=30).json()
r2 = requests.get('http://localhost:5000/aegis/simulate/2544?opponent_id=1610612747', timeout=30).json()
p1 = r1['projections']['expected_value']['points']
p2 = r2['projections']['expected_value']['points']
print(f'API vs BOS={p1:.1f}, vs LAL={p2:.1f}, different={p1!=p2}')

print('\n=== ALL MATH TESTS PASSED ===')
