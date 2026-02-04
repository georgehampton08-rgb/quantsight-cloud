"""
Vanguard Configuration Management
==================================
Pydantic-based settings for environment variable loading.
"""

import os
from enum import Enum
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class VanguardMode(str, Enum):
    """Operating modes for Vanguard."""
    SILENT_OBSERVER = "SILENT_OBSERVER"  # Log only, no actions
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"  # Quarantine only
    FULL_SOVEREIGN = "FULL_SOVEREIGN"    # Full autonomous remediation


class VanguardConfig(BaseSettings):
    """Vanguard configuration from environment variables."""
    
    # Core Settings
    enabled: bool = Field(default=True, validation_alias="VANGUARD_ENABLED")
    mode: VanguardMode = Field(default=VanguardMode.SILENT_OBSERVER, validation_alias="VANGUARD_MODE")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379", validation_alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, validation_alias="REDIS_MAX_CONNECTIONS")
    
    # Storage Configuration
    storage_path: str = Field(default="/tmp/vanguard/archivist", validation_alias="VANGUARD_STORAGE_PATH")
    storage_max_mb: int = Field(default=500, validation_alias="VANGUARD_STORAGE_MAX_MB")
    retention_days: int = Field(default=7, validation_alias="VANGUARD_RETENTION_DAYS")
    storage_mode: str = Field(
        default="FIRESTORE" if os.getenv("K_SERVICE") else "FILE", 
        validation_alias="VANGUARD_STORAGE_MODE"
    )
    firebase_project_id: Optional[str] = Field(default=None, validation_alias="FIREBASE_PROJECT_ID")
    
    # LLM Profiler Configuration
    llm_enabled: bool = Field(default=False, validation_alias="VANGUARD_LLM_ENABLED")
    llm_model: str = Field(default="gemini-pro", validation_alias="VANGUARD_LLM_MODEL")
    llm_timeout_sec: int = Field(default=30, validation_alias="VANGUARD_LLM_TIMEOUT_SEC")
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    
    # Resource Budgeting
    max_cpu_percent: float = Field(default=10.0, validation_alias="VANGUARD_MAX_CPU_PERCENT")
    max_memory_percent: float = Field(default=10.0, validation_alias="VANGUARD_MAX_MEMORY_PERCENT")
    
    # Baseline Calibration
    calibration_duration_sec: int = Field(default=60, validation_alias="VANGUARD_CALIBRATION_DURATION_SEC")
    baseline_ttl_hours: int = Field(default=24, validation_alias="VANGUARD_BASELINE_TTL_HOURS")
    
    # Chaos Vaccine
    vaccine_enabled: bool = Field(default=False, validation_alias="VANGUARD_VACCINE_ENABLED")
    vaccine_schedule: str = Field(default="0 3 * * 0", validation_alias="VANGUARD_VACCINE_SCHEDULE")  # Sunday 3 AM
    
    # Inquisitor Settings
    sampling_rate: float = Field(default=0.05, validation_alias="VANGUARD_SAMPLING_RATE")  # 5% default
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global config instance
_config: Optional[VanguardConfig] = None


def get_vanguard_config() -> VanguardConfig:
    """Get or create the global Vanguard configuration."""
    global _config
    if _config is None:
        _config = VanguardConfig()
    return _config
