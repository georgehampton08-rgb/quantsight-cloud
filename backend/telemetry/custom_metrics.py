"""
Custom Metrics — Phase 8 Step 8.5.4
======================================
OpenTelemetry custom metrics for WebSocket SLO monitoring.

Metrics:
  quantsight.ws.delivery_latency_ms — Histogram of WebSocket message delivery latency
  quantsight.ws.connections_active   — Gauge of active WebSocket connections
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level metric instruments
_ws_delivery_histogram = None
_ws_connections_gauge = None
_initialized = False


def _init_metrics():
    """Initialize OTel metric instruments. Idempotent."""
    global _ws_delivery_histogram, _ws_connections_gauge, _initialized

    if _initialized:
        return

    _initialized = True

    try:
        from opentelemetry import metrics

        meter = metrics.get_meter("quantsight.ws", "1.0.0")

        _ws_delivery_histogram = meter.create_histogram(
            name="quantsight.ws.delivery_latency_ms",
            description="WebSocket message delivery latency from broadcast to send",
            unit="ms",
        )

        _ws_connections_gauge = meter.create_up_down_counter(
            name="quantsight.ws.connections_active",
            description="Number of active WebSocket connections",
            unit="1",
        )

        logger.info("WS custom metrics initialized")

    except ImportError:
        logger.debug("OTel metrics not available — WS metrics disabled")
    except Exception as e:
        logger.debug(f"WS metrics init failed: {e}")


def get_ws_delivery_histogram():
    """Get the WebSocket delivery latency histogram (lazy init)."""
    _init_metrics()
    return _ws_delivery_histogram


def get_ws_connections_gauge():
    """Get the WebSocket connections gauge (lazy init)."""
    _init_metrics()
    return _ws_connections_gauge
