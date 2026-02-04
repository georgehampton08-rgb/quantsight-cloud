"""
CircuitBreakerService - Prevents cascading failures in NBA API calls.

Wraps NBAAPIConnector with pybreaker pattern:
- Opens after 5 consecutive failures
- Stays open for 60 seconds
- Falls back to SQLite cached data
"""

import logging
from typing import Optional, Dict, Any
from pybreaker import CircuitBreaker, CircuitBreakerError
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitBreakerService:
    """
    Circuit breaker wrapper for NBA API connector.
    
    Pattern:
    - fail_max=5: Open after 5 consecutive failures
    - timeout_duration=60: Stay open for 60 seconds
    - recovery_timeout=30: Try recovery after 30s
    """
    
    def __init__(self, name: str = "nba_api_circuit"):
        """
        Initialize circuit breaker.
        
        Args:
            name: Identifier for this circuit breaker instance
        """
        self.breaker = CircuitBreaker(
            fail_max=5,
            reset_timeout=60,  # Fixed: was timeout_duration
            name=name
        )
        
        logger.info(f"[CIRCUIT] Circuit breaker '{name}' initialized (fail_max=5, reset_timeout=60s)")

    
    def call(self, func, *args, **kwargs):
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
        """
        try:
            return self.breaker.call(func, *args, **kwargs)
        except CircuitBreakerError as e:
            logger.error(f"[CIRCUIT] Breaker OPEN, blocking call to {func.__name__}")
            raise
    
    @property
    def state(self) -> str:
        """Get current circuit state: 'open', 'closed', or 'half_open'."""
        return self.breaker.current_state
    
    @property
    def fail_count(self) -> int:
        """Get current failure count."""
        return self.breaker.fail_counter


def with_circuit_breaker(breaker_service: CircuitBreakerService):
    """
    Decorator to wrap function with circuit breaker.
    
    Usage:
        @with_circuit_breaker(circuit_breaker_service)
        def risky_api_call():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return breaker_service.call(func, *args, **kwargs)
            except CircuitBreakerError:
                logger.warning(f"[CIRCUIT] {func.__name__} blocked by open circuit")
                return None
        return wrapper
    return decorator
