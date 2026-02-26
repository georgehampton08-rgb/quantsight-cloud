"""
Failure Rate Tracker — Phase 4 Step 4.2
========================================
In-memory sliding window per endpoint path (60s window).

Tracks total_requests and failed_requests within the current window.
A "failure" is any 5xx response OR unhandled exception.
4xx responses are client errors and are NOT counted as failures.

Thread-safe via asyncio.Lock per endpoint slot.
Max tracked endpoints: 200 (evict LRU beyond limit).

Excluded routes (never tracked):
  /healthz, /readyz, /health, /health/deps, /vanguard/*, /admin/*

Usage:
    from vanguard.surgeon.failure_tracker import get_failure_tracker

    tracker = get_failure_tracker()
    tracker.record("/players/123", 200)   # success
    tracker.record("/players/123", 503)   # failure
    rate = tracker.get_failure_rate("/players/123")  # 0.5
"""

import asyncio
import time
from typing import Dict, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
WINDOW_SECONDS = 60       # sliding window duration
MAX_ENDPOINTS = 200       # evict LRU beyond this count

# Routes that must NEVER appear in the tracker.
# These are the blast-radius immune routes — Surgeon must not track or act on them.
_EXCLUDED_EXACT: frozenset = frozenset({
    "/healthz",
    "/readyz",
    "/health",
    "/health/deps",
})

_EXCLUDED_PREFIXES: tuple = (
    "/vanguard/",
    "/admin/",
)


def _is_excluded(path: str) -> bool:
    """Return True if this path must never be tracked."""
    if path in _EXCLUDED_EXACT:
        return True
    for prefix in _EXCLUDED_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _is_failure(status_code: int) -> bool:
    """Return True if this status code represents a system failure (5xx)."""
    return status_code >= 500


class _EndpointWindow:
    """Sliding window state for a single endpoint."""

    __slots__ = ("total", "failed", "window_start", "last_access", "lock")

    def __init__(self):
        self.total: int = 0
        self.failed: int = 0
        self.window_start: float = time.monotonic()
        self.last_access: float = self.window_start
        self.lock: asyncio.Lock = asyncio.Lock()

    def _maybe_reset(self, now: float) -> None:
        """If the window has expired, reset counters."""
        if now - self.window_start >= WINDOW_SECONDS:
            self.total = 0
            self.failed = 0
            self.window_start = now

    def record(self, is_failure: bool, now: float) -> None:
        """Record a request result within the current window."""
        self._maybe_reset(now)
        self.total += 1
        if is_failure:
            self.failed += 1
        self.last_access = now

    @property
    def failure_rate(self) -> float:
        """Return current failure rate (0.0 to 1.0). Returns 0.0 if no requests."""
        now = time.monotonic()
        self._maybe_reset(now)
        if self.total == 0:
            return 0.0
        return self.failed / self.total

    def reset(self) -> None:
        """Reset counters — used by HALF_OPEN probing."""
        self.total = 0
        self.failed = 0
        self.window_start = time.monotonic()


class FailureTracker:
    """
    Per-endpoint sliding window failure rate tracker.

    All public methods are async and hold a per-endpoint lock to ensure
    thread safety under concurrent requests.
    """

    def __init__(self):
        self._windows: Dict[str, _EndpointWindow] = {}
        self._global_lock = asyncio.Lock()  # protects _windows dict mutations

    async def record(self, endpoint: str, status_code: int) -> None:
        """
        Record a request outcome for an endpoint.

        Args:
            endpoint:    Request path (e.g. "/players/123")
            status_code: HTTP response status code
        """
        if _is_excluded(endpoint):
            return

        window = await self._get_or_create_window(endpoint)
        async with window.lock:
            window.record(_is_failure(status_code), time.monotonic())

    async def record_exception(self, endpoint: str) -> None:
        """
        Record an unhandled exception for an endpoint.
        Exceptions are always treated as failures regardless of status code.
        """
        if _is_excluded(endpoint):
            return

        window = await self._get_or_create_window(endpoint)
        async with window.lock:
            window.record(True, time.monotonic())

    async def get_failure_rate(self, endpoint: str) -> float:
        """
        Get the current failure rate for an endpoint.

        Returns:
            float between 0.0 (no failures) and 1.0 (all failures).
            Returns 0.0 if no data exists for this endpoint.
        """
        window = self._windows.get(endpoint)
        if window is None:
            return 0.0
        async with window.lock:
            return window.failure_rate

    async def get_request_count(self, endpoint: str) -> int:
        """
        Get total requests in the current window for an endpoint.
        Used by circuit breaker to enforce minimum request threshold.
        """
        window = self._windows.get(endpoint)
        if window is None:
            return 0
        async with window.lock:
            now = time.monotonic()
            window._maybe_reset(now)
            return window.total

    async def reset_endpoint(self, endpoint: str) -> None:
        """
        Reset failure tracking for an endpoint.
        Called when circuit transitions to HALF_OPEN for clean probe measurement.
        """
        window = self._windows.get(endpoint)
        if window is not None:
            async with window.lock:
                window.reset()
                logger.info("failure_tracker_reset", endpoint=endpoint)

    async def _get_or_create_window(self, endpoint: str) -> _EndpointWindow:
        """Get existing window or create a new one, enforcing LRU eviction."""
        if endpoint in self._windows:
            return self._windows[endpoint]

        async with self._global_lock:
            # Double-check after acquiring lock
            if endpoint in self._windows:
                return self._windows[endpoint]

            # Evict LRU if at capacity
            if len(self._windows) >= MAX_ENDPOINTS:
                self._evict_lru()

            window = _EndpointWindow()
            self._windows[endpoint] = window
            return window

    def _evict_lru(self) -> None:
        """Evict the least-recently-accessed endpoint."""
        if not self._windows:
            return
        lru_key = min(self._windows, key=lambda k: self._windows[k].last_access)
        del self._windows[lru_key]
        logger.debug("failure_tracker_evicted", endpoint=lru_key, total_tracked=len(self._windows))

    def get_all_rates(self) -> Dict[str, Dict]:
        """
        Snapshot of all tracked endpoints (for diagnostics / health endpoint).
        Non-async because it reads without locks (best-effort for admin display).
        """
        snapshot = {}
        now = time.monotonic()
        for endpoint, window in self._windows.items():
            # Read without lock — acceptable for diagnostic snapshot
            window._maybe_reset(now)
            snapshot[endpoint] = {
                "total": window.total,
                "failed": window.failed,
                "failure_rate": round(window.failure_rate, 4),
                "window_age_s": round(now - window.window_start, 1),
            }
        return snapshot


# ── Singleton ────────────────────────────────────────────────────────────────
_tracker: Optional[FailureTracker] = None


def get_failure_tracker() -> FailureTracker:
    """Get or create the global FailureTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = FailureTracker()
        logger.info("failure_tracker_initialized", max_endpoints=MAX_ENDPOINTS, window_s=WINDOW_SECONDS)
    return _tracker
