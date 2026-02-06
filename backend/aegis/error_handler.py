"""
Error Handler - Unified error taxonomy for Nexus Hub

Features:
1. Standardized error codes (NEXUS_XXX format)
2. Structured error responses with recovery actions
3. Error classification from raw exceptions
4. Cooldown integration for rate limits
5. Fallback availability hints for frontend
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """
    Nexus Hub Error Codes - Standardized across all endpoints.
    
    Format: NEXUS_{HTTP_STATUS}_{ERROR_TYPE}
    """
    
    # 400 - Bad Request
    MISSING_PARAM = "NEXUS_400_MISSING_PARAM"
    INVALID_PARAM = "NEXUS_400_INVALID_PARAM"
    INVALID_PLAYER_ID = "NEXUS_400_INVALID_PLAYER_ID"
    INVALID_TEAM_ID = "NEXUS_400_INVALID_TEAM_ID"
    INVALID_SEASON = "NEXUS_400_INVALID_SEASON"
    INVALID_GAME_ID = "NEXUS_400_INVALID_GAME_ID"
    
    # 401 - Unauthorized
    AUTH_REQUIRED = "NEXUS_401_AUTH_REQUIRED"
    INVALID_API_KEY = "NEXUS_401_INVALID_API_KEY"
    
    # 403 - Forbidden
    ADMIN_REQUIRED = "NEXUS_403_ADMIN_REQUIRED"
    
    # 404 - Not Found
    PLAYER_NOT_FOUND = "NEXUS_404_PLAYER_NOT_FOUND"
    TEAM_NOT_FOUND = "NEXUS_404_TEAM_NOT_FOUND"
    GAME_NOT_FOUND = "NEXUS_404_GAME_NOT_FOUND"
    STATS_NOT_FOUND = "NEXUS_404_STATS_NOT_FOUND"
    SEASON_NOT_FOUND = "NEXUS_404_SEASON_NOT_FOUND"
    ENDPOINT_NOT_FOUND = "NEXUS_404_ENDPOINT_NOT_FOUND"
    CACHE_NOT_FOUND = "NEXUS_404_CACHE_NOT_FOUND"
    
    # 429 - Rate Limited
    NBA_API_RATE_LIMITED = "NEXUS_429_NBA_API_RATE_LIMITED"
    GEMINI_RATE_LIMITED = "NEXUS_429_GEMINI_RATE_LIMITED"
    INTERNAL_RATE_LIMITED = "NEXUS_429_INTERNAL_RATE_LIMITED"
    
    # 500 - Internal Error
    DATABASE_ERROR = "NEXUS_500_DATABASE_ERROR"
    CALCULATION_ERROR = "NEXUS_500_CALCULATION_ERROR"
    SERIALIZATION_ERROR = "NEXUS_500_SERIALIZATION_ERROR"
    CONFIGURATION_ERROR = "NEXUS_500_CONFIGURATION_ERROR"
    UNKNOWN_ERROR = "NEXUS_500_UNKNOWN_ERROR"
    
    # 502 - Bad Gateway
    EXTERNAL_API_ERROR = "NEXUS_502_EXTERNAL_API_ERROR"
    UPSTREAM_ERROR = "NEXUS_502_UPSTREAM_ERROR"
    
    # 503 - Service Unavailable
    AEGIS_ROUTER_DOWN = "NEXUS_503_AEGIS_ROUTER_DOWN"
    VERTEX_ENGINE_DOWN = "NEXUS_503_VERTEX_ENGINE_DOWN"
    MATCHUP_LAB_DOWN = "NEXUS_503_MATCHUP_LAB_DOWN"
    ENRICHMENT_DOWN = "NEXUS_503_ENRICHMENT_DOWN"
    NBA_API_DOWN = "NEXUS_503_NBA_API_DOWN"
    GEMINI_DOWN = "NEXUS_503_GEMINI_DOWN"
    DATABASE_DOWN = "NEXUS_503_DATABASE_DOWN"
    SERVICE_UNAVAILABLE = "NEXUS_503_SERVICE_UNAVAILABLE"
    
    # 504 - Gateway Timeout
    NBA_API_TIMEOUT = "NEXUS_504_NBA_API_TIMEOUT"
    GEMINI_TIMEOUT = "NEXUS_504_GEMINI_TIMEOUT"
    SIMULATION_TIMEOUT = "NEXUS_504_SIMULATION_TIMEOUT"
    DATABASE_TIMEOUT = "NEXUS_504_DATABASE_TIMEOUT"


# Mapping from error code to HTTP status
ERROR_HTTP_STATUS: Dict[ErrorCode, int] = {
    # 400s
    ErrorCode.MISSING_PARAM: 400,
    ErrorCode.INVALID_PARAM: 400,
    ErrorCode.INVALID_PLAYER_ID: 400,
    ErrorCode.INVALID_TEAM_ID: 400,
    ErrorCode.INVALID_SEASON: 400,
    ErrorCode.INVALID_GAME_ID: 400,
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.INVALID_API_KEY: 401,
    ErrorCode.ADMIN_REQUIRED: 403,
    
    # 404s
    ErrorCode.PLAYER_NOT_FOUND: 404,
    ErrorCode.TEAM_NOT_FOUND: 404,
    ErrorCode.GAME_NOT_FOUND: 404,
    ErrorCode.STATS_NOT_FOUND: 404,
    ErrorCode.SEASON_NOT_FOUND: 404,
    ErrorCode.ENDPOINT_NOT_FOUND: 404,
    ErrorCode.CACHE_NOT_FOUND: 404,
    
    # 429s
    ErrorCode.NBA_API_RATE_LIMITED: 429,
    ErrorCode.GEMINI_RATE_LIMITED: 429,
    ErrorCode.INTERNAL_RATE_LIMITED: 429,
    
    # 500s
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.CALCULATION_ERROR: 500,
    ErrorCode.SERIALIZATION_ERROR: 500,
    ErrorCode.CONFIGURATION_ERROR: 500,
    ErrorCode.UNKNOWN_ERROR: 500,
    
    # 502s
    ErrorCode.EXTERNAL_API_ERROR: 502,
    ErrorCode.UPSTREAM_ERROR: 502,
    
    # 503s
    ErrorCode.AEGIS_ROUTER_DOWN: 503,
    ErrorCode.VERTEX_ENGINE_DOWN: 503,
    ErrorCode.MATCHUP_LAB_DOWN: 503,
    ErrorCode.ENRICHMENT_DOWN: 503,
    ErrorCode.NBA_API_DOWN: 503,
    ErrorCode.GEMINI_DOWN: 503,
    ErrorCode.DATABASE_DOWN: 503,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    
    # 504s
    ErrorCode.NBA_API_TIMEOUT: 504,
    ErrorCode.GEMINI_TIMEOUT: 504,
    ErrorCode.SIMULATION_TIMEOUT: 504,
    ErrorCode.DATABASE_TIMEOUT: 504,
}


@dataclass
class NexusError:
    """Structured error response for all Nexus endpoints."""
    code: ErrorCode
    message: str
    endpoint: str
    http_status: int = field(init=False)
    details: Optional[Dict[str, Any]] = None
    recovery_action: Optional[str] = None
    fallback_available: bool = False
    cooldown_seconds: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        self.http_status = ERROR_HTTP_STATUS.get(self.code, 500)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "endpoint": self.endpoint,
                "http_status": self.http_status,
                "details": self.details,
                "recovery_action": self.recovery_action,
                "fallback_available": self.fallback_available,
                "cooldown_seconds": self.cooldown_seconds,
                "timestamp": self.timestamp.isoformat()
            }
        }
    
    def __repr__(self):
        return f"<NexusError {self.code.value}: {self.message}>"


class NexusErrorHandler:
    """
    Centralized error handling for all endpoints.
    
    Features:
    1. Structured error responses (not raw str(e))
    2. Recovery action suggestions
    3. Cooldown integration with HealthGate
    4. Fallback availability hints for frontend
    """
    
    DEFAULT_COOLDOWN_SECONDS = 60
    
    def __init__(self, health_gate=None):
        """
        Initialize error handler.
        
        Args:
            health_gate: Optional HealthGate for cooldown integration
        """
        self.health_gate = health_gate
        self.error_counts: Dict[ErrorCode, int] = {}
        self._error_history: list = []
    
    def handle(
        self, 
        exception: Exception, 
        endpoint: str, 
        context: Dict[str, Any] = None
    ) -> NexusError:
        """
        Convert any exception to structured NexusError.
        
        Args:
            exception: The caught exception
            endpoint: The endpoint path that failed
            context: Optional context (player_id, team_id, etc.)
            
        Returns:
            NexusError with structured information
        """
        error_code, message, recovery = self._classify_error(exception, context)
        
        # Track error frequency
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
        
        # Check if fallback is available
        fallback = self._check_fallback_available(endpoint, context)
        
        # Trigger cooldown if rate limited
        cooldown = 0
        if error_code in (
            ErrorCode.NBA_API_RATE_LIMITED, 
            ErrorCode.GEMINI_RATE_LIMITED,
            ErrorCode.INTERNAL_RATE_LIMITED
        ):
            cooldown = self.DEFAULT_COOLDOWN_SECONDS
            if self.health_gate:
                self.health_gate.enter_cooldown(endpoint, cooldown)
        
        error = NexusError(
            code=error_code,
            message=message,
            endpoint=endpoint,
            details=context,
            recovery_action=recovery,
            fallback_available=fallback,
            cooldown_seconds=cooldown
        )
        
        # Log and track
        self._error_history.append(error)
        if len(self._error_history) > 100:
            self._error_history = self._error_history[-100:]
        
        logger.error(f"[NEXUS-ERROR] {error}")
        
        return error
    
    def _classify_error(
        self, 
        exc: Exception, 
        ctx: Dict[str, Any] = None
    ) -> Tuple[ErrorCode, str, str]:
        """
        Classify exception into NexusError taxonomy.
        
        Returns:
            Tuple of (ErrorCode, message, recovery_action)
        """
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__
        ctx = ctx or {}
        
        # ----- Rate Limiting -----
        if "429" in exc_str or "rate limit" in exc_str or "too many" in exc_str:
            if "gemini" in exc_str:
                return (
                    ErrorCode.GEMINI_RATE_LIMITED,
                    "Gemini API rate limited - using cached data",
                    "Wait 60s or use cached fallback"
                )
            return (
                ErrorCode.NBA_API_RATE_LIMITED,
                "NBA API rate limited - entering cooldown",
                "Wait 60s or use cached fallback"
            )
        
        # ----- Timeouts -----
        if "timeout" in exc_str or "timed out" in exc_str or exc_type == "TimeoutError":
            if "gemini" in exc_str:
                return (
                    ErrorCode.GEMINI_TIMEOUT,
                    "Gemini API timeout",
                    "Retry with longer timeout or use cache"
                )
            if "database" in exc_str or "sqlite" in exc_str:
                return (
                    ErrorCode.DATABASE_TIMEOUT,
                    "Database query timeout",
                    "Try a simpler query or check database health"
                )
            return (
                ErrorCode.NBA_API_TIMEOUT,
                "External API timeout - check network",
                "Retry with longer timeout or use cache"
            )
        
        # ----- Not Found -----
        if "not found" in exc_str or "no data" in exc_str or "does not exist" in exc_str:
            if "player" in exc_str or ctx.get("player_id"):
                return (
                    ErrorCode.PLAYER_NOT_FOUND,
                    f"Player {ctx.get('player_id', 'unknown')} not found",
                    "Verify player ID is correct"
                )
            if "team" in exc_str or ctx.get("team_id"):
                return (
                    ErrorCode.TEAM_NOT_FOUND,
                    f"Team {ctx.get('team_id', 'unknown')} not found",
                    "Verify team abbreviation or ID"
                )
            if "game" in exc_str or ctx.get("game_id"):
                return (
                    ErrorCode.GAME_NOT_FOUND,
                    f"Game {ctx.get('game_id', 'unknown')} not found",
                    "Verify game ID is correct"
                )
            if "stats" in exc_str or "season" in exc_str:
                return (
                    ErrorCode.STATS_NOT_FOUND,
                    "Stats not found for the requested parameters",
                    "Check season parameter or verify data exists"
                )
            return (
                ErrorCode.STATS_NOT_FOUND,
                "Requested data not found",
                "Check parameters and try again"
            )
        
        # ----- Service Unavailable -----
        if "not available" in exc_str or "not initialized" in exc_str or "unavailable" in exc_str:
            if "aegis" in exc_str or "router" in exc_str:
                return (
                    ErrorCode.AEGIS_ROUTER_DOWN,
                    "Aegis router not available",
                    "Check backend initialization"
                )
            if "vertex" in exc_str:
                return (
                    ErrorCode.VERTEX_ENGINE_DOWN,
                    "Vertex engine not available",
                    "Check Vertex initialization"
                )
            if "matchup" in exc_str:
                return (
                    ErrorCode.MATCHUP_LAB_DOWN,
                    "Matchup Lab not available",
                    "Check Matchup Lab initialization"
                )
            if "enrichment" in exc_str:
                return (
                    ErrorCode.ENRICHMENT_DOWN,
                    "Enrichment service not available",
                    "Service may be restarting"
                )
            return (
                ErrorCode.SERVICE_UNAVAILABLE,
                "Service temporarily unavailable",
                "Service may be restarting"
            )
        
        # ----- Database Errors -----
        if "database" in exc_str or "sqlite" in exc_str or "connection" in exc_str:
            if "no such column" in exc_str:
                return (
                    ErrorCode.DATABASE_ERROR,
                    "Database schema error - missing column",
                    "Check database migrations"
                )
            if "locked" in exc_str:
                return (
                    ErrorCode.DATABASE_ERROR,
                    "Database locked - concurrent access issue",
                    "Retry after a moment"
                )
            return (
                ErrorCode.DATABASE_ERROR,
                "Database connection error",
                "Check database file exists and is accessible"
            )
        
        # ----- Validation Errors -----
        if "invalid" in exc_str or "validation" in exc_str:
            if "player" in exc_str:
                return (
                    ErrorCode.INVALID_PLAYER_ID,
                    "Invalid player ID format",
                    "Use numeric NBA player ID"
                )
            if "team" in exc_str:
                return (
                    ErrorCode.INVALID_TEAM_ID,
                    "Invalid team ID or abbreviation",
                    "Use valid team abbreviation (e.g., LAL, BOS)"
                )
            return (
                ErrorCode.INVALID_PARAM,
                "Invalid parameter provided",
                "Check API documentation for valid parameters"
            )
        
        # ----- Missing Parameters -----
        if "missing" in exc_str or "required" in exc_str:
            return (
                ErrorCode.MISSING_PARAM,
                "Required parameter missing",
                "Provide all required parameters"
            )
        
        # ----- Authorization -----
        if "unauthorized" in exc_str or "auth" in exc_str:
            if "admin" in exc_str:
                return (
                    ErrorCode.ADMIN_REQUIRED,
                    "Admin access required",
                    "Provide valid admin API key"
                )
            return (
                ErrorCode.AUTH_REQUIRED,
                "Authentication required",
                "Provide valid API key"
            )
        
        # ----- Calculation Errors -----
        if "division" in exc_str or "zero" in exc_str or exc_type == "ZeroDivisionError":
            return (
                ErrorCode.CALCULATION_ERROR,
                "Calculation error - division by zero",
                "Check input data validity"
            )
        
        if exc_type in ("TypeError", "AttributeError"):
            return (
                ErrorCode.CALCULATION_ERROR,
                f"Calculation error - {exc_type}",
                "Check input data format"
            )
        
        # ----- JSON Errors -----
        if "json" in exc_str or "serialize" in exc_str or exc_type == "JSONDecodeError":
            return (
                ErrorCode.SERIALIZATION_ERROR,
                "Data serialization error",
                "Check data format"
            )
        
        # ----- Default -----
        return (
            ErrorCode.UNKNOWN_ERROR,
            f"An unexpected error occurred: {exc_type}",
            "Check server logs for details"
        )
    
    def _check_fallback_available(
        self, 
        endpoint: str, 
        ctx: Dict[str, Any] = None
    ) -> bool:
        """Check if cached fallback exists for this request."""
        # Endpoints that typically have cache fallbacks
        fallback_prefixes = [
            "/aegis/",
            "/confluence/",
            "/cache/",
            "/simulation/",
            "/matchup/",
            "/vertex/"
        ]
        return any(endpoint.startswith(prefix) for prefix in fallback_prefixes)
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for admin dashboard."""
        total = sum(self.error_counts.values())
        
        by_category = {}
        for code, count in self.error_counts.items():
            status = ERROR_HTTP_STATUS.get(code, 500)
            category = f"{status // 100}xx"
            by_category[category] = by_category.get(category, 0) + count
        
        return {
            "total_errors": total,
            "by_code": {code.value: count for code, count in self.error_counts.items()},
            "by_category": by_category,
            "recent_errors": [
                {
                    "code": e.code.value,
                    "message": e.message,
                    "endpoint": e.endpoint,
                    "timestamp": e.timestamp.isoformat()
                }
                for e in self._error_history[-10:]
            ]
        }
    
    def clear_stats(self) -> None:
        """Clear error statistics."""
        self.error_counts.clear()
        self._error_history.clear()


# Convenience function for simple error creation
def create_error(
    code: ErrorCode,
    message: str,
    endpoint: str,
    details: Dict[str, Any] = None,
    recovery_action: str = None
) -> NexusError:
    """Create a NexusError directly without classification."""
    return NexusError(
        code=code,
        message=message,
        endpoint=endpoint,
        details=details,
        recovery_action=recovery_action
    )
