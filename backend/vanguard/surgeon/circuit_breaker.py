"""
Circuit Breaker — 1ST-GEN STUB (DEPRECATED)
============================================
⚠️  PHASE 4 PRE-CONDITION: DO NOT EXTEND OR IMPORT FOR NEW WORK.

This file is the Phase 3 circuit breaker stub.  It contains a critical
semantic inversion: OPEN = healthy and CLOSED = quarantined, which is the
exact OPPOSITE of industry convention and the Phase 4 spec:

    Phase 4 spec / industry standard:
        CLOSED   = healthy, traffic passes through
        OPEN     = quarantined, traffic blocked
        HALF_OPEN = probe state, one request allowed

    This file (1st-gen / WRONG):
        OPEN   = healthy   ← inverted
        CLOSED = blocked   ← inverted

Step 4.3 replaces this file wholesale with a correct CLOSED→OPEN→HALF_OPEN
state machine backed by the FailureTracker sliding window.

This file is PRESERVED (not deleted) per Governance Rule 3:
  No deletions without 14-day zero-caller confirmation.
Callers of get_circuit_breaker() will be migrated in Step 4.3.

Flagged: 2026-02-26 by Phase 4 Pre-conditions commit.
"""

import time
from enum import Enum
from typing import Dict
from datetime import datetime, timedelta

from ..utils.logger import get_logger
from ..core.config import get_vanguard_config, VanguardMode

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    OPEN = "OPEN"          # Healthy, allowing traffic
    HALF_OPEN = "HALF_OPEN"  # Testing, allow 1 request
    CLOSED = "CLOSED"       # Quarantined, blocking traffic


class CircuitBreaker:
    """
    Circuit breaker for endpoint quarantine.
    
    Rules:
      - 2 failures within 5 min → CLOSED (quarantine)
      - After 5 min → HALF_OPEN (allow 1 test request)
      - 3 consecutive successes → OPEN (un-quarantine)
    """
    
    def __init__(self):
        self.config = get_vanguard_config()
        self.circuits: Dict[str, Dict] = {}  # {endpoint: {state, failures, last_failure_time}}
    
    def record_failure(self, endpoint: str) -> None:
        """Record a failure for an endpoint."""
        if endpoint not in self.circuits:
            self.circuits[endpoint] = {
                "state": CircuitState.OPEN,
                "failures": 0,
                "successes": 0,
                "last_failure_time": None,
                "quarantine_time": None
            }
        
        circuit = self.circuits[endpoint]
        circuit["failures"] += 1
        circuit["last_failure_time"] = datetime.utcnow()
        
        # Check if should quarantine (2 failures within 5 min)
        if circuit["failures"] >= 2:
            if self.config.mode in [VanguardMode.CIRCUIT_BREAKER, VanguardMode.FULL_SOVEREIGN]:
                self._close_circuit(endpoint)
        
        logger.warning("circuit_failure_recorded", endpoint=endpoint, total_failures=circuit["failures"])
    
    def record_success(self, endpoint: str) -> None:
        """Record a success for an endpoint."""
        if endpoint not in self.circuits:
            return
        
        circuit = self.circuits[endpoint]
        circuit["successes"] += 1
        
        # In HALF_OPEN: 3 successes → OPEN
        if circuit["state"] == CircuitState.HALF_OPEN and circuit["successes"] >= 3:
            self._open_circuit(endpoint)
        
        logger.debug("circuit_success_recorded", endpoint=endpoint, successes=circuit["successes"])
    
    def is_allowed(self, endpoint: str) -> bool:
        """Check if request to endpoint is allowed."""
        if endpoint not in self.circuits:
            return True  # No circuit, allow
        
        circuit = self.circuits[endpoint]
        
        if circuit["state"] == CircuitState.OPEN:
            return True  # Healthy, allow
        
        elif circuit["state"] == CircuitState.CLOSED:
            # Check if 5 min elapsed → HALF_OPEN
            if circuit["quarantine_time"]:
                elapsed = (datetime.utcnow() - circuit["quarantine_time"]).total_seconds()
                if elapsed > 300:  # 5 minutes
                    self._half_open_circuit(endpoint)
                    return True  # Allow 1 test request
            
            return False  # Quarantined, block
        
        elif circuit["state"] == CircuitState.HALF_OPEN:
            return True  # Testing, allow
    
    def _close_circuit(self, endpoint: str) -> None:
        """Quarantine an endpoint."""
        circuit = self.circuits[endpoint]
        circuit["state"] = CircuitState.CLOSED
        circuit["quarantine_time"] = datetime.utcnow()
        circuit["successes"] = 0
        
        logger.error("circuit_closed", endpoint=endpoint, message="Endpoint QUARANTINED")
    
    def _half_open_circuit(self, endpoint: str) -> None:
        """Enter testing mode."""
        circuit = self.circuits[endpoint]
        circuit["state"] = CircuitState.HALF_OPEN
        circuit["successes"] = 0
        
        logger.info("circuit_half_open", endpoint=endpoint, message="Testing endpoint")
    
    def _open_circuit(self, endpoint: str) -> None:
        """Un-quarantine an endpoint."""
        circuit = self.circuits[endpoint]
        circuit["state"] = CircuitState.OPEN
        circuit["failures"] = 0
        circuit["successes"] = 0
        
        logger.info("circuit_opened", endpoint=endpoint, message="Endpoint UN-QUARANTINED")


# Global circuit breaker
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create the global circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
