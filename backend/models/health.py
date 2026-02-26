"""Health & system status response models."""

from typing import Optional
from pydantic import BaseModel, ConfigDict


class SystemSnapshotResponse(BaseModel):
    """Response model for GET /health/deps — Oracle snapshot."""
    model_config = ConfigDict(extra="ignore")

    firestore_ok: bool = True
    gemini_ok: bool = True
    vanguard_ok: bool = True
    redis_ok: bool = False
    updated_at: str = ""


class ReadyzResponse(BaseModel):
    """Response model for GET /readyz."""
    model_config = ConfigDict(extra="ignore")

    status: str = "ok"


class HealthComponentDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "unknown"
    details: Optional[str] = None
    latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Response model for GET /health."""
    model_config = ConfigDict(extra="allow")

    status: str = "healthy"
    nba_api: Optional[str] = "unknown"
    gemini: Optional[str] = "unknown"
    database: Optional[str] = "unknown"
    timestamp: Optional[str] = None
