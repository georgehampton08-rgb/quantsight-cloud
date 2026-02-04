"""
Health Gate - Unified health monitoring with Cooldown Mode

Key Features:
1. Aggregates health from WorkerHealthMonitor
2. Tracks circuit breaker states
3. Monitors NBA API rate limiting (429 status)
4. Implements Cooldown Mode - intentional pause after rate limit hit
5. Provides unified health view for Adaptive Router decisions
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    DOWN = "down"
    COOLDOWN = "cooldown"  # Intentionally paused due to rate limiting


class ServiceType(Enum):
    """Types of services monitored."""
    CORE = "core"           # Database, internal systems
    EXTERNAL = "external"   # NBA API, Gemini
    COMPONENT = "component" # Aegis components


@dataclass
class ServiceHealth:
    """Health state for a single service."""
    name: str
    service_type: ServiceType
    status: HealthStatus
    last_check: datetime
    error_count: int = 0
    last_error: Optional[str] = None
    cooldown_until: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    
    def is_available(self) -> bool:
        """Check if service is usable (not down or in cooldown)."""
        if self.status in (HealthStatus.DOWN, HealthStatus.COOLDOWN):
            return False
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False
        return True


@dataclass
class SystemHealth:
    """Aggregated system health state."""
    overall: HealthStatus
    core: Dict[str, ServiceHealth]
    external: Dict[str, ServiceHealth]
    components: Dict[str, ServiceHealth]
    cooldowns: Dict[str, datetime]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "overall": self.overall.value,
            "core": {k: self._service_to_dict(v) for k, v in self.core.items()},
            "external": {k: self._service_to_dict(v) for k, v in self.external.items()},
            "components": {k: self._service_to_dict(v) for k, v in self.components.items()},
            "cooldowns": {k: v.isoformat() for k, v in self.cooldowns.items()},
            "timestamp": self.timestamp.isoformat()
        }
    
    def _service_to_dict(self, svc: ServiceHealth) -> Dict[str, Any]:
        return {
            "name": svc.name,
            "status": svc.status.value,
            "last_check": svc.last_check.isoformat(),
            "error_count": svc.error_count,
            "last_error": svc.last_error,
            "cooldown_until": svc.cooldown_until.isoformat() if svc.cooldown_until else None,
            "response_time_ms": svc.response_time_ms,
            "available": svc.is_available()
        }


class HealthGate:
    """
    Unified health checking with Smart Throttling.
    
    Key Feature: Cooldown Mode
    - Monitors Retry-After headers from NBA API
    - On 429 (Too Many Requests), puts endpoint in 60s cooldown
    - During cooldown, uses fallback intentionally (not "impatiently")
    
    Integration:
    - Uses existing WorkerHealthMonitor for system metrics
    - Tracks Aegis component availability
    - Feeds into AdaptiveRouter for routing decisions
    """
    
    DEFAULT_COOLDOWN_SECONDS = 60
    
    def __init__(self, worker_monitor=None):
        """
        Initialize HealthGate.
        
        Args:
            worker_monitor: Optional WorkerHealthMonitor instance for system metrics
        """
        self.worker_monitor = worker_monitor
        self.cooldowns: Dict[str, datetime] = {}
        self.service_states: Dict[str, ServiceHealth] = {}
        self._error_counts: Dict[str, int] = {}
        self._last_check: Optional[datetime] = None
        
        # Initialize known services
        self._init_services()
        
        logger.info("[NEXUS] HealthGate initialized")
    
    def _init_services(self):
        """Initialize known service health states."""
        now = datetime.now()
        
        # Core services
        self.service_states["database"] = ServiceHealth(
            name="database",
            service_type=ServiceType.CORE,
            status=HealthStatus.HEALTHY,
            last_check=now
        )
        
        # External services
        self.service_states["nba_api"] = ServiceHealth(
            name="nba_api",
            service_type=ServiceType.EXTERNAL,
            status=HealthStatus.HEALTHY,
            last_check=now
        )
        self.service_states["gemini"] = ServiceHealth(
            name="gemini",
            service_type=ServiceType.EXTERNAL,
            status=HealthStatus.HEALTHY,
            last_check=now
        )
        
        # Aegis components
        for component in ["aegis_brain", "sovereign_router", "aegis_orchestrator", 
                          "vertex_engine", "matchup_lab", "confluence_scorer"]:
            self.service_states[component] = ServiceHealth(
                name=component,
                service_type=ServiceType.COMPONENT,
                status=HealthStatus.HEALTHY,
                last_check=now
            )
    
    def check_all(self) -> SystemHealth:
        """
        Perform complete health check of all services.
        
        Returns:
            SystemHealth with aggregated status
        """
        now = datetime.now()
        self._last_check = now
        
        # Clean up expired cooldowns
        self._cleanup_cooldowns()
        
        # Gather service states by type
        core = {}
        external = {}
        components = {}
        
        for name, svc in self.service_states.items():
            # Update cooldown status if in cooldown
            if name in self.cooldowns:
                if datetime.now() < self.cooldowns[name]:
                    svc.status = HealthStatus.COOLDOWN
                    svc.cooldown_until = self.cooldowns[name]
                else:
                    # Cooldown expired, reset to degraded (needs verification)
                    svc.status = HealthStatus.DEGRADED
                    svc.cooldown_until = None
            
            # Sort by type
            if svc.service_type == ServiceType.CORE:
                core[name] = svc
            elif svc.service_type == ServiceType.EXTERNAL:
                external[name] = svc
            else:
                components[name] = svc
        
        # Get system metrics from WorkerHealthMonitor if available
        if self.worker_monitor:
            try:
                metrics = self.worker_monitor.get_current_health()
                # Update core services based on system health
                if metrics.get("cpu_percent", 0) > 90:
                    self.service_states["database"].status = HealthStatus.DEGRADED
            except Exception as e:
                logger.warning(f"[NEXUS] Failed to get worker metrics: {e}")
        
        # Calculate overall health
        overall = self._calculate_overall_health(core, external, components)
        
        return SystemHealth(
            overall=overall,
            core=core,
            external=external,
            components=components,
            cooldowns=dict(self.cooldowns),
            timestamp=now
        )
    
    def _calculate_overall_health(
        self, 
        core: Dict[str, ServiceHealth],
        external: Dict[str, ServiceHealth],
        components: Dict[str, ServiceHealth]
    ) -> HealthStatus:
        """Calculate overall system health from component statuses."""
        
        all_services = list(core.values()) + list(external.values()) + list(components.values())
        
        # Any core service down = CRITICAL
        for svc in core.values():
            if svc.status == HealthStatus.DOWN:
                return HealthStatus.CRITICAL
        
        # Count statuses
        down_count = sum(1 for s in all_services if s.status == HealthStatus.DOWN)
        cooldown_count = sum(1 for s in all_services if s.status == HealthStatus.COOLDOWN)
        degraded_count = sum(1 for s in all_services if s.status == HealthStatus.DEGRADED)
        
        # Decision logic
        if down_count > len(all_services) // 2:
            return HealthStatus.DOWN
        elif down_count > 0 or cooldown_count > 2:
            return HealthStatus.CRITICAL
        elif degraded_count > 0 or cooldown_count > 0:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    def enter_cooldown(self, service: str, duration_seconds: int = None) -> None:
        """
        Put a service in cooldown after rate limit hit.
        
        Args:
            service: Service name (e.g., "nba_api", "/aegis/simulate/{player_id}")
            duration_seconds: Cooldown duration (default: 60s)
        """
        if duration_seconds is None:
            duration_seconds = self.DEFAULT_COOLDOWN_SECONDS
            
        expires = datetime.now() + timedelta(seconds=duration_seconds)
        self.cooldowns[service] = expires
        
        # Update service state if it exists
        if service in self.service_states:
            self.service_states[service].status = HealthStatus.COOLDOWN
            self.service_states[service].cooldown_until = expires
        
        logger.warning(f"[NEXUS] COOLDOWN: {service} for {duration_seconds}s until {expires.isoformat()}")
    
    def exit_cooldown(self, service: str) -> None:
        """Manually exit a service from cooldown."""
        if service in self.cooldowns:
            del self.cooldowns[service]
        if service in self.service_states:
            self.service_states[service].status = HealthStatus.DEGRADED
            self.service_states[service].cooldown_until = None
        logger.info(f"[NEXUS] Exited cooldown: {service}")
    
    def is_in_cooldown(self, service: str) -> bool:
        """Check if a service is currently in cooldown."""
        if service not in self.cooldowns:
            return False
        if datetime.now() > self.cooldowns[service]:
            # Expired, clean up
            del self.cooldowns[service]
            return False
        return True
    
    def get_cooldown_remaining(self, service: str) -> int:
        """Get remaining cooldown seconds for a service."""
        if not self.is_in_cooldown(service):
            return 0
        remaining = (self.cooldowns[service] - datetime.now()).total_seconds()
        return max(0, int(remaining))
    
    def get_active_cooldowns(self) -> Dict[str, Dict[str, Any]]:
        """Get all active cooldowns with details."""
        self._cleanup_cooldowns()
        return {
            service: {
                "expires": expires.isoformat(),
                "remaining_seconds": self.get_cooldown_remaining(service)
            }
            for service, expires in self.cooldowns.items()
        }
    
    def _cleanup_cooldowns(self) -> None:
        """Remove expired cooldowns."""
        now = datetime.now()
        expired = [s for s, exp in self.cooldowns.items() if now > exp]
        for service in expired:
            del self.cooldowns[service]
            if service in self.service_states:
                self.service_states[service].status = HealthStatus.DEGRADED
                self.service_states[service].cooldown_until = None
            logger.info(f"[NEXUS] Cooldown expired: {service}")
    
    def record_error(self, service: str, error: str) -> None:
        """Record an error for a service."""
        self._error_counts[service] = self._error_counts.get(service, 0) + 1
        
        if service in self.service_states:
            self.service_states[service].error_count += 1
            self.service_states[service].last_error = error
            self.service_states[service].last_check = datetime.now()
            
            # Degrade status after repeated errors
            if self.service_states[service].error_count >= 3:
                self.service_states[service].status = HealthStatus.DEGRADED
            if self.service_states[service].error_count >= 5:
                self.service_states[service].status = HealthStatus.DOWN
        
        logger.warning(f"[NEXUS] Error recorded for {service}: {error}")
    
    def record_success(self, service: str, response_time_ms: float = None) -> None:
        """Record a successful request for a service."""
        if service in self.service_states:
            svc = self.service_states[service]
            svc.last_check = datetime.now()
            svc.response_time_ms = response_time_ms
            svc.last_error = None
            
            # Recover from errors on success
            if svc.status in (HealthStatus.DEGRADED, HealthStatus.DOWN):
                svc.error_count = max(0, svc.error_count - 1)
                if svc.error_count == 0:
                    svc.status = HealthStatus.HEALTHY
    
    def record_rate_limit(self, service: str, retry_after: int = None) -> None:
        """
        Handle 429 rate limit response.
        
        Args:
            service: Service that was rate limited
            retry_after: Seconds from Retry-After header (default: 60)
        """
        duration = retry_after if retry_after else self.DEFAULT_COOLDOWN_SECONDS
        self.enter_cooldown(service, duration)
        self.record_error(service, f"Rate limited (429) - cooldown for {duration}s")
    
    def is_service_available(self, service: str) -> bool:
        """Check if a service is available for requests."""
        if self.is_in_cooldown(service):
            return False
        if service in self.service_states:
            return self.service_states[service].is_available()
        return True
    
    def get_service_status(self, service: str) -> Optional[ServiceHealth]:
        """Get health state for a specific service."""
        return self.service_states.get(service)
    
    def update_component_status(self, component: str, available: bool) -> None:
        """Update availability status for an Aegis component."""
        if component in self.service_states:
            self.service_states[component].status = (
                HealthStatus.HEALTHY if available else HealthStatus.DOWN
            )
            self.service_states[component].last_check = datetime.now()
