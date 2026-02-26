"""
Custom Span Helpers — Phase 7 Step 7.3
========================================
Async context manager for custom spans on critical paths
that FastAPIInstrumentor cannot instrument automatically.

Span naming convention: {service}.{subsystem}.{operation}
  e.g., pulse.producer.cycle, vanguard.ai.analyze, firestore.query

Rules:
  - Never add PII to span attributes (no player names, user IDs, IPs)
  - Never add auth tokens or API keys
  - Spans must not add > 0.5ms overhead per operation
  - All spans use traced() — never raw start_as_current_span

Usage:
    async with traced("pulse.nba_api.fetch", {"endpoint": "scoreboard"}):
        data = await fetch_scoreboard()
"""

from contextlib import asynccontextmanager, contextmanager
from typing import Any, Optional

try:
    from opentelemetry import trace
    tracer = trace.get_tracer("quantsight")
    _OTEL_OK = True
except ImportError:
    tracer = None
    _OTEL_OK = False


@asynccontextmanager
async def traced(
    span_name: str,
    attributes: Optional[dict[str, Any]] = None,
):
    """
    Async context manager for custom spans.
    Never raises — span errors are recorded but re-raised.

    Usage:
        async with traced("pulse.cycle", {"games": 5}):
            await do_work()
    """
    if not _OTEL_OK or tracer is None:
        yield None
        return

    with tracer.start_as_current_span(span_name) as span:
        if attributes:
            for k, v in attributes.items():
                try:
                    span.set_attribute(k, str(v))
                except Exception:
                    pass  # Never fail on attribute setting
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise


@contextmanager
def traced_sync(
    span_name: str,
    attributes: Optional[dict[str, Any]] = None,
):
    """
    Synchronous context manager for custom spans.
    Used for synchronous Firestore operations and circuit breaker transitions.
    """
    if not _OTEL_OK or tracer is None:
        yield None
        return

    with tracer.start_as_current_span(span_name) as span:
        if attributes:
            for k, v in attributes.items():
                try:
                    span.set_attribute(k, str(v))
                except Exception:
                    pass
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            raise


def record_event(span_name: str, attributes: Optional[dict[str, Any]] = None):
    """
    Record a point-in-time event span (e.g., circuit breaker state transition).
    Non-blocking, fire-and-forget.
    """
    try:
        span = tracer.start_span(span_name)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        span.end()
    except Exception:
        pass  # OTel events must never crash the service
