"""
Confluence Scorer v3.1
======================
3-variable confidence scoring for projections.

Formula:
Score = 0.40 × Model_Agreement + 0.30 × Sample_Size + 0.30 × Historical_Accuracy
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceResult:
    """Result of confluence calculation"""
    score: float  # 0-100
    grade: str    # 'A', 'B', 'C', 'D', 'F'
    components: Dict[str, float]
    interpretation: str


class ConfluenceScorer:
    """
    3-Variable Confidence Scorer.
    
    Components:
    - Model Agreement (40%): Coefficient of variation of LR/RF/XGB predictions
    - Sample Size (30%): Games in rolling window (max 25)
    - Historical Accuracy (30%): % of past predictions within Floor-Ceiling
    """
    
    WEIGHTS = {
        'model_agreement': 0.40,
        'sample_size': 0.30,
        'historical_accuracy': 0.30
    }
    
    GRADES = {
        'A': (85, 100),
        'B': (70, 85),
        'C': (55, 70),
        'D': (40, 55),
        'F': (0, 40)
    }
    
    def __init__(self, learning_ledger: Optional[Any] = None):
        self.ledger = learning_ledger
    
    def calculate(
        self,
        model_predictions: Dict[str, float],
        sample_size: int,
        player_id: Optional[str] = None
    ) -> ConfluenceResult:
        """
        Calculate confluence confidence score.
        
        Args:
            model_predictions: Dict with 'linear_regression', 'random_forest', 'xgboost' values
            sample_size: Number of games in rolling window
            player_id: For historical accuracy lookup
            
        Returns:
            ConfluenceResult with 0-100 score
        """
        # Component 1: Model Agreement (1 - CV)
        preds = list(model_predictions.values())
        if preds and np.mean(preds) > 0:
            cv = np.std(preds) / np.mean(preds)
            model_agreement = max(0, min(1, 1 - cv)) * 100
        else:
            model_agreement = 50.0
        
        # Component 2: Sample Size (normalized to 25 games)
        max_sample = 25
        sample_component = min(sample_size / max_sample, 1.0) * 100
        
        # Component 3: Historical Accuracy
        if self.ledger and player_id:
            historical_accuracy = self.ledger.get_historical_accuracy(player_id) * 100
        else:
            historical_accuracy = 50.0  # Default for new players
        
        # Weighted sum
        score = (
            model_agreement * self.WEIGHTS['model_agreement'] +
            sample_component * self.WEIGHTS['sample_size'] +
            historical_accuracy * self.WEIGHTS['historical_accuracy']
        )
        
        components = {
            'model_agreement': round(model_agreement, 1),
            'sample_size': round(sample_component, 1),
            'historical_accuracy': round(historical_accuracy, 1)
        }
        
        grade = self._get_grade(score)
        interpretation = self._get_interpretation(score)
        
        return ConfluenceResult(
            score=round(score, 1),
            grade=grade,
            components=components,
            interpretation=interpretation
        )
    
    def _get_grade(self, score: float) -> str:
        """Convert score to letter grade"""
        for grade, (low, high) in self.GRADES.items():
            if low <= score < high:
                return grade
        return 'A' if score >= 100 else 'F'
    
    def _get_interpretation(self, score: float) -> str:
        """Get human-readable interpretation"""
        if score >= 85:
            return "HIGH CONFIDENCE - Strong model consensus, ample data"
        elif score >= 70:
            return "GOOD CONFIDENCE - Reliable projection with some variance"
        elif score >= 55:
            return "MODERATE CONFIDENCE - Exercise caution"
        elif score >= 40:
            return "LOW CONFIDENCE - Limited data or high model variance"
        else:
            return "VERY LOW CONFIDENCE - Consider waiting for more data"
    
    def get_confidence_summary(self, player_id: str) -> Dict:
        """Get detailed confidence analysis for a player"""
        if not self.ledger:
            return {'error': 'No ledger available'}
        
        history = self.ledger.get_player_history(player_id, limit=25)
        
        if not history:
            return {
                'player_id': player_id,
                'games_tracked': 0,
                'historical_accuracy': 0.5,
                'avg_error': None,
                'recommendation': 'New player - limited historical data'
            }
        
        accuracy = sum(1 for h in history if h.get('within_range')) / len(history)
        avg_error = np.mean([h.get('prediction_error', 0) for h in history])
        
        return {
            'player_id': player_id,
            'games_tracked': len(history),
            'historical_accuracy': round(accuracy, 3),
            'avg_error': round(avg_error, 2),
            'recommendation': self._get_recommendation(accuracy, len(history))
        }
    
    def _get_recommendation(self, accuracy: float, sample_size: int) -> str:
        """Generate recommendation based on player's history"""
        if sample_size < 5:
            return "Need more games for reliable projections"
        
        if accuracy >= 0.80:
            return "Highly predictable player - trust projections"
        elif accuracy >= 0.60:
            return "Reasonably predictable - good base for projections"
        elif accuracy >= 0.40:
            return "Volatile performer - use wider Floor/Ceiling"
        else:
            return "Very unpredictable - extreme caution advised"
