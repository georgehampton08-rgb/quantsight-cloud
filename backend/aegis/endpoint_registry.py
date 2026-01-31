"""
Endpoint Registry - Self-discovering catalog for Nexus Hub

Phase 1: Complex endpoints (Simulation, Analysis) registered first
Phase 2: Simple Data APIs to be added during gradual migration

Each endpoint has:
- category: Type classification for routing decisions
- dependencies: Services required for this endpoint
- complexity: 1-10 scale (higher = more resources needed)
- base_timeout_ms: Baseline patience for this request type
- adaptive_buffer_ms: Extra buffer for Dynamic TTL calculation
- fallback: Cache path to use when primary fails
- manager: Which orchestrator handles this endpoint (if any)
- priority: Default priority level for queuing
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class EndpointCategory(Enum):
    """Categories for endpoint classification."""
    CORE = "core"           # Health checks, basic info
    SIMULATION = "simulation"  # Monte Carlo, projections
    ANALYSIS = "analysis"     # Matchup analysis, confluence
    DATA = "data"            # Player/team data fetching
    EXTERNAL = "external"    # External API dependent
    ADMIN = "admin"          # Admin-only endpoints


class EndpointPriority(Enum):
    """Priority levels for queue ordering."""
    CRITICAL = "critical"   # Health checks, must never fail
    HIGH = "high"           # User-facing simulations
    MEDIUM = "medium"       # Standard requests
    LOW = "low"             # Background refreshes
    BACKGROUND = "background"  # Can be delayed indefinitely


@dataclass
class EndpointConfig:
    """Configuration for a registered endpoint."""
    path: str
    category: EndpointCategory
    dependencies: List[str] = field(default_factory=list)
    complexity: int = 5
    base_timeout_ms: int = 500
    adaptive_buffer_ms: int = 200
    fallback: Optional[str] = None
    manager: Optional[str] = None
    priority: EndpointPriority = EndpointPriority.MEDIUM
    health_check: bool = False
    requires_auth: bool = False
    
    def get_dynamic_ttl(self) -> int:
        """Calculate Dynamic TTL (base + buffer)."""
        return self.base_timeout_ms + self.adaptive_buffer_ms
    
    def __repr__(self):
        return f"<Endpoint {self.path} [{self.category.value}] complexity={self.complexity}>"


# =============================================================================
# PHASE 1: COMPLEX ENDPOINTS (Simulation + Analysis)
# These are registered first during gradual migration
# =============================================================================

ENDPOINT_REGISTRY: Dict[str, EndpointConfig] = {
    
    # -------------------------------------------------------------------------
    # CORE APIs - Always available, minimal dependencies, fast
    # -------------------------------------------------------------------------
    
    "/health": EndpointConfig(
        path="/health",
        category=EndpointCategory.CORE,
        dependencies=[],
        complexity=1,
        base_timeout_ms=100,
        adaptive_buffer_ms=50,
        fallback=None,
        manager=None,
        priority=EndpointPriority.CRITICAL,
        health_check=True
    ),
    
    "/aegis/health": EndpointConfig(
        path="/aegis/health",
        category=EndpointCategory.CORE,
        dependencies=["aegis_brain", "sovereign_router"],
        complexity=2,
        base_timeout_ms=200,
        adaptive_buffer_ms=100,
        fallback=None,
        manager=None,
        priority=EndpointPriority.CRITICAL,
        health_check=True
    ),
    
    # -------------------------------------------------------------------------
    # SIMULATION APIs - Heavy computation, benefits from manager
    # -------------------------------------------------------------------------
    
    "/aegis/simulate/{player_id}": EndpointConfig(
        path="/aegis/simulate/{player_id}",
        category=EndpointCategory.SIMULATION,
        dependencies=["database", "nba_api", "sovereign_router", "aegis_orchestrator"],
        complexity=8,
        base_timeout_ms=800,
        adaptive_buffer_ms=500,
        fallback="/cache/simulation/{player_id}",
        manager="aegis_orchestrator",
        priority=EndpointPriority.HIGH
    ),
    
    "/crucible/simulate": EndpointConfig(
        path="/crucible/simulate",
        category=EndpointCategory.SIMULATION,
        dependencies=["database", "nba_api", "gemini", "crucible_engine"],
        complexity=9,
        base_timeout_ms=1200,
        adaptive_buffer_ms=800,
        fallback="/cache/crucible/{game_id}",
        manager="crucible_engine",
        priority=EndpointPriority.HIGH
    ),
    
    "/aegis/player/{player_id}": EndpointConfig(
        path="/aegis/player/{player_id}",
        category=EndpointCategory.DATA,
        dependencies=["database", "aegis_brain"],
        complexity=4,
        base_timeout_ms=400,
        adaptive_buffer_ms=200,
        fallback="/cache/player/{player_id}",
        manager="aegis_brain",
        priority=EndpointPriority.MEDIUM
    ),
    
    # -------------------------------------------------------------------------
    # ANALYSIS APIs - Moderate computation, orchestration beneficial
    # -------------------------------------------------------------------------
    
    "/matchup/analyze": EndpointConfig(
        path="/matchup/analyze",
        category=EndpointCategory.ANALYSIS,
        dependencies=["database", "defense_matrix", "matchup_lab"],
        complexity=6,
        base_timeout_ms=600,
        adaptive_buffer_ms=400,
        fallback="/cache/matchup/{home_team}/{away_team}",
        manager="matchup_orchestrator",
        priority=EndpointPriority.MEDIUM
    ),
    
    "/aegis/matchup": EndpointConfig(
        path="/aegis/matchup",
        category=EndpointCategory.ANALYSIS,
        dependencies=["database", "vertex_engine", "matchup_lab"],
        complexity=7,
        base_timeout_ms=700,
        adaptive_buffer_ms=500,
        fallback="/cache/aegis_matchup/{home_team_id}/{away_team_id}",
        manager="matchup_orchestrator",
        priority=EndpointPriority.MEDIUM
    ),
    
    "/confluence/{player_id}": EndpointConfig(
        path="/confluence/{player_id}",
        category=EndpointCategory.ANALYSIS,
        dependencies=["database", "confluence_scorer", "defense_matrix"],
        complexity=5,
        base_timeout_ms=500,
        adaptive_buffer_ms=300,
        fallback="/cache/confluence/{player_id}",
        manager="confluence_scorer",
        priority=EndpointPriority.MEDIUM
    ),
    
    "/vertex/analyze/{player_id}/{opponent_id}": EndpointConfig(
        path="/vertex/analyze/{player_id}/{opponent_id}",
        category=EndpointCategory.ANALYSIS,
        dependencies=["database", "vertex_engine"],
        complexity=6,
        base_timeout_ms=600,
        adaptive_buffer_ms=400,
        fallback="/cache/vertex/{player_id}/{opponent_id}",
        manager="vertex_engine",
        priority=EndpointPriority.MEDIUM
    ),
    
    # -------------------------------------------------------------------------
    # EXTERNAL API ENDPOINTS - High patience required
    # -------------------------------------------------------------------------
    
    "/h2h/{player_id}/{opponent_id}": EndpointConfig(
        path="/h2h/{player_id}/{opponent_id}",
        category=EndpointCategory.EXTERNAL,
        dependencies=["nba_api", "database"],
        complexity=6,
        base_timeout_ms=1200,
        adaptive_buffer_ms=2000,  # Very patient - NBA API can be slow
        fallback="/cache/h2h/{player_id}/{opponent_id}",
        manager=None,
        priority=EndpointPriority.LOW
    ),
    
    "/player/{player_id}/refresh": EndpointConfig(
        path="/player/{player_id}/refresh",
        category=EndpointCategory.EXTERNAL,
        dependencies=["nba_api", "database"],
        complexity=5,
        base_timeout_ms=1000,
        adaptive_buffer_ms=1500,
        fallback=None,  # Refresh has no fallback - it's the source
        manager=None,
        priority=EndpointPriority.LOW
    ),
    
    # -------------------------------------------------------------------------
    # ADMIN ENDPOINTS - Protected, require auth
    # -------------------------------------------------------------------------
    
    "/nexus/overview": EndpointConfig(
        path="/nexus/overview",
        category=EndpointCategory.ADMIN,
        dependencies=["nexus_hub"],
        complexity=3,
        base_timeout_ms=300,
        adaptive_buffer_ms=200,
        fallback=None,
        manager="nexus_hub",
        priority=EndpointPriority.MEDIUM,
        requires_auth=True
    ),
    
    "/nexus/health": EndpointConfig(
        path="/nexus/health",
        category=EndpointCategory.ADMIN,
        dependencies=["nexus_hub", "health_gate"],
        complexity=2,
        base_timeout_ms=200,
        adaptive_buffer_ms=100,
        fallback=None,
        manager="nexus_hub",
        priority=EndpointPriority.CRITICAL,
        requires_auth=True
    ),
    
    "/nexus/cooldowns": EndpointConfig(
        path="/nexus/cooldowns",
        category=EndpointCategory.ADMIN,
        dependencies=["health_gate"],
        complexity=1,
        base_timeout_ms=100,
        adaptive_buffer_ms=50,
        fallback=None,
        manager=None,
        priority=EndpointPriority.MEDIUM,
        requires_auth=True
    ),
}


class EndpointRegistry:
    """
    Self-discovering endpoint catalog for Nexus Hub.
    
    Responsibilities:
    1. Register and catalog all endpoints
    2. Match incoming requests to endpoint configurations
    3. Provide routing hints based on complexity and dependencies
    4. Track endpoint health states
    """
    
    def __init__(self):
        self.endpoints: Dict[str, EndpointConfig] = dict(ENDPOINT_REGISTRY)
        self._path_patterns: Dict[str, re.Pattern] = {}
        self._compile_patterns()
        logger.info(f"[NEXUS] EndpointRegistry initialized with {len(self.endpoints)} endpoints")
    
    def _compile_patterns(self):
        """Compile path patterns for efficient matching."""
        for path in self.endpoints:
            # Convert {param} to regex groups
            pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', path)
            pattern = f"^{pattern}$"
            self._path_patterns[path] = re.compile(pattern)
    
    def register(self, config: EndpointConfig) -> None:
        """Register a new endpoint configuration."""
        self.endpoints[config.path] = config
        pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', config.path)
        pattern = f"^{pattern}$"
        self._path_patterns[config.path] = re.compile(pattern)
        logger.info(f"[NEXUS] Registered endpoint: {config.path}")
    
    def match(self, request_path: str) -> Optional[EndpointConfig]:
        """
        Match a request path to its endpoint configuration.
        
        Args:
            request_path: The incoming request path (e.g., "/aegis/simulate/1628389")
            
        Returns:
            EndpointConfig if matched, None otherwise
        """
        # Strip query params
        path = request_path.split("?")[0]
        
        # Try exact match first
        if path in self.endpoints:
            return self.endpoints[path]
        
        # Try pattern matching
        for template, pattern in self._path_patterns.items():
            if pattern.match(path):
                return self.endpoints[template]
        
        return None
    
    def get_by_category(self, category: EndpointCategory) -> List[EndpointConfig]:
        """Get all endpoints in a category."""
        return [ep for ep in self.endpoints.values() if ep.category == category]
    
    def get_by_manager(self, manager: str) -> List[EndpointConfig]:
        """Get all endpoints managed by a specific orchestrator."""
        return [ep for ep in self.endpoints.values() if ep.manager == manager]
    
    def get_high_complexity(self, threshold: int = 5) -> List[EndpointConfig]:
        """Get endpoints above complexity threshold."""
        return [ep for ep in self.endpoints.values() if ep.complexity >= threshold]
    
    def get_with_fallback(self) -> List[EndpointConfig]:
        """Get endpoints that have cache fallbacks available."""
        return [ep for ep in self.endpoints.values() if ep.fallback is not None]
    
    def get_all(self) -> List[EndpointConfig]:
        """Get all registered endpoints."""
        return list(self.endpoints.values())
    
    def summary(self) -> Dict[str, Any]:
        """Get registry summary for admin dashboard."""
        by_category = {}
        for cat in EndpointCategory:
            endpoints = self.get_by_category(cat)
            by_category[cat.value] = {
                "count": len(endpoints),
                "paths": [ep.path for ep in endpoints],
                "avg_complexity": sum(ep.complexity for ep in endpoints) / max(len(endpoints), 1)
            }
        
        return {
            "total_endpoints": len(self.endpoints),
            "by_category": by_category,
            "with_fallback": len(self.get_with_fallback()),
            "high_complexity": len(self.get_high_complexity()),
            "phase": "Phase 1 - Complex Endpoints"
        }


# =============================================================================
# PHASE 2: SIMPLE DATA APIs (To be added during gradual migration)
# =============================================================================
# These will be registered later:
# - /players/search
# - /teams
# - /roster/{team_id}
# - /schedule
# - /player/{player_id}
# - /player/{player_id}/stats
# - /player/{player_id}/career
# - /teams/defense/{team_abbrev}
# - /radar/{player_id}
# =============================================================================
