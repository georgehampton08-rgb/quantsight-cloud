"""
Phase 9 — ML Drift Detector
==============================
Monitors feature distribution and prediction drift over time.

Drift Types:
    1. Feature Drift — Input feature distributions shift
    2. Prediction Drift — Model output distribution shifts
    3. Performance Drift — Accuracy degrades over time

Uses Population Stability Index (PSI) for distribution comparison.
"""

import logging
from collections import deque
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger("vanguard.ml.drift_detector")


def _psi(reference: np.ndarray, current: np.ndarray, buckets: int = 10) -> float:
    """Calculate Population Stability Index (PSI) between two distributions.
    
    PSI < 0.1: No significant drift
    PSI 0.1-0.25: Moderate drift (investigation recommended)
    PSI > 0.25: Significant drift (retrain recommended)
    
    Args:
        reference: Reference distribution (training data)
        current: Current distribution (recent predictions)
        buckets: Number of histogram buckets
        
    Returns:
        PSI score (0+, lower = less drift)
    """
    if len(reference) < 10 or len(current) < 10:
        return 0.0  # Not enough data
    
    # Use reference distribution to define bucket boundaries
    breakpoints = np.percentile(reference, np.linspace(0, 100, buckets + 1))
    breakpoints = np.unique(breakpoints)
    
    if len(breakpoints) < 2:
        return 0.0
    
    ref_hist, _ = np.histogram(reference, bins=breakpoints)
    cur_hist, _ = np.histogram(current, bins=breakpoints)
    
    # Avoid division by zero
    ref_pct = (ref_hist + 1) / (len(reference) + len(breakpoints))
    cur_pct = (cur_hist + 1) / (len(current) + len(breakpoints))
    
    psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return float(psi)


class DriftDetector:
    """Monitors ML model drift for both incident classifier and Aegis predictor.
    
    Maintains rolling windows of feature values and predictions to
    detect distribution shifts over time.
    """
    
    WINDOW_SIZE = 500  # Keep last 500 predictions for comparison
    
    def __init__(self):
        # Per-model drift tracking
        self._feature_windows: Dict[str, Dict[str, deque]] = {}
        self._prediction_windows: Dict[str, deque] = {}
        self._reference_distributions: Dict[str, Dict[str, np.ndarray]] = {}
        self._last_drift_check: Dict[str, float] = {}
        self._drift_scores: Dict[str, float] = {}
    
    def record_prediction(
        self,
        model_name: str,
        features: Dict[str, float],
        prediction: Any,
        confidence: float = 0.0,
    ):
        """Record a prediction for drift monitoring.
        
        Args:
            model_name: e.g., "incident_classifier" or "aegis_predictor"
            features: Feature dict used for this prediction
            prediction: The model's output
            confidence: Prediction confidence (0-1)
        """
        # Initialize windows if needed
        if model_name not in self._feature_windows:
            self._feature_windows[model_name] = {}
        if model_name not in self._prediction_windows:
            self._prediction_windows[model_name] = deque(maxlen=self.WINDOW_SIZE)
        
        # Record feature values
        for feat_name, feat_value in features.items():
            if feat_name not in self._feature_windows[model_name]:
                self._feature_windows[model_name][feat_name] = deque(maxlen=self.WINDOW_SIZE)
            self._feature_windows[model_name][feat_name].append(float(feat_value))
        
        # Record prediction confidence
        self._prediction_windows[model_name].append(confidence)
    
    def set_reference_distribution(
        self,
        model_name: str,
        feature_distributions: Dict[str, List[float]],
    ):
        """Set reference distributions from training data.
        
        Args:
            model_name: Model identifier
            feature_distributions: Feature name → list of values from training set
        """
        self._reference_distributions[model_name] = {
            name: np.array(vals) for name, vals in feature_distributions.items()
        }
        logger.info(
            f"Reference distributions set for {model_name}: "
            f"{len(feature_distributions)} features"
        )
    
    def check_drift(self, model_name: str) -> Dict[str, Any]:
        """Check for drift on a specific model.
        
        Returns:
            Drift report with per-feature and aggregate scores
        """
        result = {
            "model_name": model_name,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "overall_drift_score": 0.0,
            "drift_detected": False,
            "feature_drift": {},
            "prediction_drift_psi": 0.0,
            "recommendation": "none",
        }
        
        feature_windows = self._feature_windows.get(model_name, {})
        reference = self._reference_distributions.get(model_name, {})
        
        if not feature_windows or not reference:
            result["recommendation"] = "insufficient_data"
            return result
        
        # Check feature drift
        drift_scores = []
        for feat_name, ref_values in reference.items():
            current_values = feature_windows.get(feat_name)
            if current_values and len(current_values) >= 10:
                psi = _psi(ref_values, np.array(current_values))
                result["feature_drift"][feat_name] = round(psi, 4)
                drift_scores.append(psi)
        
        # Aggregate drift score
        if drift_scores:
            result["overall_drift_score"] = round(float(np.mean(drift_scores)), 4)
        
        # Determine recommendation
        score = result["overall_drift_score"]
        if score > 0.25:
            result["drift_detected"] = True
            result["recommendation"] = "retrain_immediately"
            logger.warning(f"DRIFT DETECTED for {model_name}: PSI={score:.4f}")
        elif score > 0.1:
            result["drift_detected"] = True
            result["recommendation"] = "investigate"
            logger.info(f"Moderate drift for {model_name}: PSI={score:.4f}")
        else:
            result["recommendation"] = "none"
        
        self._drift_scores[model_name] = score
        return result
    
    def get_drift_score(self, model_name: str) -> float:
        """Get the last computed drift score for a model."""
        return self._drift_scores.get(model_name, 0.0)
    
    def get_all_drift_scores(self) -> Dict[str, float]:
        """Get drift scores for all monitored models."""
        return dict(self._drift_scores)


# ─────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────
_detector: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    """Get or create the global drift detector."""
    global _detector
    if _detector is None:
        _detector = DriftDetector()
    return _detector
