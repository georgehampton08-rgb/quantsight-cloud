"""
Vanguard gRPC Client — Phase 6 Step 6.3
=========================================
Async gRPC client for communicating with the Vanguard service.

Current: points to localhost:50051 (embedded mode)
Future:  points to VANGUARD_GRPC_URL env var (extracted mode)

Implements the same logical interface as the direct imports it replaces:
    client.store_incident(incident_data)
    client.get_circuit_state(endpoint)
    client.record_outcome(endpoint, status_code)

Connection retry: 3 attempts, exponential backoff
On total failure: FAIL OPEN (log warning, do not crash request)
"""
import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import grpc
from grpc import aio as grpc_aio

from vanguard.proto.generated import vanguard_pb2
from vanguard.proto.generated import vanguard_pb2_grpc

logger = logging.getLogger(__name__)

# Default for embedded mode; overridden by env var when extracted
_DEFAULT_TARGET = "localhost:50051"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds


class VanguardGrpcClient:
    """Async gRPC client to the Vanguard service."""

    def __init__(self):
        self._target = os.getenv("VANGUARD_GRPC_URL", _DEFAULT_TARGET)
        self._channel: Optional[grpc_aio.Channel] = None
        self._incident_stub = None
        self._circuit_stub = None
        self._health_stub = None

    def _ensure_channel(self):
        """Lazily create the gRPC channel and stubs."""
        if self._channel is None:
            self._channel = grpc_aio.insecure_channel(
                self._target,
                options=[
                    ("grpc.max_receive_message_length", 4 * 1024 * 1024),
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.enable_retries", 1),
                ],
            )
            self._incident_stub = vanguard_pb2_grpc.IncidentServiceStub(self._channel)
            self._circuit_stub = vanguard_pb2_grpc.CircuitServiceStub(self._channel)
            self._health_stub = vanguard_pb2_grpc.VanguardHealthServiceStub(self._channel)

    async def _call_with_retry(self, fn, *args, **kwargs):
        """Call a gRPC method with retry + exponential backoff. FAIL OPEN on total failure."""
        self._ensure_channel()
        last_error = None

        for attempt in range(_MAX_RETRIES):
            try:
                return await fn(*args, **kwargs)
            except grpc.aio.AioRpcError as e:
                last_error = e
                if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        f"gRPC call failed (attempt {attempt + 1}/{_MAX_RETRIES}): "
                        f"{e.code().name} — retrying in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                else:
                    # Non-retryable error
                    logger.error(f"gRPC call failed (non-retryable): {e.code().name} {e.details()}")
                    break
            except Exception as e:
                last_error = e
                logger.error(f"gRPC call unexpected error: {e}")
                break

        # FAIL OPEN — log and return None
        logger.warning(
            f"gRPC call FAIL OPEN after {_MAX_RETRIES} attempts. "
            f"Last error: {last_error}. Request will proceed without Vanguard."
        )
        return None

    # ── Incident operations ──────────────────────────────────────

    async def store_incident(self, incident_data: Dict[str, Any]) -> bool:
        """Store an incident via gRPC. Returns True on success, False on failure (FAIL OPEN)."""
        proto_incident = vanguard_pb2.Incident(
            fingerprint=incident_data.get("fingerprint", ""),
            endpoint=incident_data.get("endpoint", ""),
            error_type=incident_data.get("error_type", ""),
            severity=incident_data.get("severity", ""),
            occurrence_count=incident_data.get("occurrence_count", 0),
            status=incident_data.get("status", "active"),
            created_at=incident_data.get("created_at", ""),
            last_seen=incident_data.get("last_seen", ""),
            schema_version=incident_data.get("schema_version", "v1"),
        )
        request = vanguard_pb2.StoreIncidentRequest(incident=proto_incident)
        response = await self._call_with_retry(self._incident_stub.StoreIncident, request)
        if response is None:
            return False
        return response.success

    async def get_incident(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Get an incident by fingerprint. Returns dict or None."""
        request = vanguard_pb2.GetIncidentRequest(fingerprint=fingerprint)
        response = await self._call_with_retry(self._incident_stub.GetIncident, request)
        if response is None or not response.found:
            return None
        inc = response.incident
        return {
            "fingerprint": inc.fingerprint,
            "endpoint": inc.endpoint,
            "error_type": inc.error_type,
            "severity": inc.severity,
            "occurrence_count": inc.occurrence_count,
            "status": inc.status,
            "created_at": inc.created_at,
            "last_seen": inc.last_seen,
            "schema_version": inc.schema_version,
        }

    async def list_incidents(self, limit: int = 100, status_filter: str = "") -> List[Dict]:
        """List incidents. Returns list of dicts."""
        request = vanguard_pb2.ListIncidentsRequest(limit=limit, status_filter=status_filter)
        response = await self._call_with_retry(self._incident_stub.ListIncidents, request)
        if response is None:
            return []
        return [
            {
                "fingerprint": inc.fingerprint,
                "endpoint": inc.endpoint,
                "error_type": inc.error_type,
                "severity": inc.severity,
                "occurrence_count": inc.occurrence_count,
                "status": inc.status,
                "created_at": inc.created_at,
                "last_seen": inc.last_seen,
            }
            for inc in response.incidents
        ]

    async def resolve_incident(self, fingerprint: str, resolution_notes: str = "") -> bool:
        """Resolve an incident. Returns True on success."""
        request = vanguard_pb2.ResolveIncidentRequest(
            fingerprint=fingerprint,
            resolution_notes=resolution_notes,
        )
        response = await self._call_with_retry(self._incident_stub.ResolveIncident, request)
        if response is None:
            return False
        return response.success

    # ── Circuit breaker operations ───────────────────────────────

    async def get_circuit_state(self, endpoint: str) -> Dict[str, Any]:
        """Get circuit state for an endpoint. Returns dict with state info."""
        request = vanguard_pb2.CircuitStateRequest(endpoint=endpoint)
        response = await self._call_with_retry(self._circuit_stub.GetCircuitState, request)
        if response is None:
            # FAIL OPEN: assume CLOSED
            return {"endpoint": endpoint, "state": "CLOSED", "failure_rate": 0.0, "opened_at": ""}
        return {
            "endpoint": response.endpoint,
            "state": response.state,
            "failure_rate": response.failure_rate,
            "opened_at": response.opened_at,
        }

    async def record_outcome(self, endpoint: str, status_code: int) -> bool:
        """Record an endpoint outcome. Returns True on success."""
        request = vanguard_pb2.RecordOutcomeRequest(
            endpoint=endpoint,
            status_code=status_code,
        )
        response = await self._call_with_retry(self._circuit_stub.RecordOutcome, request)
        if response is None:
            return False
        return response.accepted

    # ── Health operations ────────────────────────────────────────

    async def get_health(self) -> Dict[str, Any]:
        """Get Vanguard health status."""
        request = vanguard_pb2.HealthRequest()
        response = await self._call_with_retry(self._health_stub.GetHealth, request)
        if response is None:
            return {"mode": "UNKNOWN", "firestore_ok": False, "redis_ok": False}
        return {
            "mode": response.mode,
            "firestore_ok": response.firestore_ok,
            "redis_ok": response.redis_ok,
            "gemini_ok": response.gemini_ok,
            "version": response.version,
            "active_fallbacks": list(response.active_fallbacks),
        }

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self):
        """Close the gRPC channel."""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            logger.info("Vanguard gRPC client channel closed")


# ── Singleton ────────────────────────────────────────────────────

_client: Optional[VanguardGrpcClient] = None


def get_grpc_client() -> VanguardGrpcClient:
    """Get or create the global Vanguard gRPC client."""
    global _client
    if _client is None:
        _client = VanguardGrpcClient()
    return _client


async def close_grpc_client():
    """Close the global gRPC client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
