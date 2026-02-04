"""
Vertex Monte Carlo Engine v3.1
==============================
High-performance 10,000-iteration Monte Carlo simulation.

Features:
- NumPy vectorization for <500ms execution
- Gaussian distribution for continuous stats (PTS/REB/AST)
- Poisson distribution for discrete stats (3PM/STL/BLK)
- Dependency Injection for testability
"""

import numpy as np
from numpy.random import default_rng
from typing import Dict, List, Optional, Protocol, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# Dependency Injection Protocols
class DataFetcher(Protocol):
    """Interface for data fetching - injectable for testing"""
    async def fetch_player_stats(self, player_id: str, games: int) -> Dict: ...
    async def fetch_team_defense(self, team_id: str) -> Dict: ...
    async def fetch_player_vitals(self, player_id: str) -> Dict: ...


class PaceCalculator(Protocol):
    """Interface for pace normalization - injectable"""
    def calculate_multiplier(self, team_a_pace: float, team_b_pace: float) -> float: ...


@dataclass
class ProjectionMatrix:
    """Output projection with Floor/EV/Ceiling"""
    floor_20th: Dict[str, float]
    expected_value: Dict[str, float]
    ceiling_80th: Dict[str, float]
    simulations: Optional[Dict[str, np.ndarray]] = None
    
    def to_dict(self) -> Dict:
        return {
            'floor': self.floor_20th,
            'ev': self.expected_value,
            'ceiling': self.ceiling_80th
        }


@dataclass
class SimulationResult:
    """Full simulation result with all metadata"""
    projection: ProjectionMatrix
    confluence_score: float
    model_agreement: float
    execution_time_ms: float
    n_simulations: int


