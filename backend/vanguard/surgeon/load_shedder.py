"""
Load Shedding Governor — Phase 4 Step 4.6
===========================================
Protects the container from OOM kills under burst load.

Behavior:
  - Background loop (10s interval) checks container memory via psutil
  - Hysteresis thresholds:
      90% memory → SHEDDING_ACTIVE = True
      75% memory → SHEDDING_ACTIVE = False (recovery)
  - When SHEDDING_ACTIVE:
      - All non-critical POST requests return 429 Too Many Requests
        with Retry-After: 30
      - Critical paths exempt: GET requests, /healthz, /readyz,
        /health/deps, /vanguard/admin/*, /live/stream SSE
  - On activation: post Vanguard incident
    (type=LOAD_SHEDDING_ACTIVATED, severity=RED, memory_pct=float)
  - Optional webhook alert (ALERT_WEBHOOK_URL env var)

Feature flag gate:
  Only activates when Vanguard mode is CIRCUIT_BREAKER or FULL_SOVEREIGN
  AND FEATURE_LOAD_SHEDDER=true.
"""

import asyncio
import os
import time
from typing import Optional
from datetime import datetime, timezone

from ..utils.logger import get_logger
from ..core.config import get_vanguard_config, VanguardMode

logger = get_logger(__name__)

# ── Thresholds (hysteresis) ──────────────────────────────────────────────────
SHEDDING_THRESHOLD_HIGH = 90   # percent → activate shedding
SHEDDING_THRESHOLD_LOW = 75    # percent → deactivate shedding (recovery)
CHECK_INTERVAL_S = 10          # background loop interval

# ── Exempt paths (never shed) ────────────────────────────────────────────────
_EXEMPT_EXACT: frozenset = frozenset({
    "/healthz",
    "/readyz",
    "/health",
    "/health/deps",
})

_EXEMPT_PREFIXES: tuple = (
    "/vanguard/",
    "/admin/",
    "/live/",     # SSE stream
)


def _is_exempt_from_shedding(path: str, method: str) -> bool:
    """Return True if this request should never be shed."""
    # All GET requests are exempt
    if method == "GET":
        return True
    if path in _EXEMPT_EXACT:
        return True
    for prefix in _EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class LoadSheddingGovernor:
    """
    Memory-pressure based load shedding with hysteresis.

    Reads psutil.virtual_memory().percent on a background loop.
    DegradedInjectorMiddleware reads SHEDDING_ACTIVE to inject
    X-System-Status: load-shedding header.
    """

    def __init__(self):
        self.SHEDDING_ACTIVE: bool = False
        self._memory_pct: float = 0.0
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False

    def start(self) -> None:
        """Start the background monitoring loop."""
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._monitor_loop())
            logger.info("load_shedder_started",
                        high_threshold=SHEDDING_THRESHOLD_HIGH,
                        low_threshold=SHEDDING_THRESHOLD_LOW)
        except RuntimeError:
            logger.warning("load_shedder_no_event_loop")

    def stop(self) -> None:
        """Stop the background monitoring loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("load_shedder_stopped")

    def should_shed(self, path: str, method: str) -> bool:
        """
        Check if a request should be shed.
        Called by SurgeonMiddleware on every request.
        """
        if not self.SHEDDING_ACTIVE:
            return False
        if _is_exempt_from_shedding(path, method):
            return False
        return True

    @property
    def memory_pct(self) -> float:
        """Current memory utilization percentage (best-effort, non-blocking)."""
        return self._memory_pct

    async def _monitor_loop(self) -> None:
        """Background loop that checks memory and toggles SHEDDING_ACTIVE."""
        while self._running:
            try:
                await asyncio.sleep(CHECK_INTERVAL_S)
                self._memory_pct = self._read_memory_pct()

                if not self.SHEDDING_ACTIVE and self._memory_pct >= SHEDDING_THRESHOLD_HIGH:
                    self.SHEDDING_ACTIVE = True
                    logger.error(
                        "load_shedding_ACTIVATED",
                        memory_pct=round(self._memory_pct, 1),
                        threshold=SHEDDING_THRESHOLD_HIGH,
                    )
                    await self._post_incident(self._memory_pct)
                    await self._send_webhook_alert(self._memory_pct)

                elif self.SHEDDING_ACTIVE and self._memory_pct <= SHEDDING_THRESHOLD_LOW:
                    self.SHEDDING_ACTIVE = False
                    logger.info(
                        "load_shedding_DEACTIVATED",
                        memory_pct=round(self._memory_pct, 1),
                        threshold=SHEDDING_THRESHOLD_LOW,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("load_shedder_error", error=str(e))

    @staticmethod
    def _read_memory_pct() -> float:
        """Read current memory utilization. Falls back to 0.0 if psutil unavailable."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            logger.debug("psutil_not_available")
            return 0.0
        except Exception as e:
            logger.error("memory_read_failed", error=str(e))
            return 0.0

    async def _post_incident(self, memory_pct: float) -> None:
        """Post a Vanguard incident for load shedding activation."""
        try:
            from ..archivist.storage import get_incident_storage
            from ..inquisitor.fingerprint import generate_error_fingerprint

            storage = get_incident_storage()
            fingerprint = generate_error_fingerprint(
                exception_type="LOAD_SHEDDING_ACTIVATED",
                traceback_lines=[f"Memory at {memory_pct:.1f}%"],
                endpoint="system/memory",
            )

            incident = {
                "fingerprint": fingerprint,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "RED",
                "status": "ACTIVE",
                "error_type": "LOAD_SHEDDING_ACTIVATED",
                "error_message": f"Memory pressure at {memory_pct:.1f}% — shedding active",
                "endpoint": "system/memory",
                "request_id": "surgeon-load-shedder",
                "traceback": None,
                "context_vector": {"memory_pct": round(memory_pct, 1)},
                "remediation_log": [],
                "resolved_at": None,
            }
            await storage.store(incident)
            logger.info("load_shedding_incident_posted", memory_pct=round(memory_pct, 1))
        except Exception as e:
            logger.error("load_shedding_incident_failed", error=str(e))

    async def _send_webhook_alert(self, memory_pct: float) -> None:
        """Send alert to Slack/PagerDuty webhook if configured."""
        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if not webhook_url:
            logger.info("load_shedding_no_webhook_url")
            return

        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(webhook_url, json={
                    "text": f"🚨 QuantSight Load Shedding ACTIVATED — Memory at {memory_pct:.1f}%",
                    "severity": "critical",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            logger.info("load_shedding_webhook_sent", url=webhook_url)
        except Exception as e:
            logger.error("load_shedding_webhook_failed", error=str(e))


# ── Singleton ────────────────────────────────────────────────────────────────
_governor: Optional[LoadSheddingGovernor] = None


def get_load_shedder() -> LoadSheddingGovernor:
    """Get or create the global LoadSheddingGovernor singleton."""
    global _governor
    if _governor is None:
        _governor = LoadSheddingGovernor()
    return _governor
