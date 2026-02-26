"""Vanguard API response models — typed schemas for admin, health, and incident endpoints."""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


# ── Vanguard Health ────────────────────────────────────────────────────────

class VanguardHealthResponse(BaseModel):
    """Response model for GET /vanguard/health."""
    model_config = ConfigDict(extra="allow")

    status: str = "unknown"
    version: str = ""
    mode: str = ""
    enabled: bool = True
    llm_enabled: bool = False
    sampling_rate: Optional[float] = None
    storage_size_mb: Optional[float] = None
    active_incidents: Optional[int] = None
    uptime_seconds: Optional[float] = None


# ── Incidents ──────────────────────────────────────────────────────────────

class IncidentSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    fingerprint: str = ""
    error_type: Optional[str] = None
    endpoint: Optional[str] = None
    status: str = "ACTIVE"
    occurrence_count: Optional[int] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    severity: Optional[str] = None
    labels: Optional[Dict[str, Any]] = None


class IncidentListResponse(BaseModel):
    """Response model for GET /vanguard/admin/incidents."""
    model_config = ConfigDict(extra="allow")

    total: int = 0
    active: Optional[int] = None
    resolved: Optional[int] = None
    incidents: List[IncidentSummary] = []
    timestamp: Optional[str] = None


# ── Stats ──────────────────────────────────────────────────────────────────

class HealthBreakdown(BaseModel):
    model_config = ConfigDict(extra="allow")

    incident_score: float = 100.0
    subsystem_score: float = 100.0
    endpoint_score: float = 100.0


class VanguardStatsResponse(BaseModel):
    """Response model for GET /vanguard/admin/stats."""
    model_config = ConfigDict(extra="allow")

    active_incidents: int = 0
    resolved_incidents: int = 0
    health_score: float = 100.0
    health_breakdown: Optional[HealthBreakdown] = None
    subsystem_health: Optional[Dict[str, Any]] = None
    top_incident_endpoints: Optional[List[Any]] = None
    vanguard_mode: Optional[str] = None
    timestamp: Optional[str] = None
