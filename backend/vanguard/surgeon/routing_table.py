"""
Surgeon Dynamic Routing Table — Phase 5 Step 5.2
===================================================
When Gemini API is unavailable, Surgeon rewrites the in-memory routing
table to substitute heuristic triage — without human intervention and
without touching Vanguard's ingestion path.

Data structure:
  In-memory dict: route_key → RouteConfig
  RouteConfig fields:
      primary_handler: str (fully qualified function name)
      fallback_handler: str | None
      fallback_active: bool
      fallback_reason: str | None
      fallback_activated_at: datetime | None

Rules:
  - Routing table modifications are in-memory only
  - No file writes, no Firestore writes for routing changes
  - Surgeon CANNOT modify blast radius routes via routing table
  - All routing table state exposed at /health/deps under routing_table key
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ── Blast radius routes (routing table CANNOT touch these) ───────────────────
_BLAST_RADIUS_ROUTES = frozenset({
    "/healthz",
    "/readyz",
    "/health",
    "/health/deps",
    "/vanguard/health",
    "/vanguard/admin/incidents",
})

_BLAST_RADIUS_PREFIXES = ("/vanguard/", "/admin/")


def _is_blast_radius(route_key: str) -> bool:
    """Return True if this route is blast-radius protected."""
    if route_key in _BLAST_RADIUS_ROUTES:
        return True
    for prefix in _BLAST_RADIUS_PREFIXES:
        if route_key.startswith(prefix):
            return True
    return False


@dataclass
class RouteConfig:
    """Configuration for a single routable path."""
    primary_handler: str          # fully qualified function name
    fallback_handler: Optional[str] = None
    fallback_active: bool = False
    fallback_reason: Optional[str] = None
    fallback_activated_at: Optional[datetime] = None


class RoutingTable:
    """
    In-memory routing table that allows the Surgeon to dynamically
    substitute fallback handlers when primary dependencies go down.

    All mutations are in-memory only. No Firestore, no file writes.
    """

    def __init__(self):
        self._routes: Dict[str, RouteConfig] = {}
        self._lock = asyncio.Lock()

        # Register initial fallback entries
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register Phase 5 initial fallback entries."""
        self._routes["gemini_triage_path"] = RouteConfig(
            primary_handler="vanguard.ai.ai_analyzer.VanguardAIAnalyzer.analyze_incident",
            fallback_handler="vanguard.ai.heuristic_triage.generate_heuristic_triage",
        )
        logger.info(
            "routing_table_initialized",
            routes=list(self._routes.keys()),
        )

    def register_route(
        self,
        route_key: str,
        primary_handler: str,
        fallback_handler: Optional[str] = None,
    ) -> bool:
        """
        Register a new route in the routing table.
        Returns False if the route_key is blast-radius protected.
        """
        if _is_blast_radius(route_key):
            logger.warning(
                "routing_table_register_blocked",
                route_key=route_key,
                reason="blast_radius_protected",
            )
            return False

        self._routes[route_key] = RouteConfig(
            primary_handler=primary_handler,
            fallback_handler=fallback_handler,
        )
        logger.info("routing_table_route_registered", route_key=route_key)
        return True

    async def activate_fallback(self, route_key: str, reason: str) -> bool:
        """
        Activate the fallback handler for a given route.

        Returns False if:
        - route_key not found
        - route_key is blast-radius protected
        - no fallback_handler registered
        - fallback already active
        """
        if _is_blast_radius(route_key):
            logger.warning(
                "routing_table_activate_blocked",
                route_key=route_key,
                reason="blast_radius_protected",
            )
            return False

        async with self._lock:
            route = self._routes.get(route_key)
            if route is None:
                logger.warning(
                    "routing_table_activate_not_found",
                    route_key=route_key,
                )
                return False

            if route.fallback_handler is None:
                logger.warning(
                    "routing_table_no_fallback",
                    route_key=route_key,
                )
                return False

            if route.fallback_active:
                logger.debug(
                    "routing_table_already_active",
                    route_key=route_key,
                )
                return True  # idempotent

            route.fallback_active = True
            route.fallback_reason = reason
            route.fallback_activated_at = datetime.now(timezone.utc)

            logger.warning(
                "routing_table_fallback_ACTIVATED",
                route_key=route_key,
                reason=reason,
                fallback_handler=route.fallback_handler,
            )
            return True

    async def deactivate_fallback(self, route_key: str) -> Optional[float]:
        """
        Deactivate the fallback handler for a given route.

        Returns the recovery_time_s (seconds the fallback was active),
        or None if the fallback was not active.
        """
        async with self._lock:
            route = self._routes.get(route_key)
            if route is None or not route.fallback_active:
                return None

            recovery_time_s = 0.0
            if route.fallback_activated_at is not None:
                elapsed = datetime.now(timezone.utc) - route.fallback_activated_at
                recovery_time_s = elapsed.total_seconds()

            route.fallback_active = False
            route.fallback_reason = None
            route.fallback_activated_at = None

            logger.info(
                "routing_table_fallback_DEACTIVATED",
                route_key=route_key,
                recovery_time_s=round(recovery_time_s, 2),
            )
            return recovery_time_s

    def is_fallback_active(self, route_key: str) -> bool:
        """Check if a fallback is currently active for a route."""
        route = self._routes.get(route_key)
        return route is not None and route.fallback_active

    def get_active_fallbacks(self) -> List[Dict]:
        """
        Return a list of all active fallbacks for /health/deps exposure.
        """
        active = []
        for key, route in self._routes.items():
            if route.fallback_active:
                active.append({
                    "route_key": key,
                    "primary_handler": route.primary_handler,
                    "fallback_handler": route.fallback_handler,
                    "reason": route.fallback_reason,
                    "activated_at": (
                        route.fallback_activated_at.isoformat()
                        if route.fallback_activated_at
                        else None
                    ),
                })
        return active

    def get_route(self, route_key: str) -> Optional[RouteConfig]:
        """Get the RouteConfig for a route key (or None)."""
        return self._routes.get(route_key)

    def get_all_routes(self) -> Dict[str, Dict]:
        """Diagnostic snapshot of all routes (for admin/health)."""
        snapshot = {}
        for key, route in self._routes.items():
            snapshot[key] = {
                "primary_handler": route.primary_handler,
                "fallback_handler": route.fallback_handler,
                "fallback_active": route.fallback_active,
                "fallback_reason": route.fallback_reason,
                "fallback_activated_at": (
                    route.fallback_activated_at.isoformat()
                    if route.fallback_activated_at
                    else None
                ),
            }
        return snapshot


# ── Singleton ────────────────────────────────────────────────────────────────
_routing_table: Optional[RoutingTable] = None


def get_routing_table() -> RoutingTable:
    """Get or create the global RoutingTable singleton."""
    global _routing_table
    if _routing_table is None:
        _routing_table = RoutingTable()
    return _routing_table
