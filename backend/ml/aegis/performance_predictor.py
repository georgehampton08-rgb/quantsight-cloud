"""
Phase 9 — Aegis ML Performance Predictor
===========================================
Scikit-learn based player performance predictor for Aegis simulation.

Blends ML predictions with existing Monte Carlo simulation results:
    - 0.6 weight ML prediction + 0.4 weight rule-based simulation
    
Feature vector: 12 player stats + 4 opponent defense features
(matches sim_adapter.py schema exactly)
"""

import os
import io
import functools
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger("ml.aegis.performance_predictor")

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
GCS_BUCKET = os.getenv("ML_ARTIFACTS_BUCKET", "quantsight-ml-artifacts")
GCS_MODEL_BLOB = "models/aegis_predictor/latest.joblib"
ML_WEIGHT = 0.6
RULE_WEIGHT = 0.4

# Feature order must match training
PLAYER_FEATURES = [
    "pts_ema", "reb_ema", "ast_ema",
    "stl_ema", "blk_ema", "tov_ema",
    "pts_std", "reb_std", "ast_std",
    "min_ema", "fga_ema", "fg_pct_ema",
]

OPPONENT_FEATURES = [
    "def_rating", "pace", "opp_fg_pct", "opp_3pt_pct",
]

ALL_FEATURES = PLAYER_FEATURES + OPPONENT_FEATURES


class AegisPerformancePredictor:
    """ML-enhanced performance prediction for Aegis simulation.
    
    Predicts player stat projections and blends with rule-based
    Monte Carlo simulation results.
    """
    
    def __init__(self):
        self._model = None
        self._loaded = False
        self._load_error: Optional[str] = None
    
    @property
    def is_loaded(self) -> bool:
        return self._loaded and self._model is not None
    
    def _try_load(self) -> bool:
        """Try loading the Aegis predictor model."""
        if self._loaded:
            return self._model is not None
        
        self._loaded = True
        
        try:
            import joblib
            
            # Try local artifacts first
            local_path = os.path.join(
                os.path.dirname(__file__), "..", "ml_artifacts", "aegis_predictor.joblib"
            )
            if os.path.exists(local_path):
                self._model = joblib.load(local_path)
                logger.info(f"Aegis predictor loaded from: {local_path}")
                return True
            
            # Try /tmp cache
            tmp_path = "/tmp/ml_models/aegis_predictor.joblib"
            if os.path.exists(tmp_path):
                self._model = joblib.load(tmp_path)
                logger.info(f"Aegis predictor loaded from cache: {tmp_path}")
                return True
            
            # Try GCS
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET)
            blob = bucket.blob(GCS_MODEL_BLOB)
            
            if blob.exists():
                model_bytes = blob.download_as_bytes()
                self._model = joblib.load(io.BytesIO(model_bytes))
                
                os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
                with open(tmp_path, "wb") as f:
                    f.write(model_bytes)
                
                logger.info(f"Aegis predictor loaded from GCS")
                return True
            
            self._load_error = "Model not found"
            return False
            
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"Aegis predictor load failed: {e}")
            return False
    
    def predict(
        self,
        player_stats: Dict[str, float],
        opponent_stats: Dict[str, float],
    ) -> Optional[Dict[str, float]]:
        """Generate ML performance prediction.
        
        Args:
            player_stats: Player feature dict (12 features)
            opponent_stats: Opponent defense features (4 features)
            
        Returns:
            Prediction dict with floor/expected/ceiling, or None
        """
        if not self._try_load():
            return None
        
        try:
            # Build feature vector in correct order
            features = []
            for feat in PLAYER_FEATURES:
                features.append(float(player_stats.get(feat, 0.0)))
            for feat in OPPONENT_FEATURES:
                features.append(float(opponent_stats.get(feat, 0.0)))
            
            X = np.array([features])
            prediction = self._model.predict(X)[0]
            
            # Assume model predicts expected value
            expected = float(prediction)
            pts_std = float(player_stats.get("pts_std", 5.0))
            
            return {
                "floor": round(max(0, expected - 1.5 * pts_std), 1),
                "expected_value": round(expected, 1),
                "ceiling": round(expected + 1.5 * pts_std, 1),
                "ml_confidence": 0.75,
                "source": "ml_predictor",
            }
            
        except Exception as e:
            logger.warning(f"Aegis ML prediction failed: {e}")
            return None
    
    def blend_with_simulation(
        self,
        ml_prediction: Dict[str, float],
        simulation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Blend ML prediction with Monte Carlo simulation result.
        
        Weight: 0.6 ML + 0.4 Simulation
        
        Args:
            ml_prediction: ML output with floor/expected/ceiling
            simulation_result: Rule-based sim output
            
        Returns:
            Blended result dictionary
        """
        sim_floor = float(simulation_result.get("projections", {}).get("floor", 0))
        sim_ev = float(simulation_result.get("projections", {}).get("expected_value", 0))
        sim_ceiling = float(simulation_result.get("projections", {}).get("ceiling", 0))
        
        blended = {
            "floor": round(ML_WEIGHT * ml_prediction["floor"] + RULE_WEIGHT * sim_floor, 1),
            "expected_value": round(ML_WEIGHT * ml_prediction["expected_value"] + RULE_WEIGHT * sim_ev, 1),
            "ceiling": round(ML_WEIGHT * ml_prediction["ceiling"] + RULE_WEIGHT * sim_ceiling, 1),
            "ml_weight": ML_WEIGHT,
            "sim_weight": RULE_WEIGHT,
            "source": "ml_blended",
        }
        
        return blended


# ─────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────
_predictor: Optional[AegisPerformancePredictor] = None


def get_aegis_predictor() -> AegisPerformancePredictor:
    """Get or create the global Aegis predictor."""
    global _predictor
    if _predictor is None:
        _predictor = AegisPerformancePredictor()
    return _predictor
