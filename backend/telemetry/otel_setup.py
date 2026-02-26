"""
OpenTelemetry Setup — Phase 7 Step 7.2
========================================
Shared instrumentation foundation for all QuantSight services.

OTEL_ENABLED env var gates instrumentation (default: true).
Falls back to ConsoleSpanExporter in local dev.
Never raises — failures are logged and ignored.

Usage:
    from telemetry.otel_setup import setup_telemetry
    provider = setup_telemetry(app, "quantsight-main")
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level result for health checks
_otel_ok: bool = False


def setup_telemetry(app, service_name: str) -> Optional[object]:
    """
    Initialize OpenTelemetry for a FastAPI service.

    - OTEL_ENABLED=false disables all instrumentation (default: true)
    - GOOGLE_CLOUD_PROJECT present → Cloud Trace exporter
    - No GOOGLE_CLOUD_PROJECT → Console exporter (local dev)
    - BatchSpanProcessor is NON-BLOCKING — never adds latency to requests
    - Excluded URLs: /healthz, /readyz (no tracing noise from probes)

    Returns the TracerProvider on success, None on failure.
    """
    global _otel_ok

    if not os.getenv("OTEL_ENABLED", "true").lower() == "true":
        logger.info("OTel disabled via OTEL_ENABLED=false")
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.getenv("GIT_SHA", os.getenv("K_REVISION", "unknown")),
            "deployment.environment": os.getenv("ENVIRONMENT", "production"),
        })

        provider = TracerProvider(resource=resource)

        # Cloud Trace in production, Console in local dev
        if os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                from opentelemetry.exporter.gcp.trace import CloudTraceSpanExporter
                exporter = CloudTraceSpanExporter(
                    project_id=os.getenv("GOOGLE_CLOUD_PROJECT")
                )
                logger.info(f"OTel: Using Cloud Trace exporter (project={os.getenv('GOOGLE_CLOUD_PROJECT')})")
            except ImportError:
                logger.warning("OTel: opentelemetry-exporter-gcp-trace not installed, falling back to console")
                exporter = ConsoleSpanExporter()
        else:
            exporter = ConsoleSpanExporter()
            logger.info("OTel: Using Console exporter (no GOOGLE_CLOUD_PROJECT)")

        # BatchSpanProcessor is NON-BLOCKING — never adds latency to requests
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Auto-instrument all FastAPI routes
        # Excluded URLs: health probes (no tracing noise)
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls="/healthz,/readyz,/health",
        )

        _otel_ok = True
        logger.info(f"OTel: Initialized for service={service_name}")
        return provider

    except Exception as e:
        # OTel failure must NEVER crash the service
        _otel_ok = False
        logger.warning(f"OTel setup failed: {e}. Continuing without tracing.")
        return None


def is_otel_ok() -> bool:
    """Check if OTel initialized successfully (for /health/deps)."""
    return _otel_ok
