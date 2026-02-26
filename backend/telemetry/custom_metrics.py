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


# ────────────────────────────────────────────────────────────────────
# Phase 9 — ML Metrics
# ────────────────────────────────────────────────────────────────────
_ml_confidence_histogram = None
_ml_fallback_counter = None
_ml_aegis_mae_histogram = None
_ml_drift_gauge = None
_ml_initialized = False


def _init_ml_metrics():
    """Initialize ML-specific OTel metrics. Idempotent."""
    global _ml_confidence_histogram, _ml_fallback_counter
    global _ml_aegis_mae_histogram, _ml_drift_gauge, _ml_initialized

    if _ml_initialized:
        return

    _ml_initialized = True

    try:
        from opentelemetry import metrics

        meter = metrics.get_meter("quantsight.ml", "1.0.0")

        _ml_confidence_histogram = meter.create_histogram(
            name="quantsight.ml.classifier_confidence",
            description="ML incident classifier confidence score per prediction",
            unit="1",
        )

        _ml_fallback_counter = meter.create_counter(
            name="quantsight.ml.fallback_total",
            description="Number of times the system fell back from ML to heuristic or stub",
            unit="1",
        )

        _ml_aegis_mae_histogram = meter.create_histogram(
            name="quantsight.ml.aegis_prediction_mae",
            description="Mean Absolute Error for Aegis ML performance predictions",
            unit="1",
        )

        _ml_drift_gauge = meter.create_up_down_counter(
            name="quantsight.ml.drift_score",
            description="Feature/prediction drift score (0=no drift, 1=severe drift)",
            unit="1",
        )

        logger.info("ML custom metrics initialized")

    except ImportError:
        logger.debug("OTel metrics not available — ML metrics disabled")
    except Exception as e:
        logger.debug(f"ML metrics init failed: {e}")


def get_ml_confidence_histogram():
    """Get the ML classifier confidence histogram (lazy init)."""
    _init_ml_metrics()
    return _ml_confidence_histogram


def get_ml_fallback_counter():
    """Get the ML fallback counter (lazy init)."""
    _init_ml_metrics()
    return _ml_fallback_counter


def get_ml_aegis_mae_histogram():
    """Get the Aegis ML prediction MAE histogram (lazy init)."""
    _init_ml_metrics()
    return _ml_aegis_mae_histogram


def get_ml_drift_gauge():
    """Get the ML drift score gauge (lazy init)."""
    _init_ml_metrics()
    return _ml_drift_gauge
