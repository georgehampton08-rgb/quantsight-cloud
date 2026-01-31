"""
Archetype Clusterer v3.1
========================
K-Means based player archetype classification.

Replaces hardcoded thresholds with data-driven clustering.
If a player's usage or shot profile shifts, archetype updates dynamically.
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ArchetypeResult:
    """Result of archetype classification"""
    archetype: str
    confidence: float
    method: str  # 'kmeans' or 'fallback'


class ArchetypeClusterer:
    """
    K-Means based player archetype classification.
    
    Clusters players into 6 archetypes based on statistical profile:
    1. Scorer - High PPG, high usage
    2. Playmaker - High APG, high assist ratio
    3. Slasher - High paint touches, FTR
    4. Three-and-D - High 3P%, defensive stats
    5. Rim Protector - High BPG, rebounds
    6. Balanced - No dominant trait
    """
    
    ARCHETYPE_NAMES = [
        'Scorer', 'Playmaker', 'Slasher', 
        'Three-and-D', 'Rim Protector', 'Balanced'
    ]
    
    # Archetype friction matrix: (player_arch, defender_arch) -> modifier
    FRICTION_MATRIX = {
        ('Slasher', 'Rim Protector'): -0.15,
        ('Scorer', 'Perimeter Lock'): -0.12,
        ('Playmaker', 'Ball Hawk'): -0.10,
        ('Three-and-D', 'Close-out Specialist'): -0.08,
        ('Rim Protector', 'Stretch Big'): -0.05,
        ('Scorer', 'Rim Protector'): -0.08,
        ('Slasher', 'Perimeter Lock'): -0.06,
    }
    
    # Fallback thresholds for rule-based classification
    FALLBACK_THRESHOLDS = {
        'Scorer': {'points': 20.0},
        'Playmaker': {'assists': 6.0},
        'Rim Protector': {'blocks': 1.5},
        'Three-and-D': {'three_pct': 0.36, 'steals': 1.0},
        'Slasher': {'ftr': 0.35},
    }
    
    def __init__(self, n_clusters: int = 6):
        self.n_clusters = n_clusters
        self._is_fitted = False
        
        if SKLEARN_AVAILABLE:
            self.kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            self.scaler = StandardScaler()
        else:
            self.kmeans = None
            self.scaler = None
            logger.warning("[ARCHETYPE] sklearn not available, using fallback classification")
    
    def fit(self, league_data: List[Dict]) -> 'ArchetypeClusterer':
        """
        Fit clusterer on league-wide data.
        
        Should be called periodically (daily) with all active players.
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("[ARCHETYPE] Cannot fit - sklearn not available")
            return self
        
        if len(league_data) < self.n_clusters:
            logger.warning(f"[ARCHETYPE] Need at least {self.n_clusters} players to fit")
            return self
        
        features = self._extract_features(league_data)
        scaled = self.scaler.fit_transform(features)
        self.kmeans.fit(scaled)
        self._is_fitted = True
        
        logger.info(f"[ARCHETYPE] Fitted on {len(league_data)} players")
        
        return self
    
    def classify(self, player_stats: Dict) -> ArchetypeResult:
        """
        Classify a player's archetype based on current stats.
        
        Args:
            player_stats: Dictionary with rolling averages
            
        Returns:
            ArchetypeResult with archetype name and confidence
        """
        if self._is_fitted and SKLEARN_AVAILABLE:
            return self._classify_kmeans(player_stats)
        else:
            return self._classify_fallback(player_stats)
    
    def _classify_kmeans(self, stats: Dict) -> ArchetypeResult:
        """K-Means based classification"""
        features = self._extract_single_features(stats)
        scaled = self.scaler.transform([features])
        
        cluster = self.kmeans.predict(scaled)[0]
        
        # Get distance to cluster center for confidence
        center = self.kmeans.cluster_centers_[cluster]
        distance = np.linalg.norm(scaled[0] - center)
        confidence = max(0.5, 1 - distance / 10)  # Normalize
        
        return ArchetypeResult(
            archetype=self.ARCHETYPE_NAMES[cluster],
            confidence=round(confidence, 2),
            method='kmeans'
        )
    
    def _classify_fallback(self, stats: Dict) -> ArchetypeResult:
        """
        Rule-based fallback when K-Means not fitted.
        Uses same logic as v1.0 thresholds.
        """
        pts = stats.get('points_avg', 0) or stats.get('points_ema', 0) or stats.get('pts', 0)
        ast = stats.get('assists_avg', 0) or stats.get('assists_ema', 0) or stats.get('ast', 0)
        blk = stats.get('blocks_avg', 0) or stats.get('blocks_ema', 0) or stats.get('blk', 0)
        stl = stats.get('steals_avg', 0) or stats.get('steals_ema', 0) or stats.get('stl', 0)
        
        three_pct = stats.get('three_p_pct', 0) or stats.get('fg3_pct', 0)
        ftr = stats.get('ftr', stats.get('free_throw_rate', 0))
        
        # Priority-based classification
        if pts >= 20:
            return ArchetypeResult('Scorer', 0.85, 'fallback')
        if ast >= 6:
            return ArchetypeResult('Playmaker', 0.82, 'fallback')
        if blk >= 1.5:
            return ArchetypeResult('Rim Protector', 0.80, 'fallback')
        if three_pct >= 0.36 and stl >= 1.0:
            return ArchetypeResult('Three-and-D', 0.78, 'fallback')
        if ftr >= 0.35:
            return ArchetypeResult('Slasher', 0.75, 'fallback')
        
        return ArchetypeResult('Balanced', 0.70, 'fallback')
    
    def _extract_features(self, league_data: List[Dict]) -> np.ndarray:
        """Extract feature matrix from league data"""
        return np.array([
            self._extract_single_features(p) for p in league_data
        ])
    
    def _extract_single_features(self, stats: Dict) -> List[float]:
        """Extract feature vector for single player"""
        return [
            float(stats.get('points_avg', 0) or stats.get('points_ema', 0) or 0),
            float(stats.get('assists_avg', 0) or stats.get('assists_ema', 0) or 0),
            float(stats.get('rebounds_avg', 0) or stats.get('rebounds_ema', 0) or 0),
            float(stats.get('blocks_avg', 0) or stats.get('blocks_ema', 0) or 0),
            float(stats.get('steals_avg', 0) or stats.get('steals_ema', 0) or 0),
            float(stats.get('three_p_pct', 0) or 0) * 100,
            float(stats.get('usage_rate', 20) or 20),
        ]
    
    def get_friction(self, player_arch: str, defender_arch: str) -> float:
        """Get friction coefficient for archetype matchup"""
        return self.FRICTION_MATRIX.get((player_arch, defender_arch), 0.0)
    
    def get_friction_for_team(self, player_arch: str, team_defense: Dict) -> float:
        """
        Get aggregate friction based on team's defensive metrics.
        
        Uses actual Points Allowed Over Average (PAOA) data to create
        meaningful opponent-specific adjustments.
        
        Args:
            player_arch: Player's archetype
            team_defense: Dict with 'defensive_rating', 'paoa', 'available', etc.
            
        Returns:
            Friction modifier (-0.15 to +0.10) affecting simulation
        """
        # Base friction from archetype matchup
        primary = team_defense.get('primary_archetype', 'Balanced')
        friction = self.get_friction(player_arch, primary)
        
        # PAOA-based adjustment (actual opponent-specific impact)
        # PAOA positive = team allows MORE points = easier matchup
        # PAOA negative = team allows FEWER points = harder matchup
        paoa = team_defense.get('paoa', {})
        
        # Get position-specific PAOA if available
        avg_paoa = 0.0
        if paoa and isinstance(paoa, dict):
            position_values = [v for v in paoa.values() if v != 0.0]
            if position_values:
                avg_paoa = sum(position_values) / len(position_values)
        
        # Convert PAOA to friction adjustment
        # PAOA of +5 (bad defense) = +0.05 (easier game)
        # PAOA of -5 (good defense) = -0.05 (harder game)
        paoa_friction = avg_paoa / 100  # Scale for simulation
        friction += paoa_friction
        
        # Additional defensive rating adjustment
        def_rating = team_defense.get('defensive_rating', 110.0) or 110.0
        
        # Deviation from league average (110)
        # Lower rating = better defense = negative friction
        rating_adjustment = (def_rating - 110) / 200  # ~0.025 per point
        friction += rating_adjustment
        
        # Clamp to reasonable range
        friction = max(-0.15, min(0.10, friction))
        
        logger.info(f"[FRICTION] Archetype={player_arch}, PAOA={avg_paoa:.1f}, "
                    f"DefRating={def_rating:.1f}, TotalFriction={friction:.3f}")
        
        return round(friction, 4)
