"""
Anomaly Detection
=================
Z-score based anomaly detection comparing current metrics to baseline.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from ..bootstrap.redis_client import get_redis
from ..core.types import Baseline, BaselineMetric
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AnomalyDetector:
    """
    Z-score anomaly detector.
    Compares current metrics to statistical baseline.
    """
    
    def __init__(self):
        self.baseline: Optional[Baseline] = None
    
    async def load_baseline(self) -> bool:
        """
        Load baseline from Redis.
        Returns True if loaded successfully.
        """
        try:
            redis_client = await get_redis()
            baseline_data = await redis_client.get("vanguard:baseline:current")
            
            if baseline_data:
                self.baseline = json.loads(baseline_data)
                logger.info("baseline_loaded", expires_at=self.baseline.get("expires_at"))
                return True
            else:
                logger.warning("baseline_not_found", message="Run calibration first")
                return False
        
        except Exception as e:
            logger.error("baseline_load_error", error=str(e))
            return False
    
    def detect_anomaly(self, metric_name: str, current_value: float) -> Dict[str, Any]:
        """
        Detect if current value is anomalous compared to baseline.
        
        Args:
            metric_name: Name of metric (cpu_pct, memory_mb, etc.)
            current_value: Current measured value
        
        Returns:
            {
                "anomaly": bool,
                "severity": "GREEN" | "YELLOW" | "RED",
                "z_score": float,
                "evidence": str
            }
        """
        if not self.baseline:
            return {
                "anomaly": False,
                "severity": "GREEN",
                "z_score": 0.0,
                "evidence": "No baseline available"
            }
        
        # Get baseline metric
        baseline_metric: BaselineMetric = self.baseline.get(metric_name)
        if not baseline_metric:
            return {
                "anomaly": False,
                "severity": "GREEN",
                "z_score": 0.0,
                "evidence": f"No baseline for {metric_name}"
            }
        
        # Calculate Z-score
        mean = baseline_metric["mean"]
        std = baseline_metric.get("std", 1.0)  # Avoid division by zero
        
        if std == 0:
            z_score = 0.0
        else:
            z_score = (current_value - mean) / std
        
        # Classify anomaly
        if z_score > 3:
            return {
                "anomaly": True,
                "severity": "RED",
                "z_score": z_score,
                "evidence": f"{metric_name} is {z_score:.1f}σ above baseline"
            }
        elif z_score > 2:
            return {
                "anomaly": True,
                "severity": "YELLOW",
                "z_score": z_score,
                "evidence": f"{metric_name} is {z_score:.1f}σ above baseline"
            }
        else:
            return {
                "anomaly": False,
                "severity": "GREEN",
                "z_score": z_score,
                "evidence": f"{metric_name} is {z_score:.1f}σ from baseline (normal)"
            }


# Global detector instance
_detector: AnomalyDetector | None = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get or create the global anomaly detector."""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector
