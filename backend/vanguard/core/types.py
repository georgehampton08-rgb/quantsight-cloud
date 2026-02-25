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
    GREEN = "GREEN"    # Healthy / suppressed
    YELLOW = "YELLOW"  # Warning (minor 4xx)
    AMBER = "AMBER"    # Phase 2: 4xx on known API prefixes
    RED = "RED"        # Critical (5xx, unhandled exceptions)


class IncidentStatus(str, Enum):
    """Incident resolution status."""
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class Incident(TypedDict, total=False):
    """
    Incident data structure.

    Phase 3 (schema_version v1) adds structured blocks.
    All v1 fields are Optional (total=False) for backward compatibility.
    """
    # --- v0 core fields (always present) ---
    fingerprint: str
    timestamp: str  # ISO format
    severity: str   # Severity enum value
    status: str     # IncidentStatus enum value
    error_type: str
    error_message: str
    endpoint: str
    request_id: str
    traceback: Optional[str]
    context_vector: Dict[str, Any]  # Feature flags, business context
    remediation_log: List[str]      # v0 legacy list
    resolved_at: Optional[str]      # ISO format

    # --- v1 structured fields (added in Phase 3) ---
    schema_version: str             # "v1"
    labels: Dict[str, Any]          # service, revision, region, component, team, player_id
    duration_ms: Optional[float]
    remediation: Dict[str, Any]     # plan, references, confidence, auto_generated, generated_at
    ai_analysis: Dict[str, Any]     # summary, root_cause, suggested_fix, confidence, model
    resolution: Dict[str, Any]      # resolved_by, resolution_type, notes, resolved_at, verified



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
