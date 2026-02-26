"""
Pulse Service Isolation — Phase 5 Step 5.4
=============================================
Unified facade for all pulse-related components. This module provides
a single, clean import boundary for the entire pulse subsystem.

The isolation enables:
  1. Feature-flag gating (PULSE_SERVICE_ENABLED)
  2. Independent deployment readiness (future microservice split)
  3. Blast-radius containment (pulse failures don't cascade to core API)
  4. Clean lifecycle management (start/stop in one place)

Components managed:
  - CloudAsyncPulseProducer (NBA API → Firestore writer)
  - PulseStatsArchiver (quarter-end stat snapshots)
  - Live Stream Routes (SSE + REST endpoints)

Usage in main.py:
  from services.pulse_service import PulseServiceFacade
  pulse = PulseServiceFacade()
  await pulse.start()    # startup
  await pulse.stop()     # shutdown
  pulse.is_healthy()     # health check
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── Feature Flag ─────────────────────────────────────────────────────────────
PULSE_SERVICE_ENABLED = os.getenv("PULSE_SERVICE_ENABLED", "true").lower() == "true"


class PulseServiceFacade:
    """
    Facade for the entire pulse subsystem.
    Manages lifecycle, health, and provides a clean API boundary.
    """

    def __init__(self):
        self._producer = None
        self._archiver = None
        self._started = False
        self._start_time: Optional[datetime] = None
        self._error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return PULSE_SERVICE_ENABLED

    async def start(self) -> bool:
        """
        Start all pulse components.
        Returns True if started successfully, False otherwise.
        Safe to call multiple times (idempotent).
        """
        if not self.enabled:
            logger.info("pulse_service_disabled", reason="PULSE_SERVICE_ENABLED=false")
            return False

        if self._started:
            return True

        try:
            # 1. Start the producer
            from services.async_pulse_producer_cloud import (
                start_cloud_producer,
                get_cloud_producer,
            )
            await start_cloud_producer()
            self._producer = get_cloud_producer()

            # 2. Initialize the archiver (already done by producer, just grab ref)
            try:
                from services.pulse_stats_archiver import get_pulse_archiver
                self._archiver = get_pulse_archiver()
            except ImportError:
                logger.warning("pulse_archiver_not_available")

            self._started = True
            self._start_time = datetime.now(timezone.utc)
            self._error = None
            logger.info("pulse_service_started")
            return True

        except Exception as e:
            self._error = str(e)
            logger.error(f"pulse_service_start_failed: {e}")
            return False

    async def stop(self) -> None:
        """Stop all pulse components."""
        if not self._started:
            return

        try:
            from services.async_pulse_producer_cloud import stop_cloud_producer
            await stop_cloud_producer()
            logger.info("pulse_service_stopped")
        except Exception as e:
            logger.error(f"pulse_service_stop_failed: {e}")
        finally:
            self._started = False
            self._producer = None

    def is_healthy(self) -> bool:
        """Check if the pulse service is running and producing data."""
        if not self.enabled or not self._started:
            return False

        if self._producer is None:
            return False

        status = self._producer.get_status()
        return status.get("running", False)

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive pulse service status for /live/status and health checks."""
        if not self.enabled:
            return {
                "status": "disabled",
                "enabled": False,
                "reason": "PULSE_SERVICE_ENABLED=false",
            }

        if not self._started:
            return {
                "status": "not_started",
                "enabled": True,
                "error": self._error,
            }

        producer_status = {}
        if self._producer:
            producer_status = self._producer.get_status()

        return {
            "status": "operational" if self.is_healthy() else "degraded",
            "enabled": True,
            "started": self._started,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._start_time).total_seconds()
                if self._start_time else 0
            ),
            "producer": producer_status,
            "archiver_available": self._archiver is not None,
        }

    def get_producer(self):
        """Get the underlying producer instance (for live_stream_routes)."""
        return self._producer


# ── Singleton ────────────────────────────────────────────────────────────────
_pulse_service: Optional[PulseServiceFacade] = None


def get_pulse_service() -> PulseServiceFacade:
    """Get or create the global pulse service facade."""
    global _pulse_service
    if _pulse_service is None:
        _pulse_service = PulseServiceFacade()
    return _pulse_service
