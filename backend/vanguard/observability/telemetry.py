"""
OpenTelemetry Foundation — Phase 5 Step 5.3
==============================================
Minimal instrumentation layer for QuantSight Cloud.
Provides structured traces, metrics, and logging hooks
without requiring the full OTel SDK installed.

This module follows a "grow-into-it" pattern:
  - When opentelemetry-sdk IS installed → uses real OTel
  - When opentelemetry-sdk IS NOT installed → uses no-op stubs
  - Zero import failures either way

Traces are designed around the QuantSight request lifecycle:
  1. HTTP request → Middleware span
  2. AI triage → analysis span (with routing source: gemini vs heuristic)
  3. Surgeon remediation → remediation span
  4. Pulse producer → update cycle span

Usage:
    from vanguard.observability.telemetry import get_tracer, get_meter
    tracer = get_tracer("vanguard.inquisitor")
    with tracer.start_as_current_span("ai_triage") as span:
        span.set_attribute("triage.source", "heuristic")
        ...
"""

import logging
import os
from typing import Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ── Detect OTel SDK availability ─────────────────────────────────────────────
OTEL_AVAILABLE = False
OTEL_EXPORTER = os.getenv("OTEL_EXPORTER", "none")  # none | console | gcp

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    OTEL_AVAILABLE = True
    logger.info("otel_sdk_available", exporter=OTEL_EXPORTER)
except ImportError:
    logger.info("otel_sdk_not_installed — using no-op stubs")


# ── No-Op Stubs (when OTel SDK is not installed) ─────────────────────────────

class _NoOpSpan:
    """No-op span that silently accepts all calls."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, *args, **kwargs) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpTracer:
    """No-op tracer that returns no-op spans."""

    def start_as_current_span(self, name: str, **kwargs):
        return _NoOpSpan()

    def start_span(self, name: str, **kwargs):
        return _NoOpSpan()


class _NoOpCounter:
    def add(self, amount: int, attributes: Optional[dict] = None) -> None:
        pass


class _NoOpHistogram:
    def record(self, value: float, attributes: Optional[dict] = None) -> None:
        pass


class _NoOpMeter:
    """No-op meter that returns no-op instruments."""

    def create_counter(self, name: str, **kwargs):
        return _NoOpCounter()

    def create_histogram(self, name: str, **kwargs):
        return _NoOpHistogram()

    def create_up_down_counter(self, name: str, **kwargs):
        return _NoOpCounter()


# ── OTel Initialization ─────────────────────────────────────────────────────

_tracer_provider = None
_meter_provider = None
_initialized = False


def _initialize_otel() -> None:
    """Initialize OTel providers (only if SDK is available)."""
    global _tracer_provider, _meter_provider, _initialized

    if _initialized or not OTEL_AVAILABLE:
        return

    try:
        resource = Resource.create({
            "service.name": "quantsight-cloud",
            "service.version": os.getenv("K_REVISION", "local"),
            "deployment.environment": "production" if os.getenv("K_SERVICE") else "development",
        })

        # Tracer
        _tracer_provider = TracerProvider(resource=resource)

        # Add exporters based on config
        if OTEL_EXPORTER == "console":
            from opentelemetry.sdk.trace.export import (
                SimpleSpanProcessor,
                ConsoleSpanExporter,
            )
            _tracer_provider.add_span_processor(
                SimpleSpanProcessor(ConsoleSpanExporter())
            )
        elif OTEL_EXPORTER == "gcp":
            try:
                from opentelemetry.exporter.gcp.trace import CloudTraceSpanExporter
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                _tracer_provider.add_span_processor(
                    BatchSpanProcessor(CloudTraceSpanExporter())
                )
            except ImportError:
                logger.warning("GCP trace exporter not installed — falling back to no-op")

        trace.set_tracer_provider(_tracer_provider)

        # Meter
        _meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(_meter_provider)

        _initialized = True
        logger.info(
            "otel_initialized",
            exporter=OTEL_EXPORTER,
            service="quantsight-cloud",
        )

    except Exception as e:
        logger.error(f"otel_initialization_failed: {e}")


# ── Public API ───────────────────────────────────────────────────────────────

def get_tracer(name: str = "quantsight") -> Any:
    """
    Get a tracer. Returns real OTel tracer if SDK is available, no-op otherwise.
    """
    if OTEL_AVAILABLE:
        _initialize_otel()
        return trace.get_tracer(name)
    return _NoOpTracer()


def get_meter(name: str = "quantsight") -> Any:
    """
    Get a meter. Returns real OTel meter if SDK is available, no-op otherwise.
    """
    if OTEL_AVAILABLE:
        _initialize_otel()
        return metrics.get_meter(name)
    return _NoOpMeter()


# ── Pre-built Instruments ────────────────────────────────────────────────────
# These are the standard metrics that Vanguard subsystems should use.

_vanguard_meter = None


def _get_vanguard_meter():
    global _vanguard_meter
    if _vanguard_meter is None:
        _vanguard_meter = get_meter("vanguard")
    return _vanguard_meter


def get_request_duration_histogram():
    """Histogram for HTTP request durations."""
    return _get_vanguard_meter().create_histogram(
        name="http.server.duration",
        description="HTTP request duration in seconds",
        unit="s",
    )


def get_triage_counter():
    """Counter for AI triage executions by source (gemini vs heuristic)."""
    return _get_vanguard_meter().create_counter(
        name="vanguard.triage.executions",
        description="Number of AI triage executions",
    )


def get_incident_counter():
    """Counter for Vanguard incidents by severity."""
    return _get_vanguard_meter().create_counter(
        name="vanguard.incidents.created",
        description="Number of incidents created",
    )


def get_circuit_breaker_state():
    """Up/down counter for circuit breaker state changes."""
    return _get_vanguard_meter().create_up_down_counter(
        name="vanguard.circuit_breaker.state",
        description="Circuit breaker state transitions",
    )


async def shutdown_otel() -> None:
    """Gracefully shut down OTel providers."""
    global _tracer_provider, _meter_provider, _initialized

    if _tracer_provider:
        try:
            _tracer_provider.shutdown()
        except Exception:
            pass
    if _meter_provider:
        try:
            _meter_provider.shutdown()
        except Exception:
            pass

    _initialized = False
    logger.info("otel_shutdown_complete")
