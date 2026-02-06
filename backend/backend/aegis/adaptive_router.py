"""
Adaptive Router - Intelligent routing with Dynamic TTL

Features:
1. Advisory routing - recommends best path without intercepting
2. Dynamic TTL calculation based on endpoint complexity
3. Shadow-Race integration for patient data handling
4. Health-aware routing decisions
5. Priority-based request handling
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

from .endpoint_registry import EndpointRegistry, EndpointConfig, EndpointCategory, EndpointPriority
from .health_gate import HealthGate, HealthStatus
from .shadow_race import ShadowRace, ShadowRaceResult

logger = logging.getLogger(__name__)


class RouteStrategy(Enum):
    """Routing strategies."""
    DIRECT = "direct"       # Call endpoint directly, no orchestration
    MANAGED = "managed"     # Route through manager/orchestrator
    FALLBACK = "fallback"   # Use cached fallback
    COOLDOWN = "cooldown"   # Service in cooldown, use fallback intentionally
    DEGRADED = "degraded"   # Degraded mode - limited functionality


@dataclass
class RouteDecision:
    """Result of routing decision."""
    strategy: RouteStrategy
    target: str
    timeout_ms: int = 1000
    use_shadow_race: bool = False
    patience_threshold_ms: int = 800
    fallback: Optional[str] = None
    reason: str = ""
    priority: EndpointPriority = EndpointPriority.MEDIUM
    endpoint_config: Optional[EndpointConfig] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "strategy": self.strategy.value,
            "target": self.target,
            "timeout_ms": self.timeout_ms,
            "use_shadow_race": self.use_shadow_race,
            "patience_threshold_ms": self.patience_threshold_ms,
            "fallback": self.fallback,
            "reason": self.reason,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat()
        }


class AdaptiveRouter:
    """
    Patient routing with Dynamic TTL.
    
    Key Features:
    1. Adaptive Timeouts - Calculates patience based on complexity
    2. Shadow-Race - Displays cache while live continues in background
    3. Priority Awareness - Fast lane for high-stakes requests
    4. Health-Aware - Routes around unhealthy services
    
    This is an ADVISORY router - it recommends the best path
    but doesn't intercept requests (per approved design decision).
    """
    
    # Complexity thresholds
    LOW_COMPLEXITY_THRESHOLD = 3
    HIGH_COMPLEXITY_THRESHOLD = 6
    
    # System load thresholds
    HIGH_LOAD_CPU_THRESHOLD = 80
    DEGRADED_LOAD_CPU_THRESHOLD = 60
    
    def __init__(
        self, 
        registry: EndpointRegistry = None,
        health_gate: HealthGate = None,
        shadow_race: ShadowRace = None
    ):
        """
        Initialize AdaptiveRouter.
        
        Args:
            registry: Endpoint registry for configuration lookup
            health_gate: Health gate for service status
            shadow_race: Shadow race for patient data handling
        """
        self.registry = registry or EndpointRegistry()
        self.health_gate = health_gate or HealthGate()
        self.shadow_race = shadow_race or ShadowRace()
        
        self._stats = {
            "total_routes": 0,
            "direct_routes": 0,
            "managed_routes": 0,
            "fallback_routes": 0,
            "cooldown_routes": 0
        }
        
        logger.info("[NEXUS] AdaptiveRouter initialized")
    
    def recommend(self, path: str, context: Dict[str, Any] = None) -> RouteDecision:
        """
        Get routing recommendation for a path.
        
        This is the main advisory interface - returns recommendation
        without actually routing the request.
        
        Args:
            path: Request path (e.g., "/aegis/simulate/1628389")
            context: Optional context (user priority, force_fresh, etc.)
            
        Returns:
            RouteDecision with recommended strategy
        """
        context = context or {}
        self._stats["total_routes"] += 1
        
        # Match endpoint configuration
        endpoint = self.registry.match(path)
        
        if not endpoint:
            # Unknown endpoint - direct call with default timeout
            return RouteDecision(
                strategy=RouteStrategy.DIRECT,
                target=path,
                timeout_ms=1000,
                use_shadow_race=False,
                reason="Unknown endpoint - using defaults"
            )
        
        # Calculate dynamic TTL
        timeout_ms = self._calculate_dynamic_ttl(endpoint, context)
        
        # Check cooldown status
        if self.health_gate.is_in_cooldown(path):
            self._stats["cooldown_routes"] += 1
            return RouteDecision(
                strategy=RouteStrategy.COOLDOWN,
                target=endpoint.fallback or path,
                timeout_ms=timeout_ms,
                use_shadow_race=False,
                fallback=endpoint.fallback,
                reason="Service in cooldown - using cache intentionally",
                priority=endpoint.priority,
                endpoint_config=endpoint
            )
        
        # Check service health
        health_decision = self._check_health_routing(endpoint)
        if health_decision:
            return health_decision
        
        # Route based on complexity and system load
        return self._decide_route(endpoint, timeout_ms, context)
    
    def _calculate_dynamic_ttl(
        self, 
        endpoint: EndpointConfig, 
        context: Dict[str, Any] = None
    ) -> int:
        """
        Calculate timeout based on endpoint complexity.
        
        | Request Type    | Baseline | Buffer  | Total   |
        |-----------------|----------|---------|---------|
        | Simple Search   | 200ms    | +50ms   | 250ms   |
        | Matchup Analysis| 500ms    | +300ms  | 800ms   |
        | Crucible Sim    | 800ms    | +500ms  | 1300ms  |
        | H2H Refresh     | 1200ms   | +2000ms | 3200ms  |
        """
        context = context or {}
        
        base_timeout = endpoint.base_timeout_ms
        buffer = endpoint.adaptive_buffer_ms
        
        # Adjust for priority
        if context.get("priority") == "high":
            # High priority gets less patience (faster response expected)
            buffer = buffer // 2
        elif context.get("priority") == "low":
            # Low priority gets more patience
            buffer = buffer * 2
        
        # Adjust for force_fresh requests
        if context.get("force_fresh"):
            # Force fresh requests need more patience
            buffer = buffer + 500
        
        # System load adjustment (if health gate available)
        if self.health_gate and self.health_gate.worker_monitor:
            try:
                metrics = self.health_gate.worker_monitor.get_current_health()
                cpu = metrics.get("cpu_percent", 0)
                if cpu > self.HIGH_LOAD_CPU_THRESHOLD:
                    # High load = more patience needed
                    buffer = int(buffer * 1.5)
            except:
                pass
        
        return base_timeout + buffer
    
    def _check_health_routing(self, endpoint: EndpointConfig) -> Optional[RouteDecision]:
        """Check if we need to route around unhealthy services."""
        
        # Check each dependency
        for dep in endpoint.dependencies:
            if not self.health_gate.is_service_available(dep):
                # Dependency unhealthy - use fallback if available
                if endpoint.fallback:
                    self._stats["fallback_routes"] += 1
                    return RouteDecision(
                        strategy=RouteStrategy.FALLBACK,
                        target=endpoint.fallback,
                        timeout_ms=endpoint.get_dynamic_ttl(),
                        use_shadow_race=False,
                        fallback=endpoint.fallback,
                        reason=f"Dependency '{dep}' unavailable - using fallback",
                        priority=endpoint.priority,
                        endpoint_config=endpoint
                    )
                else:
                    return RouteDecision(
                        strategy=RouteStrategy.DEGRADED,
                        target=endpoint.path,
                        timeout_ms=endpoint.get_dynamic_ttl(),
                        use_shadow_race=False,
                        reason=f"Dependency '{dep}' unavailable - degraded mode",
                        priority=endpoint.priority,
                        endpoint_config=endpoint
                    )
        
        return None
    
    def _decide_route(
        self, 
        endpoint: EndpointConfig, 
        timeout_ms: int,
        context: Dict[str, Any]
    ) -> RouteDecision:
        """Make final routing decision based on complexity and load."""
        
        # Simple endpoint + healthy system = direct call
        if endpoint.complexity <= self.LOW_COMPLEXITY_THRESHOLD:
            self._stats["direct_routes"] += 1
            return RouteDecision(
                strategy=RouteStrategy.DIRECT,
                target=endpoint.path,
                timeout_ms=timeout_ms,
                use_shadow_race=False,
                fallback=endpoint.fallback,
                reason="Low complexity - direct call preferred",
                priority=endpoint.priority,
                endpoint_config=endpoint
            )
        
        # Check if this is a complex endpoint that benefits from Shadow-Race
        use_shadow_race = (
            endpoint.complexity >= self.HIGH_COMPLEXITY_THRESHOLD and
            endpoint.fallback is not None and
            endpoint.category in (EndpointCategory.SIMULATION, EndpointCategory.ANALYSIS)
        )
        
        # Complex endpoint or has manager = managed routing
        if endpoint.manager or endpoint.complexity >= self.HIGH_COMPLEXITY_THRESHOLD:
            self._stats["managed_routes"] += 1
            return RouteDecision(
                strategy=RouteStrategy.MANAGED,
                target=endpoint.manager or endpoint.path,
                timeout_ms=timeout_ms,
                use_shadow_race=use_shadow_race,
                patience_threshold_ms=endpoint.base_timeout_ms,  # Cache after base timeout
                fallback=endpoint.fallback,
                reason="High complexity - using manager with Shadow-Race" if use_shadow_race else "Has manager - routed through orchestrator",
                priority=endpoint.priority,
                endpoint_config=endpoint
            )
        
        # Medium complexity - direct but with monitoring
        self._stats["direct_routes"] += 1
        return RouteDecision(
            strategy=RouteStrategy.DIRECT,
            target=endpoint.path,
            timeout_ms=timeout_ms,
            use_shadow_race=False,
            fallback=endpoint.fallback,
            reason="Medium complexity - direct call with fallback available",
            priority=endpoint.priority,
            endpoint_config=endpoint
        )
    
    async def execute_with_shadow_race(
        self,
        decision: RouteDecision,
        live_task,
        cache_task
    ) -> ShadowRaceResult:
        """
        Execute request with Shadow-Race pattern.
        
        Args:
            decision: RouteDecision from recommend()
            live_task: Async callable for live request
            cache_task: Async callable for cache fallback
            
        Returns:
            ShadowRaceResult with data and source info
        """
        if not decision.use_shadow_race:
            # No shadow race - just execute live
            try:
                result = await live_task()
                return ShadowRaceResult(
                    data=result,
                    source="live",
                    late_arrival_pending=False
                )
            except Exception as e:
                # Try fallback
                if decision.fallback:
                    try:
                        fallback_result = await cache_task()
                        return ShadowRaceResult(
                            data=fallback_result,
                            source="fallback",
                            error=str(e)
                        )
                    except:
                        pass
                raise
        
        # Use Shadow-Race
        return await self.shadow_race.execute(
            live_task=live_task,
            cache_fallback=cache_task,
            patience_ms=decision.patience_threshold_ms,
            endpoint=decision.target
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        total = self._stats["total_routes"]
        return {
            **self._stats,
            "direct_rate": (
                self._stats["direct_routes"] / total * 100 if total > 0 else 0
            ),
            "managed_rate": (
                self._stats["managed_routes"] / total * 100 if total > 0 else 0
            ),
            "fallback_rate": (
                self._stats["fallback_routes"] / total * 100 if total > 0 else 0
            ),
            "shadow_race_stats": self.shadow_race.get_stats()
        }
    
    def get_route_matrix(self) -> List[Dict[str, Any]]:
        """Get routing matrix for all registered endpoints."""
        matrix = []
        for endpoint in self.registry.get_all():
            decision = self.recommend(endpoint.path)
            matrix.append({
                "path": endpoint.path,
                "category": endpoint.category.value,
                "complexity": endpoint.complexity,
                "recommended_strategy": decision.strategy.value,
                "timeout_ms": decision.timeout_ms,
                "use_shadow_race": decision.use_shadow_race,
                "has_fallback": endpoint.fallback is not None
            })
        return matrix
