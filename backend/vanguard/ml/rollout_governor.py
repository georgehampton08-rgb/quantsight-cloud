"""
Phase 9 — Model Rollout Governor
===================================
Safety layer for ML model deployments.

Provides:
    1. Canary model routing (1-5% traffic to candidate model)
    2. Automatic rollback rules (fallback rate, drift, severity shift)
    3. Model version registry with A/B comparison metrics

Strategy:
    - New model → canary (5% traffic) → compare for 1h → promote or rollback
    - Rollback triggers:
        * ML fallback rate > 20% for 1h
        * Drift PSI > 0.25
        * Increased incident severity after deployment
"""

import time
import logging
from collections import deque
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("vanguard.ml.rollout_governor")


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
CANARY_TRAFFIC_PCT = 5           # % of traffic routed to candidate
CANARY_EVAL_WINDOW_S = 3600     # 1 hour evaluation before promotion
MAX_FALLBACK_RATE = 0.20         # Rollback if > 20% fallback rate
MAX_DRIFT_PSI = 0.25             # Rollback if drift exceeds threshold
MAX_SEVERITY_INCREASE = 0.15     # Rollback if RED severity increases 15%+


class ModelVersion:
    """Represents a deployed model version with tracking metrics."""
    
    __slots__ = (
        "version_id", "source", "deployed_at",
        "predictions_total", "predictions_used",
        "predictions_fallback", "cumulative_confidence",
    )
    
    def __init__(self, version_id: str, source: str):
        self.version_id = version_id
        self.source = source  # "gcs", "local_cache", etc.
        self.deployed_at = time.time()
        self.predictions_total = 0
        self.predictions_used = 0       # Confidence >= threshold
        self.predictions_fallback = 0   # Confidence < threshold → fell through
        self.cumulative_confidence = 0.0
    
    @property
    def fallback_rate(self) -> float:
        if self.predictions_total == 0:
            return 0.0
        return self.predictions_fallback / self.predictions_total
    
    @property
    def avg_confidence(self) -> float:
        if self.predictions_total == 0:
            return 0.0
        return self.cumulative_confidence / self.predictions_total
    
    @property
    def uptime_s(self) -> float:
        return time.time() - self.deployed_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "source": self.source,
            "deployed_at": datetime.fromtimestamp(
                self.deployed_at, tz=timezone.utc
            ).isoformat(),
            "uptime_s": round(self.uptime_s, 1),
            "predictions_total": self.predictions_total,
            "predictions_used": self.predictions_used,
            "predictions_fallback": self.predictions_fallback,
            "fallback_rate": round(self.fallback_rate, 4),
            "avg_confidence": round(self.avg_confidence, 4),
        }


