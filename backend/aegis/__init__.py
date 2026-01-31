"""
Aegis Module v3.2
=================
Intelligence, feedback layer, and Nexus Hub supervisor components.
"""

# Core routing
from aegis.sovereign_router import SovereignRouter
from aegis.healer_protocol import HealerProtocol

# Feedback layer
from aegis.learning_ledger import LearningLedger
from aegis.next_day_audit import NextDayAudit
from aegis.confluence_scorer import ConfluenceScorer
from aegis.simulation_cache import SimulationCache

# Orchestration
from aegis.orchestrator import AegisOrchestrator, OrchestratorConfig

# Nexus Hub - API Supervisor
from aegis.nexus_hub import NexusHub, get_nexus_hub
from aegis.endpoint_registry import EndpointRegistry, EndpointConfig, EndpointCategory
from aegis.health_gate import HealthGate, HealthStatus, SystemHealth
from aegis.adaptive_router import AdaptiveRouter, RouteDecision, RouteStrategy
from aegis.shadow_race import ShadowRace, ShadowRaceResult
from aegis.priority_queue import PriorityQueue, Priority
from aegis.error_handler import NexusErrorHandler, NexusError, ErrorCode

__all__ = [
    # Original exports
    'SovereignRouter',
    'HealerProtocol',
    'LearningLedger',
    'NextDayAudit',
    'ConfluenceScorer',
    'SimulationCache',
    'AegisOrchestrator',
    'OrchestratorConfig',
    # Nexus Hub exports
    'NexusHub',
    'get_nexus_hub',
    'EndpointRegistry',
    'EndpointConfig',
    'EndpointCategory',
    'HealthGate',
    'HealthStatus',
    'SystemHealth',
    'AdaptiveRouter',
    'RouteDecision',
    'RouteStrategy',
    'ShadowRace',
    'ShadowRaceResult',
    'PriorityQueue',
    'Priority',
    'NexusErrorHandler',
    'NexusError',
    'ErrorCode',
]

