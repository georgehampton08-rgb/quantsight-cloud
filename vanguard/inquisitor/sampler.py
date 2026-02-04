"""
Adaptive Sampling Logic
========================
Dynamically adjusts trace sampling rate based on system load.
"""

import psutil
from ..core.config import get_vanguard_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AdaptiveSampler:
    """
    Adaptive sampling controller.
    
    Rules:
      - Normal load (CPU <80%): 5% sampling (default)
      - High load (CPU >=80%): 1% sampling (reduced overhead)
      - Active incident on endpoint: 100% sampling for 5 minutes
    """
    
    def __init__(self):
        self.config = get_vanguard_config()
        self.default_rate = self.config.sampling_rate
        self.current_rate = self.default_rate
        self.forced_endpoints: dict[str, float] = {}  # {endpoint: sampling_rate}
    
    def should_sample(self, endpoint: str) -> bool:
        """Determine if this request should be fully traced."""
        import random
        
        # Check if endpoint has forced sampling
        if endpoint in self.forced_endpoints:
            rate = self.forced_endpoints[endpoint]
            return random.random() < rate
        
        # Adaptive sampling based on CPU
        return random.random() < self.current_rate
    
    def update_sampling_rate(self) -> None:
        """Adjust sampling rate based on current CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            if cpu_percent >= 80:
                # High CPU - reduce sampling
                self.current_rate = 0.01  # 1%
                logger.debug("adaptive_sampling_reduced", cpu=cpu_percent, rate=0.01)
            else:
                # Normal CPU - use default
                self.current_rate = self.default_rate
        
        except Exception as e:
            logger.warning("adaptive_sampling_error", error=str(e))
            # Fallback to default
            self.current_rate = self.default_rate
    
    def force_sampling(self, endpoint: str, rate: float = 1.0, duration_sec: int = 300) -> None:
        """
        Force a specific sampling rate for an endpoint (e.g., during incident).
        
        Args:
            endpoint: API endpoint path
            rate: Sampling rate (0.0-1.0)
            duration_sec: How long to maintain this rate (default 5 min)
        """
        self.forced_endpoints[endpoint] = rate
        logger.info("forced_sampling_enabled", endpoint=endpoint, rate=rate, duration=duration_sec)
        
        # TODO: Schedule removal after duration_sec (requires background task)


# Global sampler instance
_sampler: AdaptiveSampler | None = None


def get_sampler() -> AdaptiveSampler:
    """Get or create the global adaptive sampler."""
    global _sampler
    if _sampler is None:
        _sampler = AdaptiveSampler()
    return _sampler
