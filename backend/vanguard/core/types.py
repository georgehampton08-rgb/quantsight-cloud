"""
Vanguard Type Definitions
==========================
TypedDicts and data models for incidents, traces, and baselines.
"""

from datetime import datetime
from enum import Enum
from typing import TypedDict, Optional, Dict, Any, List


class Severity(str, Enum):
    """Incident severity levels."""
    GREEN = "GREEN"    # Healthy
    YELLOW = "YELLOW"  # Warning
    RED = "RED"        # Critical


class IncidentStatus(str, Enum):
    """Incident resolution status."""
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class Incident(TypedDict):
    """Incident data structure."""
    fingerprint: str
    timestamp: str  # ISO format
    severity: Severity
    status: IncidentStatus
    error_type: str
    error_message: str
    endpoint: str
    request_id: str
    traceback: Optional[str]
    context_vector: Dict[str, Any]  # Feature flags, business context
    remediation_log: List[str]
    resolved_at: Optional[str]  # ISO format


class Trace(TypedDict):
    """Request trace data structure."""
    request_id: str
    timestamp: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    error: Optional[str]
    sampled: bool  # Full trace vs metadata only


class BaselineMetric(TypedDict):
    """Statistical baseline for a single metric."""
    mean: float
    std: float  # Standard deviation
    p95: float  # 95th percentile


class Baseline(TypedDict):
    """System baseline metrics."""
    cpu_pct: BaselineMetric
    memory_mb: BaselineMetric
    db_connections_active: BaselineMetric
    event_loop_latency_ms: BaselineMetric
    created_at: str  # ISO format
    expires_at: str  # ISO format


class VanguardMode(str, Enum):
    """Vanguard operating modes (duplicate for convenience)."""
    SILENT_OBSERVER = "SILENT_OBSERVER"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    FULL_SOVEREIGN = "FULL_SOVEREIGN"
