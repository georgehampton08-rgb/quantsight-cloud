"""
Nexus Hub - Lead API Supervisor

The central orchestrator for intelligent endpoint management.

Responsibilities:
1. Endpoint Discovery - Auto-registers all endpoints
2. Health Aggregation - Unified view with Cooldown Mode
3. Advisory Routing - Recommends optimal paths (not intercepting)
4. Priority Queuing - High-stakes sims get the "fast lane"
5. Shadow-Race - Live data continues after cache displayed
6. Error Handling - Unified error taxonomy

This is the main entry point for Nexus Hub functionality.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

from .endpoint_registry import (
    EndpointRegistry, 
    EndpointConfig, 
    EndpointCategory,
    EndpointPriority
)
from .health_gate import HealthGate, SystemHealth, HealthStatus
from .adaptive_router import AdaptiveRouter, RouteDecision, RouteStrategy
from .shadow_race import ShadowRace, ShadowRaceResult, SSEBroadcaster
from .priority_queue import PriorityQueue, Priority
from .error_handler import NexusErrorHandler, NexusError, ErrorCode

logger = logging.getLogger(__name__)


@dataclass
class NexusOverview:
    """Complete system overview for admin dashboard."""
    status: str
    uptime_seconds: float
    endpoints: Dict[str, Any]
    health: Dict[str, Any]
    routing: Dict[str, Any]
    queue: Dict[str, Any]
    errors: Dict[str, Any]
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "endpoints": self.endpoints,
            "health": self.health,
            "routing": self.routing,
            "queue": self.queue,
            "errors": self.errors,
            "timestamp": self.timestamp
        }


class NexusHub:
    """
    Lead API Supervisor - The central endpoint manager.
    
    This class coordinates all Nexus Hub components:
    - EndpointRegistry: Catalogs all endpoints with metadata
    - HealthGate: Unified health with Cooldown Mode
    - AdaptiveRouter: Advisory routing with Dynamic TTL
    - ShadowRace: Patient data handling
    - PriorityQueue: Fast lane for high-stakes requests
    - ErrorHandler: Unified error taxonomy
    
    Usage:
        nexus_hub = NexusHub()
        await nexus_hub.start()
        
        # Get routing recommendation
        decision = nexus_hub.recommend_route("/aegis/simulate/1628389")
        
        # Get system overview
        overview = nexus_hub.get_system_overview()
    """
    
    VERSION = "1.0.0"
    
    def __init__(self, worker_monitor=None):
        """
        Initialize Nexus Hub.
        
        Args:
            worker_monitor: Optional WorkerHealthMonitor for system metrics
        """
        self._start_time = datetime.now()
        self._initialized = False
        
        # Initialize components
        self.registry = EndpointRegistry()
        self.health_gate = HealthGate(worker_monitor=worker_monitor)
        self.sse_broadcaster = SSEBroadcaster()
        self.shadow_race = ShadowRace(sse_broadcaster=self.sse_broadcaster)
        self.router = AdaptiveRouter(
            registry=self.registry,
            health_gate=self.health_gate,
            shadow_race=self.shadow_race
        )
        self.priority_queue = PriorityQueue()
        self.error_handler = NexusErrorHandler(health_gate=self.health_gate)
        
        logger.info(f"[NEXUS] NexusHub v{self.VERSION} initialized")
    
    async def start(self) -> None:
        """Start the Nexus Hub background services."""
        await self.priority_queue.start()
        self._initialized = True
        logger.info("[NEXUS] NexusHub started")
    
    async def stop(self) -> None:
        """Stop the Nexus Hub background services."""
        await self.priority_queue.stop()
        self._initialized = False
        logger.info("[NEXUS] NexusHub stopped")
    
    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        return (datetime.now() - self._start_time).total_seconds()
    
    def get_overall_status(self) -> str:
        """Get overall system status."""
        health = self.health_gate.check_all()
        
        if health.overall == HealthStatus.HEALTHY:
            return "operational"
        elif health.overall == HealthStatus.DEGRADED:
            return "degraded"
        elif health.overall == HealthStatus.CRITICAL:
            return "critical"
        else:
            return "down"
    
    def recommend_route(self, path: str, context: Dict[str, Any] = None) -> RouteDecision:
        """
        Get routing recommendation for a path.
        
        This is the main advisory interface for the frontend.
        
        Args:
            path: Request path (e.g., "/aegis/simulate/1628389")
            context: Optional context (priority, force_fresh, etc.)
            
        Returns:
            RouteDecision with recommended strategy
        """
        return self.router.recommend(path, context)
    
    async def execute_with_priority(
        self,
        func,
        priority: str = "medium",
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a task with priority queuing.
        
        Args:
            func: Async callable to execute
            priority: "critical", "high", "medium", "low", or "background"
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Task result
        """
        priority_map = {
            "critical": Priority.CRITICAL,
            "high": Priority.HIGH,
            "medium": Priority.MEDIUM,
            "low": Priority.LOW,
            "background": Priority.BACKGROUND
        }
        
        p = priority_map.get(priority, Priority.MEDIUM)
        
        if p in (Priority.CRITICAL, Priority.HIGH):
            # Fast lane - execute immediately
            return await self.priority_queue.execute_immediate(func, p, *args, **kwargs)
        else:
            # Queue for background processing
            return await self.priority_queue.submit_and_wait(func, p, timeout=30.0, *args, **kwargs)
    
    def handle_error(
        self, 
        exception: Exception, 
        endpoint: str, 
        context: Dict[str, Any] = None
    ) -> NexusError:
        """
        Handle an exception with unified error taxonomy.
        
        Args:
            exception: The caught exception
            endpoint: The endpoint that failed
            context: Optional context (player_id, etc.)
            
        Returns:
            NexusError with structured information
        """
        return self.error_handler.handle(exception, endpoint, context)
    
    def get_system_overview(self) -> NexusOverview:
        """
        Get complete system overview for admin dashboard.
        
        Returns:
            NexusOverview with all system information
        """
        health = self.health_gate.check_all()
        
        return NexusOverview(
            status=self.get_overall_status(),
            uptime_seconds=self.uptime_seconds,
            endpoints=self.registry.summary(),
            health=health.to_dict(),
            routing=self.router.get_stats(),
            queue=self.priority_queue.get_stats(),
            errors=self.error_handler.get_error_stats(),
            timestamp=datetime.now().isoformat()
        )
    
    def get_health(self) -> SystemHealth:
        """Get unified health status."""
        return self.health_gate.check_all()
    
    def get_cooldowns(self) -> Dict[str, Dict[str, Any]]:
        """Get active cooldown states."""
        return self.health_gate.get_active_cooldowns()
    
    def get_route_matrix(self) -> List[Dict[str, Any]]:
        """Get routing matrix for all endpoints."""
        return self.router.get_route_matrix()
    
    def enter_cooldown(self, service: str, duration_seconds: int = 60) -> None:
        """Manually put a service in cooldown."""
        self.health_gate.enter_cooldown(service, duration_seconds)
    
    def exit_cooldown(self, service: str) -> None:
        """Manually exit a service from cooldown."""
        self.health_gate.exit_cooldown(service)
    
    def register_endpoint(self, config: EndpointConfig) -> None:
        """Register a new endpoint configuration."""
        self.registry.register(config)
    
    def update_component_status(self, component: str, available: bool) -> None:
        """Update availability status for an Aegis component."""
        self.health_gate.update_component_status(component, available)
    
    def record_request_success(self, service: str, response_time_ms: float = None) -> None:
        """Record a successful request for health tracking."""
        self.health_gate.record_success(service, response_time_ms)
    
    def record_request_error(self, service: str, error: str) -> None:
        """Record an error for health tracking."""
        self.health_gate.record_error(service, error)
    
    def record_rate_limit(self, service: str, retry_after: int = None) -> None:
        """Handle 429 rate limit response."""
        self.health_gate.record_rate_limit(service, retry_after)
    
    def get_sse_listener(self, listener_id: str):
        """Get SSE listener for late arrivals."""
        return self.sse_broadcaster.register_listener(listener_id)
    
    def remove_sse_listener(self, listener_id: str) -> None:
        """Remove SSE listener."""
        self.sse_broadcaster.unregister_listener(listener_id)
    
    def get_late_arrival(self, request_id: str):
        """Get late arrival data if available."""
        return self.sse_broadcaster.get_late_arrival(request_id)


# Singleton instance for easy access
_nexus_hub_instance: Optional[NexusHub] = None


def get_nexus_hub(worker_monitor=None) -> NexusHub:
    """Get or create the singleton NexusHub instance."""
    global _nexus_hub_instance
    if _nexus_hub_instance is None:
        _nexus_hub_instance = NexusHub(worker_monitor=worker_monitor)
    return _nexus_hub_instance


def reset_nexus_hub() -> None:
    """Reset the singleton instance (for testing)."""
    global _nexus_hub_instance
    _nexus_hub_instance = None
