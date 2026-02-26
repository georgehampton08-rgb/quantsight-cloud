"""
Vanguard gRPC Server — Phase 6 Step 6.3
=========================================
Implements the Vanguard gRPC servicers.

Can run either:
  - Embedded inside the monolith (current — localhost:50051)
  - As a standalone Cloud Run service (extraction target)

All servicers delegate to existing archivist/surgeon subsystems,
keeping the gRPC layer as a thin transport wrapper.
"""
import logging
import asyncio
from datetime import datetime, timezone

import grpc
from grpc import aio as grpc_aio

from vanguard.proto.generated import vanguard_pb2
from vanguard.proto.generated import vanguard_pb2_grpc

logger = logging.getLogger(__name__)


# ── Incident Service ─────────────────────────────────────────────

class VanguardIncidentServicer(vanguard_pb2_grpc.IncidentServiceServicer):
    """gRPC servicer for incident storage operations."""

    async def StoreIncident(self, request, context):
        try:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()

            incident_data = {
                "fingerprint": request.incident.fingerprint,
                "endpoint": request.incident.endpoint,
                "error_type": request.incident.error_type,
                "severity": request.incident.severity,
                "occurrence_count": request.incident.occurrence_count,
                "status": request.incident.status or "active",
                "created_at": request.incident.created_at or datetime.now(timezone.utc).isoformat(),
                "last_seen": request.incident.last_seen or datetime.now(timezone.utc).isoformat(),
                "schema_version": request.incident.schema_version or "v1",
            }

            success = await storage.store(incident_data)
            return vanguard_pb2.StoreIncidentResponse(
                success=success,
                fingerprint=request.incident.fingerprint,
            )
        except Exception as e:
            logger.error(f"gRPC StoreIncident failed: {e}")
            return vanguard_pb2.StoreIncidentResponse(
                success=False,
                fingerprint=request.incident.fingerprint,
            )

    async def GetIncident(self, request, context):
        try:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()
            incident = await storage.load(request.fingerprint)

            if incident is None:
                return vanguard_pb2.GetIncidentResponse(found=False)

            proto_incident = vanguard_pb2.Incident(
                fingerprint=incident.get("fingerprint", ""),
                endpoint=incident.get("endpoint", ""),
                error_type=incident.get("error_type", ""),
                severity=incident.get("severity", ""),
                occurrence_count=incident.get("occurrence_count", 0),
                status=incident.get("status", ""),
                created_at=incident.get("created_at", ""),
                last_seen=incident.get("last_seen", ""),
                schema_version=incident.get("schema_version", ""),
            )
            return vanguard_pb2.GetIncidentResponse(
                incident=proto_incident,
                found=True,
            )
        except Exception as e:
            logger.error(f"gRPC GetIncident failed: {e}")
            return vanguard_pb2.GetIncidentResponse(found=False)

    async def ListIncidents(self, request, context):
        try:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()
            limit = request.limit or 100

            fingerprints = await storage.list_incidents(limit=limit)
            incidents = []
            for fp in fingerprints:
                data = await storage.load(fp)
                if data is None:
                    continue
                # Apply status filter if provided
                if request.status_filter and data.get("status") != request.status_filter:
                    continue
                incidents.append(vanguard_pb2.Incident(
                    fingerprint=data.get("fingerprint", fp),
                    endpoint=data.get("endpoint", ""),
                    error_type=data.get("error_type", ""),
                    severity=data.get("severity", ""),
                    occurrence_count=data.get("occurrence_count", 0),
                    status=data.get("status", ""),
                    created_at=data.get("created_at", ""),
                    last_seen=data.get("last_seen", ""),
                    schema_version=data.get("schema_version", ""),
                ))
            return vanguard_pb2.ListIncidentsResponse(incidents=incidents)
        except Exception as e:
            logger.error(f"gRPC ListIncidents failed: {e}")
            return vanguard_pb2.ListIncidentsResponse(incidents=[])

    async def ResolveIncident(self, request, context):
        try:
            from vanguard.archivist.storage import get_incident_storage
            storage = get_incident_storage()
            success = await storage.resolve(request.fingerprint)
            return vanguard_pb2.ResolveIncidentResponse(success=success)
        except Exception as e:
            logger.error(f"gRPC ResolveIncident failed: {e}")
            return vanguard_pb2.ResolveIncidentResponse(success=False)


