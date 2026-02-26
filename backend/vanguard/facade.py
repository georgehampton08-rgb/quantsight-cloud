"""
Vanguard Facade — Strangler Fig Migration Layer (Phase 6 Step 6.4)
====================================================================
Provides a unified interface for Vanguard operations that transparently
routes to either:
  - DIRECT: In-process calls to archivist/surgeon (current default)
  - GRPC:   gRPC client calls (when FEATURE_GRPC_SERVER=true)

Usage:
    from vanguard.facade import get_vanguard_facade
    facade = get_vanguard_facade()
    await facade.store_incident(incident_data)
    state = await facade.get_circuit_state("/api/roster")

The facade is the Strangler Fig vine — new callers import only the facade,
and the flag flip migrates them from direct to gRPC without code changes.
"""
import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Use feature flag to determine routing
_USE_GRPC = None  # cached after first check


def _should_use_grpc() -> bool:
    """Check if gRPC transport is enabled."""
    global _USE_GRPC
    if _USE_GRPC is None:
        try:
            from vanguard.core.feature_flags import flag
            _USE_GRPC = flag("FEATURE_GRPC_SERVER")
        except Exception:
            _USE_GRPC = False
    return _USE_GRPC


class VanguardFacade:
    """
    Dual-path facade for Vanguard operations.

    When FEATURE_GRPC_SERVER=false (default): calls go directly to
    archivist/surgeon subsystems in-process.

    When FEATURE_GRPC_SERVER=true: calls are routed over gRPC to the
    embedded (or remote) Vanguard service.
    """

    # ── Incident operations ──────────────────────────────────────

    async def store_incident(self, incident_data: Dict[str, Any]) -> bool:
        """Store an incident via the active transport."""
        if _should_use_grpc():
            from vanguard.grpc_client import get_grpc_client
            client = get_grpc_client()
            return await client.store_incident(incident_data)
        else:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()
            return await storage.store(incident_data)

    async def get_incident(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Get an incident by fingerprint."""
        if _should_use_grpc():
            from vanguard.grpc_client import get_grpc_client
            client = get_grpc_client()
            return await client.get_incident(fingerprint)
        else:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()
            return await storage.load(fingerprint)

    async def list_incidents(self, limit: int = 100, status_filter: str = "") -> List[Dict]:
        """List incidents."""
        if _should_use_grpc():
            from vanguard.grpc_client import get_grpc_client
            client = get_grpc_client()
            return await client.list_incidents(limit=limit, status_filter=status_filter)
        else:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()
            fingerprints = await storage.list_incidents(limit=limit)
            results = []
            for fp in fingerprints:
                data = await storage.load(fp)
                if data and (not status_filter or data.get("status") == status_filter):
                    results.append(data)
            return results

    async def resolve_incident(self, fingerprint: str, notes: str = "") -> bool:
        """Resolve an incident."""
        if _should_use_grpc():
            from vanguard.grpc_client import get_grpc_client
            client = get_grpc_client()
            return await client.resolve_incident(fingerprint, notes)
        else:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()
            return await storage.resolve(fingerprint)

    # ── Circuit breaker operations ───────────────────────────────

    async def get_circuit_state(self, endpoint: str) -> Dict[str, Any]:
        """Get circuit breaker state for an endpoint."""
        if _should_use_grpc():
            from vanguard.grpc_client import get_grpc_client
            client = get_grpc_client()
            return await client.get_circuit_state(endpoint)
        else:
            try:
                from vanguard.surgeon.circuit_breaker_v2 import get_circuit_breaker_v2
                cb = get_circuit_breaker_v2()
                state = await cb.get_state(endpoint)
                return {
                    "endpoint": endpoint,
                    "state": state.value if hasattr(state, "value") else str(state),
                    "failure_rate": 0.0,
                    "opened_at": "",
                }
            except Exception:
                return {"endpoint": endpoint, "state": "CLOSED", "failure_rate": 0.0, "opened_at": ""}

    async def record_outcome(self, endpoint: str, status_code: int) -> bool:
        """Record an endpoint outcome for the circuit breaker."""
        if _should_use_grpc():
            from vanguard.grpc_client import get_grpc_client
            client = get_grpc_client()
            return await client.record_outcome(endpoint, status_code)
        else:
            try:
                from vanguard.surgeon.failure_tracker import get_failure_tracker
                tracker = get_failure_tracker()
                await tracker.record(endpoint, status_code)
                return True
            except Exception:
                return False

    # ── Health ───────────────────────────────────────────────────

    async def get_health(self) -> Dict[str, Any]:
        """Get Vanguard health status."""
        if _should_use_grpc():
            from vanguard.grpc_client import get_grpc_client
            client = get_grpc_client()
            return await client.get_health()
        else:
            try:
                from vanguard.snapshot import SYSTEM_SNAPSHOT
                from vanguard.core.config import get_vanguard_config
                config = get_vanguard_config()
                return {
                    "mode": config.mode.value if hasattr(config.mode, "value") else str(config.mode),
                    "firestore_ok": SYSTEM_SNAPSHOT.get("firestore_ok", False),
                    "redis_ok": SYSTEM_SNAPSHOT.get("redis_ok", False),
                    "gemini_ok": SYSTEM_SNAPSHOT.get("gemini_ok", False),
                    "version": "3.1.0",
                    "active_fallbacks": SYSTEM_SNAPSHOT.get("active_fallbacks", []),
                }
            except Exception:
                return {"mode": "UNKNOWN", "firestore_ok": False, "redis_ok": False}


# ── Singleton ────────────────────────────────────────────────────

_facade: Optional[VanguardFacade] = None


def get_vanguard_facade() -> VanguardFacade:
    """Get or create the global Vanguard facade."""
    global _facade
    if _facade is None:
        _facade = VanguardFacade()
        transport = "gRPC" if _should_use_grpc() else "DIRECT"
        logger.info(f"Vanguard facade initialized (transport={transport})")
    return _facade
