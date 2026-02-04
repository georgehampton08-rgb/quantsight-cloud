"""
Dual-Mode Detection System
Automatically detects ML models and falls back to classic heuristics
"""

import os
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class DualModeDetector:
    """
    Detects available analysis modes and provides fallback logic.
    
    Modes:
    - ML: Machine learning models (scikit-learn, tensorflow, etc.)
    - Classic: Heuristic-based analysis (formulas, statistical methods)
    - Hybrid: Combination of both
    """
    
    def __init__(self, ml_models_dir: Optional[str] = None):
        self.ml_models_dir = Path(ml_models_dir) if ml_models_dir else Path("models")
        self.available_modes = self._detect_modes()
        self.active_mode = self._determine_active_mode()
        
        logger.info(f"DualModeDetector initialized: {self.active_mode} mode active")
        logger.info(f"Available modes: {list(self.available_modes.keys())}")
    
    def _detect_modes(self) -> Dict[str, bool]:
        """
        Detect which analysis modes are available.
        
        Returns:
            Dict of mode availability
        """
        modes = {
            'ml': False,
            'classic': True,  # Always available (fallback)
            'hybrid': False
        }
        
        # Check for ML models
        if self.ml_models_dir.exists():
            ml_files = list(self.ml_models_dir.glob('*.pkl')) + \
                      list(self.ml_models_dir.glob('*.h5')) + \
                      list(self.ml_models_dir.glob('*.joblib'))
            
            if ml_files:
                modes['ml'] = True
                logger.info(f"Found {len(ml_files)} ML model(s)")
        
        # Check for required ML libraries
        try:
            import sklearn
            modes['ml'] = modes['ml'] and True
        except ImportError:
            logger.warning("scikit-learn not available, ML mode disabled")
            modes['ml'] = False
        
        # Hybrid available if both ML and classic work
        modes['hybrid'] = modes['ml'] and modes['classic']
        
        return modes
    
    def _determine_active_mode(self) -> str:
        """
        Determine which mode to use as primary.
        
        Priority:
        1. Hybrid (if both available)
        2. ML (if models available)
        3. Classic (fallback)
        """
        if self.available_modes['hybrid']:
            return 'hybrid'
        elif self.available_modes['ml']:
            return 'ml'
        else:
            return 'classic'
    
    def get_analysis_mode(self, requested_mode: Optional[str] = None) -> str:
        """
        Get the analysis mode to use for a request.
        
        Args:
            requested_mode: Mode requested by caller ('ml', 'classic', 'hybrid')
            
        Returns:
            Mode to use (with fallback if requested not available)
        """
        if not requested_mode:
            return self.active_mode
        
        # If requested mode is available, use it
        if self.available_modes.get(requested_mode, False):
            return requested_mode
        
        # Otherwise, fall back
        logger.warning(f"Requested mode '{requested_mode}' not available, "
                      f"falling back to {self.active_mode}")
        return self.active_mode
    
    def should_use_ml(self, context: Optional[Dict] = None) -> bool:
        """
        Decision: Should ML be used for this request?
        
        Args:
            context: Optional context about the request
            
        Returns:
            True if ML should be used
        """
        mode = self.active_mode
        
        # In classic mode, never use ML
        if mode == 'classic':
            return False
        
        # In ML or hybrid mode, use ML
        return True
    
    def get_fallback_chain(self) -> list[str]:
        """
        Get the fallback chain for analysis.
        
        Returns:
            List of modes to try in order
        """
        if self.active_mode == 'hybrid':
            return ['ml', 'classic']
        elif self.active_mode == 'ml':
            return ['ml', 'classic']
        else:
            return ['classic']
    
    def get_status(self) -> dict:
        """Return detector status for monitoring"""
        return {
            'active_mode': self.active_mode,
            'available_modes': self.available_modes,
            'ml_models_dir': str(self.ml_models_dir),
            'ml_models_found': len(list(self.ml_models_dir.glob('*.pkl'))) if self.ml_models_dir.exists() else 0
        }


class ClassicAnalyzer:
    """
    Classic heuristic-based analysis fallback.
    
    Uses statistical formulas and rule-based logic when ML is unavailable.
    """
    
    @staticmethod
    def analyze_player_performance(stats: dict) -> dict:
        """
        Classic performance analysis using formulas.
        
        Args:
            stats: Player statistics
            
        Returns:
            Analysis results
        """
        ppg = stats.get('points_avg', 0)
        rpg = stats.get('rebounds_avg', 0)
        apg = stats.get('assists_avg', 0)
        
        # Simple PER-like calculation
        efficiency = (ppg + rpg + apg) / 3
        
        # Classification based on thresholds
        if efficiency > 20:
            tier = 'Elite'
        elif efficiency > 15:
            tier = 'All-Star'
        elif efficiency > 10:
            tier = 'Starter'
        else:
            tier = 'Role Player'
        
        return {
            'method': 'classic_heuristic',
            'efficiency_score': round(efficiency, 2),
            'tier': tier,
            'confidence': 0.75  # Classic methods have moderate confidence
        }
    
    @staticmethod
    def predict_performance(stats: dict, context: dict) -> dict:
        """
        Classic performance prediction using linear extrapolation.
        
        Args:
            stats: Historical statistics
            context: Context (opponent, home/away, etc.)
            
        Returns:
            Prediction
        """
        ppg = stats.get('points_avg', 15)
        
        # Simple adjustments based on context
        adjustment = 0
        
        if context.get('home_game'):
            adjustment += 2  # Home court advantage
        
        if context.get('opponent_defense') == 'weak':
            adjustment += 3
        elif context.get('opponent_defense') == 'strong':
            adjustment -= 3
        
        predicted_points = ppg + adjustment
        
        return {
            'method': 'classic_formula',
            'predicted_points': round(predicted_points, 1),
            'confidence': 0.70,
            'adjustments': {
                'home_advantage': 2 if context.get('home_game') else 0,
                'opponent_defense': adjustment - (2 if context.get('home_game') else 0)
            }
        }
