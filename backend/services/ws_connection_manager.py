"""
WebSocket Connection Manager — Phase 8 Step 8.2.2
===================================================
Manages all active WebSocket connections across the pulse service instance.
Thread-safe via asyncio.Lock.
Enforces MAX_CONNECTIONS per instance.

Design:
  - Each connection tracked by connection_id (UUID)
  - Subscription filters determine which broadcasts reach which client
  - Dead connections detected and pruned during broadcast
  - FAIL OPEN: broadcast failures disconnect the failing client silently
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# ── Connection state type ────────────────────────────────────────────────────
class ConnectionState:
    """Tracks a single WebSocket connection's metadata."""
    __slots__ = (
        "websocket", "filters", "session_token",
        "connected_at", "last_ping", "subscriptions",
    )

    def __init__(
        self,
        websocket: WebSocket,
        session_token: str,
    ):
        self.websocket = websocket
        self.filters: dict = {}
        self.session_token = session_token
        self.connected_at = datetime.now(timezone.utc)
        self.last_ping = datetime.now(timezone.utc)
        self.subscriptions: set = set()


class WebSocketConnectionManager:
    """
    Manages all active WebSocket connections across the pulse service instance.
    Thread-safe via asyncio.Lock.
    Enforces MAX_CONNECTIONS per instance.
    """
    MAX_CONNECTIONS = 500

    def __init__(self):
        self._connections: dict[str, ConnectionState] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        connection_id: str,
        websocket: WebSocket,
        session_token: str,
    ) -> bool:
        """
        Register a new WebSocket connection.
        Returns False if at connection limit. Never raises.
        """
        async with self._lock:
            if len(self._connections) >= self.MAX_CONNECTIONS:
                logger.warning(
                    "ws_connection_limit_reached",
                    extra={"active": len(self._connections), "max": self.MAX_CONNECTIONS},
                )
                return False
            self._connections[connection_id] = ConnectionState(
                websocket=websocket,
                session_token=session_token,
            )
            logger.info(
                "ws_connected",
                extra={
                    "connection_id": connection_id,
                    "session_token": session_token[:8],
                    "active": len(self._connections),
                },
            )
            return True

    async def disconnect(self, connection_id: str):
        """Remove a connection from the registry."""
        async with self._lock:
            state = self._connections.pop(connection_id, None)
            if state:
                logger.info(
                    "ws_disconnected",
                    extra={
                        "connection_id": connection_id,
                        "active": len(self._connections),
                    },
                )

    async def update_filters(self, connection_id: str, filters: dict):
        """Update the subscription filters for a connection."""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].filters = filters

    async def update_last_ping(self, connection_id: str):
        """Update last_ping timestamp for heartbeat tracking."""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].last_ping = datetime.now(timezone.utc)

    async def broadcast_to_subscribers(
        self,
        event_type: str,
        data: dict,
        filter_key: Optional[str] = None,
        filter_value: Optional[str] = None,
        _ws_delivery_histogram=None,
    ):
        """
        Send to all connections whose filters match.
        If no filter set on the connection: send to all.
        Never raises on individual send failure — disconnects the failing connection.
        """
        # Snapshot targets outside the lock
        async with self._lock:
            targets = list(self._connections.items())

        payload = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        dead_connections = []

        for conn_id, state in targets:
            # Filter matching logic
            if filter_key and filter_value:
                conn_filters = state.filters
                # If the client has a filter for this key but a different value, skip
                if filter_key in conn_filters and conn_filters.get(filter_key) != filter_value:
                    continue

            try:
                start = time.monotonic()
                await state.websocket.send_json(payload)
                latency_ms = (time.monotonic() - start) * 1000

                # Record delivery latency if histogram provided
                if _ws_delivery_histogram is not None:
                    try:
                        _ws_delivery_histogram.record(
                            latency_ms,
                            {"event_type": event_type},
                        )
                    except Exception:
                        pass  # metric recording never crashes broadcast
            except Exception:
                dead_connections.append(conn_id)

        # Prune dead connections
        for conn_id in dead_connections:
            await self.disconnect(conn_id)

    async def get_connection_states(self) -> list[tuple[str, ConnectionState]]:
        """Return snapshot of all connection states (for heartbeat)."""
        async with self._lock:
            return list(self._connections.items())

    @property
    def active_count(self) -> int:
        return len(self._connections)

    def get_stats(self) -> dict:
        """Return connection statistics for health endpoints."""
        return {
            "websocket_connections_active": len(self._connections),
            "websocket_max_connections": self.MAX_CONNECTIONS,
            "websocket_enabled": True,
        }


# ── Global singleton ─────────────────────────────────────────────────────────
_manager: Optional[WebSocketConnectionManager] = None


def get_ws_manager() -> WebSocketConnectionManager:
    """Get or create the global WebSocket connection manager."""
    global _manager
    if _manager is None:
        _manager = WebSocketConnectionManager()
    return _manager
