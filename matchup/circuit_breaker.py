"""
Circuit Breaker Pattern for Matchup Engine
Prevents cascading failures and 503 errors
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Too many failures, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """
    Circuit breaker for protecting backend services from overload
    
    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Too many failures, reject all requests immediately
    - HALF_OPEN: Testing if service recovered, allow limited requests
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout_seconds)
        self.success_threshold = success_threshold
        
        self.failures = 0
        self.successes = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
        logger.info(f"Circuit breaker initialized: {failure_threshold} failures, {timeout_seconds}s timeout")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker
        
        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is OPEN or function fails
        """
        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and datetime.utcnow() - self.last_failure_time > self.timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.successes = 0
            else:
                raise Exception("Circuit breaker is OPEN - service temporarily unavailable")
        
        try:
            # Execute function
            result = await func(*args, **kwargs)
            
            # Record success
            self._record_success()
            
            return result
            
        except Exception as e:
            # Record failure
            self._record_failure()
            raise e
    
    def _record_success(self):
        """Record successful execution"""
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            logger.info(f"Circuit breaker success {self.successes}/{self.success_threshold}")
            
            if self.successes >= self.success_threshold:
                self._reset()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            if self.failures > 0:
                self.failures = 0
    
    def _record_failure(self):
        """Record failed execution"""
        self.failures += 1
        self.last_failure_time = datetime.utcnow()
        
        logger.warning(f"Circuit breaker failure {self.failures}/{self.failure_threshold}")
        
        if self.failures >= self.failure_threshold:
            self._trip()
    
    def _trip(self):
        """Trip the circuit breaker to OPEN state"""
        if self.state != CircuitState.OPEN:
            logger.error("Circuit breaker TRIPPED - entering OPEN state")
            self.state = CircuitState.OPEN
    
    def _reset(self):
        """Reset circuit breaker to CLOSED state"""
        logger.info("Circuit breaker RESET - entering CLOSED state")
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time = None
    
    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        return {
            "state": self.state.value,
            "failures": self.failures,
            "successes": self.successes,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


# Global circuit breakers for different services
_breakers = {}

def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for a service"""
    if service_name not in _breakers:
        _breakers[service_name] = CircuitBreaker()
        logger.info(f"Created circuit breaker for: {service_name}")
    return _breakers[service_name]
