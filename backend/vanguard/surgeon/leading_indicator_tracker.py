"""
Phase 9 — Leading Indicator Tracker
======================================
Monitors pre-failure signals for predictive circuit breaking.

Tracks:
    - Latency p95/p99 trends (rising = warning)
    - Error rate velocity (rate of change)
    - Request count anomalies
    - Consecutive error bursts

These signals feed the Predictive Circuit Breaker to trigger
PREDICTIVE_OPEN before actual failure thresholds are breached.
"""

import time
import logging
from collections import deque
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("vanguard.surgeon.leading_indicators")


@dataclass
class EndpointIndicators:
    """Tracked indicators for a single endpoint."""
    
    # Latency tracking (sliding window of recent latencies in ms)
    latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    
    # Error tracking (timestamps of recent errors)
    error_timestamps: deque = field(default_factory=lambda: deque(maxlen=200))
    
    # Request tracking (timestamps of recent requests)
    request_timestamps: deque = field(default_factory=lambda: deque(maxlen=200))
    
    # Historical error rates for velocity calculation
    error_rate_samples: deque = field(default_factory=lambda: deque(maxlen=10))
    
    last_updated: float = 0.0


class LeadingIndicatorTracker:
    """Tracks pre-failure signals across endpoints.
    
    Used by PredictiveCircuitBreaker to determine when to enter
    PREDICTIVE_OPEN state before actual failures breach CB thresholds.
    """
    
    MAX_ENDPOINTS = 200
    WINDOW_SECONDS = 60  # Sliding window for rate calculations
    
    def __init__(self):
        self._endpoints: Dict[str, EndpointIndicators] = {}
    
    def _get_or_create(self, endpoint: str) -> EndpointIndicators:
        """Get or create indicators for an endpoint (with LRU eviction)."""
        if endpoint not in self._endpoints:
            if len(self._endpoints) >= self.MAX_ENDPOINTS:
                # Evict oldest
                oldest = min(self._endpoints, key=lambda k: self._endpoints[k].last_updated)
                del self._endpoints[oldest]
            self._endpoints[endpoint] = EndpointIndicators()
        return self._endpoints[endpoint]
    
    def record_request(
        self,
        endpoint: str,
        latency_ms: float,
        is_error: bool,
    ):
        """Record a request outcome for leading indicator analysis.
        
        Args:
            endpoint: Request path
            latency_ms: Response time in milliseconds
            is_error: Whether the response was an error (4xx/5xx)
        """
        now = time.time()
        indicators = self._get_or_create(endpoint)
        indicators.last_updated = now
        
        # Track latency
        indicators.latencies.append(latency_ms)
        
        # Track request timestamp
        indicators.request_timestamps.append(now)
        
        # Track error timestamp
        if is_error:
            indicators.error_timestamps.append(now)
    
    def get_latency_p95(self, endpoint: str) -> float:
        """Get p95 latency for an endpoint (ms)."""
        indicators = self._endpoints.get(endpoint)
        if not indicators or not indicators.latencies:
            return 0.0
        
        sorted_latencies = sorted(indicators.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    def get_latency_p99(self, endpoint: str) -> float:
        """Get p99 latency for an endpoint (ms)."""
        indicators = self._endpoints.get(endpoint)
        if not indicators or not indicators.latencies:
            return 0.0
        
        sorted_latencies = sorted(indicators.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    def get_error_rate(self, endpoint: str, window_s: float = None) -> float:
        """Get error rate for an endpoint in the sliding window."""
        window = window_s or self.WINDOW_SECONDS
        now = time.time()
        cutoff = now - window
        
        indicators = self._endpoints.get(endpoint)
        if not indicators:
            return 0.0
        
        recent_requests = sum(1 for ts in indicators.request_timestamps if ts > cutoff)
        recent_errors = sum(1 for ts in indicators.error_timestamps if ts > cutoff)
        
        if recent_requests == 0:
            return 0.0
        
        return recent_errors / recent_requests
    
    def get_error_rate_velocity(self, endpoint: str) -> float:
        """Calculate rate of change of error rate.
        
        Positive = error rate increasing (bad)
        Negative = error rate decreasing (good)
        Zero = stable
        
        Returns:
            Rate of change per second (approximate)
        """
        indicators = self._endpoints.get(endpoint)
        if not indicators:
            return 0.0
        
        # Calculate current error rate and compare to historical
        current_rate = self.get_error_rate(endpoint, window_s=30)
        historical_rate = self.get_error_rate(endpoint, window_s=60)
        
        # Store current rate for trend analysis
        indicators.error_rate_samples.append((time.time(), current_rate))
        
        # Velocity = (current - historical) / time_delta
        if len(indicators.error_rate_samples) < 2:
            return 0.0
        
        return current_rate - historical_rate
    
    def get_request_count(self, endpoint: str, window_s: float = None) -> int:
        """Get request count in the sliding window."""
        window = window_s or self.WINDOW_SECONDS
        now = time.time()
        cutoff = now - window
        
        indicators = self._endpoints.get(endpoint)
        if not indicators:
            return 0
        
        return sum(1 for ts in indicators.request_timestamps if ts > cutoff)
    
    def get_consecutive_errors(self, endpoint: str) -> int:
        """Count consecutive recent errors (burst detection)."""
        indicators = self._endpoints.get(endpoint)
        if not indicators:
            return 0
        
        # Look at the last N request outcomes
        now = time.time()
        cutoff = now - 30  # Last 30 seconds
        
        recent_errors = sorted(
            [ts for ts in indicators.error_timestamps if ts > cutoff],
            reverse=True,
        )
        
        if not recent_errors:
            return 0
        
        # Count how many errors happened in rapid succession (< 2s apart)
        consecutive = 1
        for i in range(1, len(recent_errors)):
            if recent_errors[i - 1] - recent_errors[i] < 2.0:
                consecutive += 1
            else:
                break
        
        return consecutive
    
    def get_indicator_snapshot(self, endpoint: str) -> Dict[str, Any]:
        """Get a full snapshot of leading indicators for an endpoint.
        
        Returns:
            Dictionary of indicator values for ML features / logging
        """
        return {
            "endpoint": endpoint,
            "latency_p95_ms": round(self.get_latency_p95(endpoint), 2),
            "latency_p99_ms": round(self.get_latency_p99(endpoint), 2),
            "error_rate_30s": round(self.get_error_rate(endpoint, 30), 4),
            "error_rate_60s": round(self.get_error_rate(endpoint, 60), 4),
            "error_rate_velocity": round(self.get_error_rate_velocity(endpoint), 6),
            "request_count_30s": self.get_request_count(endpoint, 30),
            "request_count_60s": self.get_request_count(endpoint, 60),
            "consecutive_errors": self.get_consecutive_errors(endpoint),
            "timestamp": time.time(),
        }
    
    def should_predict_failure(self, endpoint: str) -> Tuple[bool, float, str]:
        """Determine if leading indicators suggest imminent failure.
        
        Returns:
            (should_open, confidence, reason)
        """
        snapshot = self.get_indicator_snapshot(endpoint)
        
        reasons = []
        confidence = 0.0
        
        # Signal 1: Error rate velocity is strongly positive
        velocity = snapshot["error_rate_velocity"]
        if velocity > 0.1:  # Error rate increasing by >10% per 30s
            confidence += 0.3
            reasons.append(f"error_rate_velocity={velocity:.4f}")
        
        # Signal 2: p95 latency spiking above threshold
        p95 = snapshot["latency_p95_ms"]
        if p95 > 2000:  # > 2 seconds
            confidence += 0.2
            reasons.append(f"latency_p95={p95:.0f}ms")
        
        # Signal 3: Consecutive error burst
        consecutive = snapshot["consecutive_errors"]
        if consecutive >= 5:
            confidence += 0.25
            reasons.append(f"consecutive_errors={consecutive}")
        
        # Signal 4: Error rate already elevated but below CB threshold
        error_rate = snapshot["error_rate_30s"]
        if 0.3 <= error_rate < 0.5:  # 30-50% (CB triggers at 50%)
            confidence += 0.25
            reasons.append(f"error_rate_30s={error_rate:.2%}")
        
        should_open = confidence >= 0.5
        reason = "; ".join(reasons) if reasons else "no_signals"
        
        return should_open, round(confidence, 3), reason


# ─────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────
_tracker: Optional[LeadingIndicatorTracker] = None


def get_leading_indicator_tracker() -> LeadingIndicatorTracker:
    """Get or create the global leading indicator tracker."""
    global _tracker
    if _tracker is None:
        _tracker = LeadingIndicatorTracker()
    return _tracker