class VertexMonteCarloEngine:
    """
    High-Performance Monte Carlo Simulation Engine v3.1
    
    Dependency Injection Points:
    - ema_calculator: For recency-weighted baselines
    - vanguard_forge: For ensemble predictions
    - pace_calculator: For tempo normalization
    
    Distribution Logic:
    - Gaussian: Points, Rebounds, Assists, Minutes (continuous)
    - Poisson: 3PM, Steals, Blocks, Turnovers (discrete counts)
    """
    
    # Distribution type assignment
    GAUSSIAN_STATS = ['points', 'rebounds', 'assists', 'minutes']
    POISSON_STATS = ['threes', 'steals', 'blocks', 'turnovers']
    
    # League average pace for normalization
    LEAGUE_AVG_PACE = 99.5
    
    def __init__(
        self,
        n_simulations: int = 50_000,
        seed: int = 42,
        ema_calculator: Optional[Any] = None,
        vanguard_forge: Optional[Any] = None
    ):
        self.n_simulations = n_simulations
        self.rng = default_rng(seed=seed)
        self.ema = ema_calculator
        self.forge = vanguard_forge
    
    def run_simulation(
        self,
        ema_stats: Dict[str, float],
        pace_factor: float = 1.0,
        friction: float = 0.0,
        fatigue_modifier: float = 0.0,
        usage_boost: float = 0.0,
        volatility_factor: float = 1.0,
        minutes_modifier: float = 1.0
    ) -> SimulationResult:
        """
        Execute vectorized Monte Carlo simulation.
        
        Args:
            ema_stats: EMA-weighted baselines from EMACalculator
            pace_factor: Pace normalization multiplier
            friction: Archetype friction modifier (-ve = penalty)
            fatigue_modifier: Schedule fatigue modifier (B2B penalty)
            usage_boost: Usage vacuum boost from injured teammates
            volatility_factor: Per-player volatility (1.0=normal, >1=more volatile)
            minutes_modifier: Expected minutes ratio (minutes_ema / baseline_minutes)
            
        Returns:
            SimulationResult with projections and metadata
        """
        import time
        start = time.perf_counter()
        
        # Calculate total modifier (includes minutes projection)
        total_modifier = pace_factor * (1 + friction + fatigue_modifier + usage_boost) * minutes_modifier
        
        # Run vectorized Monte Carlo with volatility adjustment
        simulations = self._vectorized_monte_carlo(ema_stats, total_modifier, volatility_factor)
        
        # Calculate projections with dynamic confidence intervals
        projection = self._calculate_projections(simulations, volatility_factor)
        
        # Calculate model agreement (if forge available)
        if self.forge:
            forge_result = self.forge.predict_from_stats(
                ema_stats, pace_factor, friction
            )
            model_agreement = np.mean([
                r.model_agreement for r in forge_result.values()
            ]) if forge_result else 0.85
        else:
            model_agreement = 0.85
        
        execution_time = (time.perf_counter() - start) * 1000
        
        logger.info(f"[VERTEX] Simulation complete in {execution_time:.0f}ms (vol={volatility_factor:.2f}, min={minutes_modifier:.2f})")
        
        return SimulationResult(
            projection=projection,
            confluence_score=0.0,  # Will be set by ConfluenceScorer
            model_agreement=model_agreement,
            execution_time_ms=round(execution_time, 1),
            n_simulations=self.n_simulations
        )
    
    def _vectorized_monte_carlo(
        self,
        baselines: Dict[str, float],
        modifier: float,
        volatility_factor: float = 1.0
    ) -> Dict[str, np.ndarray]:
        """
        NumPy-vectorized simulation - NO PYTHON LOOPS in critical path.
        
        Distribution Logic:
        - Gaussian: For continuous stats where outputs form a bell curve
        - Poisson: For discrete counts where 0 or 1 is most likely
        
        Args:
            baselines: EMA stats dictionary
            modifier: Total modifier (pace * friction * fatigue * minutes)
            volatility_factor: Player-specific variance scaling (>1 = wider, <1 = narrower)
        """
        n = self.n_simulations
        results = {}
        
        # GAUSSIAN STATS (continuous)
        for stat in self.GAUSSIAN_STATS:
            ema_key = f'{stat}_ema'
            std_key = f'{stat}_std'
            
            mean = baselines.get(ema_key, 10.0) * modifier
            # Apply volatility factor to standard deviation
            base_std = baselines.get(std_key, mean * 0.3)
            std = base_std * volatility_factor
            
            # Vectorized Gaussian sampling
            samples = self.rng.normal(mean, std, n)
            
            # Clamp to realistic bounds
            if stat == 'points':
                samples = np.clip(samples, 0, 70)
            elif stat == 'rebounds':
                samples = np.clip(samples, 0, 30)
            elif stat == 'assists':
                samples = np.clip(samples, 0, 25)
            else:
                samples = np.clip(samples, 0, 48)
            
            results[stat] = samples
        
        # POISSON STATS (discrete counts)
        for stat in self.POISSON_STATS:
            ema_key = f'{stat}_ema'
            
            lambda_val = baselines.get(ema_key, 1.0) * modifier
            lambda_val = max(0.1, lambda_val)  # Poisson needs λ > 0
            
            # Vectorized Poisson sampling
            samples = self.rng.poisson(lambda_val, n)
            
            # Clamp to realistic bounds
            if stat == 'threes':
                samples = np.clip(samples, 0, 15)
            else:
                samples = np.clip(samples, 0, 10)
            
            results[stat] = samples
        
        return results
    
    def _calculate_projections(
        self,
        simulations: Dict[str, np.ndarray],
        volatility_factor: float = 1.0
    ) -> ProjectionMatrix:
        """
        Calculate Floor (20th), EV (mean), Ceiling (80th) from simulations.
        
        Dynamically adjusts percentile thresholds based on volatility:
        - High volatility (>1.2): Use 15th/85th for wider bands
        - Normal volatility (0.8-1.2): Use 20th/80th
        - Low volatility (<0.8): Use 25th/75th for narrower bands
        """
        floor = {}
        expected = {}
        ceiling = {}
        
        # Dynamic percentile thresholds based on volatility
        if volatility_factor > 1.2:
            floor_pct, ceil_pct = 15, 85  # Wider bands for volatile players
        elif volatility_factor < 0.8:
            floor_pct, ceil_pct = 25, 75  # Narrower bands for consistent players
        else:
            floor_pct, ceil_pct = 20, 80  # Standard bands
        
        for stat, values in simulations.items():
            floor[stat] = round(float(np.percentile(values, floor_pct)), 1)
            expected[stat] = round(float(np.mean(values)), 1)
            ceiling[stat] = round(float(np.percentile(values, ceil_pct)), 1)
        
        return ProjectionMatrix(
            floor_20th=floor,
            expected_value=expected,
            ceiling_80th=ceiling,
            simulations=simulations
        )
    
    def probability_of_hit(
        self,
        simulations: np.ndarray,
        line: float,
        direction: str = 'over'
    ) -> float:
        """
        Calculate probability of hitting a specific line.
        
        Args:
            simulations: Array of 10,000 simulation results
            line: The line to compare against (e.g., 22.5 points)
            direction: 'over' or 'under'
            
        Returns:
            Probability (0.0 to 1.0)
        """
        if direction == 'over':
            hits = np.sum(simulations > line)
        else:
            hits = np.sum(simulations < line)
        
        return round(float(hits / len(simulations)), 4)
    
    def get_hit_probabilities(
        self,
        simulations: Dict[str, np.ndarray],
        lines: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate hit probabilities for multiple stat lines.
        
        Args:
            simulations: Dict of simulation arrays by stat
            lines: Dict of lines to check (e.g., {'points': 22.5})
            
        Returns:
            Dict of hit probabilities
        """
        probs = {}
        for stat, line in lines.items():
            if stat in simulations:
                probs[stat] = self.probability_of_hit(
                    simulations[stat], line, 'over'
                )
        return probs