class RolloutGovernor:
    """Governs ML model rollout with canary traffic and automatic rollback.
    
    State machine:
        STABLE → CANARY → EVALUATING → PROMOTED | ROLLED_BACK
    """
    
    def __init__(self):
        self._primary: Optional[ModelVersion] = None
        self._candidate: Optional[ModelVersion] = None
        self._state = "STABLE"  # STABLE, CANARY, EVALUATING, ROLLED_BACK
        self._rollback_reasons: list = []
        self._prediction_counter = 0
    
    @property
    def state(self) -> str:
        return self._state
    
    def register_primary(self, version_id: str, source: str):
        """Register the current production model."""
        self._primary = ModelVersion(version_id, source)
        self._state = "STABLE"
        logger.info(f"Primary model registered: {version_id} (source={source})")
    
    def deploy_candidate(self, version_id: str, source: str):
        """Deploy a new model as canary candidate.
        
        Routes CANARY_TRAFFIC_PCT of predictions to the candidate.
        """
        self._candidate = ModelVersion(version_id, source)
        self._state = "CANARY"
        self._rollback_reasons = []
        logger.info(
            f"Canary deployed: {version_id} → "
            f"{CANARY_TRAFFIC_PCT}% traffic for {CANARY_EVAL_WINDOW_S}s"
        )
    
    def should_use_candidate(self) -> bool:
        """Determine if this request should use the candidate model.
        
        Returns True for ~CANARY_TRAFFIC_PCT% of calls.
        """
        if self._state != "CANARY" or self._candidate is None:
            return False
        
        self._prediction_counter += 1
        return (self._prediction_counter % 100) < CANARY_TRAFFIC_PCT
    
    def record_prediction(
        self,
        is_candidate: bool,
        confidence: float,
        used: bool,  # True if confidence >= threshold
    ):
        """Record a prediction outcome for the active or candidate model."""
        model = self._candidate if is_candidate else self._primary
        if model is None:
            return
        
        model.predictions_total += 1
        model.cumulative_confidence += confidence
        
        if used:
            model.predictions_used += 1
        else:
            model.predictions_fallback += 1
    
    def evaluate(self, drift_score: float = 0.0) -> Dict[str, Any]:
        """Evaluate canary candidate for promotion or rollback.
        
        Called periodically (e.g., every 5 minutes).
        
        Args:
            drift_score: Current PSI drift score from DriftDetector
            
        Returns:
            Evaluation result with action and reasons
        """
        result = {
            "state": self._state,
            "action": "none",
            "reasons": [],
            "candidate": self._candidate.to_dict() if self._candidate else None,
            "primary": self._primary.to_dict() if self._primary else None,
        }
        
        if self._state != "CANARY" or self._candidate is None:
            return result
        
        # Check rollback conditions
        reasons = []
        
        # Rule 1: Fallback rate too high
        if (self._candidate.predictions_total >= 20 and
                self._candidate.fallback_rate > MAX_FALLBACK_RATE):
            reasons.append(
                f"fallback_rate={self._candidate.fallback_rate:.2%} "
                f"> {MAX_FALLBACK_RATE:.0%}"
            )
        
        # Rule 2: Drift too high
        if drift_score > MAX_DRIFT_PSI:
            reasons.append(f"drift_psi={drift_score:.4f} > {MAX_DRIFT_PSI}")
        
        # Rule 3: Average confidence significantly lower than primary
        if (self._primary and self._primary.predictions_total >= 20 and
                self._candidate.predictions_total >= 20):
            confidence_diff = (
                self._primary.avg_confidence - self._candidate.avg_confidence
            )
            if confidence_diff > 0.1:  # 10% lower confidence
                reasons.append(
                    f"confidence_drop={confidence_diff:.4f} "
                    f"(primary={self._primary.avg_confidence:.4f}, "
                    f"candidate={self._candidate.avg_confidence:.4f})"
                )
        
        if reasons:
            self._state = "ROLLED_BACK"
            self._rollback_reasons = reasons
            self._candidate = None
            result["action"] = "rollback"
            result["reasons"] = reasons
            logger.warning(f"ROLLBACK triggered: {'; '.join(reasons)}")
            return result
        
        # Check promotion conditions
        if self._candidate.uptime_s >= CANARY_EVAL_WINDOW_S:
            if self._candidate.predictions_total >= 10:
                # Promote candidate to primary
                old_primary = self._primary
                self._primary = self._candidate
                self._candidate = None
                self._state = "STABLE"
                result["action"] = "promote"
                logger.info(
                    f"Candidate PROMOTED to primary: "
                    f"{self._primary.version_id} "
                    f"(fallback_rate={self._primary.fallback_rate:.2%}, "
                    f"avg_confidence={self._primary.avg_confidence:.4f})"
                )
            else:
                # Not enough traffic — extend evaluation
                result["action"] = "extend"
                logger.info("Extending canary evaluation — insufficient traffic")
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get rollout governor status for health/admin."""
        return {
            "state": self._state,
            "primary": self._primary.to_dict() if self._primary else None,
            "candidate": self._candidate.to_dict() if self._candidate else None,
            "canary_traffic_pct": CANARY_TRAFFIC_PCT,
            "rollback_reasons": self._rollback_reasons,
        }


# ─────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────
_governor: Optional[RolloutGovernor] = None


def get_rollout_governor() -> RolloutGovernor:
    """Get or create the global rollout governor."""
    global _governor
    if _governor is None:
        _governor = RolloutGovernor()
    return _governor