# ── Circuit Breaker Service ──────────────────────────────────────

class VanguardCircuitServicer(vanguard_pb2_grpc.CircuitServiceServicer):
    """gRPC servicer for circuit breaker state queries."""

    async def GetCircuitState(self, request, context):
        try:
            from vanguard.surgeon.circuit_breaker_v2 import get_circuit_breaker_v2
            cb = get_circuit_breaker_v2()
            state = await cb.get_state(request.endpoint)
            failure_rate = 0.0
            opened_at = ""

            # Try to get detailed state info
            try:
                endpoint_info = cb._endpoint_states.get(request.endpoint)
                if endpoint_info:
                    failure_rate = getattr(endpoint_info, "failure_rate", 0.0)
                    opened_at = getattr(endpoint_info, "opened_at", "")
            except Exception:
                pass

            return vanguard_pb2.CircuitStateResponse(
                endpoint=request.endpoint,
                state=state.value if hasattr(state, "value") else str(state),
                failure_rate=failure_rate,
                opened_at=str(opened_at) if opened_at else "",
            )
        except Exception as e:
            logger.error(f"gRPC GetCircuitState failed: {e}")
            return vanguard_pb2.CircuitStateResponse(
                endpoint=request.endpoint,
                state="CLOSED",
                failure_rate=0.0,
            )

    async def RecordOutcome(self, request, context):
        try:
            from vanguard.surgeon.failure_tracker import get_failure_tracker
            from vanguard.surgeon.circuit_breaker_v2 import get_circuit_breaker_v2
            tracker = get_failure_tracker()
            cb = get_circuit_breaker_v2()

            await tracker.record(request.endpoint, request.status_code)
            await cb.evaluate_endpoint(request.endpoint)

            return vanguard_pb2.RecordOutcomeResponse(accepted=True)
        except Exception as e:
            logger.error(f"gRPC RecordOutcome failed: {e}")
            return vanguard_pb2.RecordOutcomeResponse(accepted=False)


# ── Health Service ───────────────────────────────────────────────

class VanguardHealthServicer(vanguard_pb2_grpc.VanguardHealthServiceServicer):
    """gRPC servicer for Vanguard health queries."""

    async def GetHealth(self, request, context):
        try:
            from vanguard.snapshot import SYSTEM_SNAPSHOT
            from vanguard.core.config import get_vanguard_config

            config = get_vanguard_config()
            snap = SYSTEM_SNAPSHOT

            return vanguard_pb2.HealthResponse(
                mode=config.mode.value if hasattr(config.mode, "value") else str(config.mode),
                firestore_ok=snap.get("firestore_ok", False),
                redis_ok=snap.get("redis_ok", False),
                gemini_ok=snap.get("gemini_ok", False),
                version="3.1.0",
                active_fallbacks=snap.get("active_fallbacks", []),
            )
        except Exception as e:
            logger.error(f"gRPC GetHealth failed: {e}")
            return vanguard_pb2.HealthResponse(
                mode="UNKNOWN",
                firestore_ok=False,
                redis_ok=False,
                gemini_ok=False,
                version="3.1.0",
            )


# ── Server lifecycle ─────────────────────────────────────────────

_grpc_server = None


async def start_grpc_server(port: int = 50051):
    """Start the embedded gRPC server."""
    global _grpc_server

    server = grpc_aio.server(
        options=[
            ("grpc.max_receive_message_length", 4 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 30000),
        ]
    )

    vanguard_pb2_grpc.add_IncidentServiceServicer_to_server(
        VanguardIncidentServicer(), server
    )
    vanguard_pb2_grpc.add_CircuitServiceServicer_to_server(
        VanguardCircuitServicer(), server
    )
    vanguard_pb2_grpc.add_VanguardHealthServiceServicer_to_server(
        VanguardHealthServicer(), server
    )

    listen_addr = f"[::]:{port}"
    server.add_insecure_port(listen_addr)

    await server.start()
    _grpc_server = server
    logger.info(f"Vanguard gRPC server started on {listen_addr}")
    return server


async def stop_grpc_server(grace: int = 5):
    """Gracefully stop the gRPC server."""
    global _grpc_server
    if _grpc_server is not None:
        await _grpc_server.stop(grace=grace)
        logger.info("Vanguard gRPC server stopped")
        _grpc_server = None


def get_grpc_server():
    """Return the current gRPC server instance (or None)."""
    return _grpc_server
