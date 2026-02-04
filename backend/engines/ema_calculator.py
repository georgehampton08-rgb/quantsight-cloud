"""
EMA Calculator v3.1
===================
Exponential Moving Average for recency-weighted player baselines.

Mathematical Foundation:
EMA_t = α × X_t + (1-α) × EMA_{t-1}

With α=0.15:
- Most recent game: 15% weight
- 10 games ago: ~3.3% weight
- 25 games ago: ~0.7% weight

Result: ~6x more weight on recent games vs simple average.
"""

import numpy as np
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class EMACalculator:
    """
    Exponential Moving Average Calculator.
    
    Uses α=0.15 decay factor to weight recent performance heavily.
    Balances "Season Soul" with "Current Heat".
    """
    
    def __init__(self, alpha: float = 0.15):
        """
        Args:
            alpha: Smoothing factor (0-1). Higher = more weight on recent.
                   Default 0.15 balances recency with stability.
        """
        self.alpha = alpha
    
    def calculate(self, game_logs: List[Dict]) -> Dict[str, float]:
        """
        Calculate EMA for all tracked statistics.
        
        Args:
            game_logs: List of game dictionaries, ordered newest-first
            
        Returns:
            Dictionary with EMA values and standard deviations
        """
        if not game_logs:
            return self._default_baselines()
        
        # Reverse to process oldest-first (EMA builds forward)
        games = list(reversed(game_logs))
        
        stats = {
            'points': [float(g.get('pts', g.get('points', 0)) or 0) for g in games],
            'rebounds': [float(g.get('reb', g.get('rebounds', 0)) or 0) for g in games],
            'assists': [float(g.get('ast', g.get('assists', 0)) or 0) for g in games],
            'threes': [float(g.get('fg3m', g.get('three_pm', 0)) or 0) for g in games],
            'steals': [float(g.get('stl', g.get('steals', 0)) or 0) for g in games],
            'blocks': [float(g.get('blk', g.get('blocks', 0)) or 0) for g in games],
            'minutes': [float(g.get('min', g.get('minutes', 0)) or 0) for g in games],
        }
        
        result = {}
        for stat_name, values in stats.items():
            if not values:
                continue
            ema = self._compute_ema(np.array(values))
            std = float(np.std(values)) if len(values) > 1 else 0.0
            
            result[f'{stat_name}_ema'] = round(ema, 2)
            result[f'{stat_name}_std'] = round(std, 2)
        
        return result
    
    def _compute_ema(self, values: np.ndarray) -> float:
        """
        Compute EMA using iterative formula.
        
        Formula: EMA_t = α × X_t + (1-α) × EMA_{t-1}
        """
        if len(values) == 0:
            return 0.0
        
        # Initialize EMA with first value
        ema = float(values[0])
        
        # Apply EMA formula iteratively
        for value in values[1:]:
            ema = self.alpha * float(value) + (1 - self.alpha) * ema
        
        return ema
    
    def _default_baselines(self) -> Dict[str, float]:
        """Return league-average baselines when no data available"""
        return {
            'points_ema': 12.0, 'points_std': 5.0,
            'rebounds_ema': 4.5, 'rebounds_std': 2.0,
            'assists_ema': 2.5, 'assists_std': 1.5,
            'threes_ema': 1.2, 'threes_std': 1.0,
            'steals_ema': 0.8, 'steals_std': 0.5,
            'blocks_ema': 0.5, 'blocks_std': 0.4,
            'minutes_ema': 24.0, 'minutes_std': 6.0,
        }
    
    def get_weight_distribution(self, n_games: int = 25) -> List[Dict]:
        """
        Show how weights distribute across games (for debugging).
        
        Returns list of {game_index, weight_pct} for visualization.
        """
        weights = []
        current_weight = self.alpha
        
        for i in range(n_games):
            weights.append({
                'game': i + 1,
                'weight_pct': round(current_weight * 100, 2),
                'label': 'most_recent' if i == 0 else f'{i+1}_games_ago'
            })
            current_weight *= (1 - self.alpha)
        
        return weights
    
    def compare_to_simple_average(self, game_logs: List[Dict]) -> Dict[str, Dict]:
        """
        Compare EMA to simple average for analysis.
        
        Returns:
            {stat: {ema: x, simple_avg: y, delta: z}}
        """
        ema_stats = self.calculate(game_logs)
        
        comparison = {}
        for stat in ['points', 'rebounds', 'assists', 'threes']:
            values = [float(g.get('pts' if stat == 'points' else stat[:3], 0) or 0) 
                     for g in game_logs]
            
            simple_avg = float(np.mean(values)) if values else 0
            ema_val = ema_stats.get(f'{stat}_ema', 0)
            
            comparison[stat] = {
                'ema': ema_val,
                'simple_avg': round(simple_avg, 2),
                'delta': round(ema_val - simple_avg, 2),
                'interpretation': 'Recent form is BETTER' if ema_val > simple_avg else 'Recent form is WORSE'
            }
        
        return comparison
