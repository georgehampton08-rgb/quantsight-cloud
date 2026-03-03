"""
In-Process Sliding Window Rate Limiter
========================================
Replaces the broken Redis-backed limiter.

Why in-process instead of Redis?
  Redis is not reliably available in this Cloud Run config.
  The old limiter silently failed open — zero throttling was happening.
  This implementation actually works.

Algorithm: Sliding window using deque of request timestamps per IP.
  - O(n) cleanup per request, n = window size (small in practice)
  - asyncio-safe: event loop is single-threaded, no lock needed

Limits:
  Default public routes:  60 req / 60s per IP
  Admin routes (/admin/): 20 req / 60s per IP
  AI routes (/matchup/analyze, /ai/): 10 req / 60s per IP

Cloud Run consideration:
  With min-instances=1, one stable process handles all requests.
  Per-instance limiting = per-user limiting for this config.
  If scaling to multiple instances, upgrade to Redis or Memorystore.

Purge:
  Call _MEMORY_BUCKETS.clear() from the /admin/cache/purge endpoint
  to reset all rate limit windows.
"""

import time
import logging
from collections import deque, defaultdict
from typing import Dict, Deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Module-level bucket store ───────────────────────────────────────────────
# Exported so /admin/cache/purge can clear it.
# Structure: { "ip:bucket" -> deque([timestamp, ...]) }
_MEMORY_BUCKETS: Dict[str, Deque[float]] = defaultdict(deque)

# ── Route classification ─────────────────────────────────────────────────────
_BYPASS_PATHS = frozenset({
    "/healthz", "/readyz", "/health/deps", "/health",
    "/", "/favicon.ico", "/manifest.json",
})

_AI_PREFIXES = ("/matchup/analyze", "/ai/", "/vanguard/ai", "/stratos/")

_LIMITS = {
    "ai":     (10,  60),   # 10 req / 60s
    "admin":  (20,  60),   # 20 req / 60s
    "public": (60,  60),   # 60 req / 60s
}


def _classify(path: str) -> str:
    if any(path.startswith(p) for p in _AI_PREFIXES):
        return "ai"
    if path.startswith("/admin") or path.startswith("/vanguard/admin"):
        return "admin"
    return "public"


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _sliding_window_check(key: str, limit: int, window: int) -> tuple[bool, int, int]:
    """
    Returns (allowed, current_count, remaining).
    Evicts timestamps older than window seconds.
    """
    now = time.monotonic()
    bucket = _MEMORY_BUCKETS[key]

    # Evict expired entries from the left
    cutoff = now - window
    while bucket and bucket[0] < cutoff:
        bucket.popleft()

    current = len(bucket)

    if current >= limit:
        return False, current, 0

    # Record this request
    bucket.append(now)
    return True, current + 1, limit - (current + 1)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    In-process sliding window rate limiter.
    No Redis required. Actually enforces limits.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Never rate-limit bypass paths or CORS preflight
        if path in _BYPASS_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = _get_client_ip(request)
        bucket_type = _classify(path)
        limit, window = _LIMITS[bucket_type]
        key = f"{client_ip}:{bucket_type}"

        allowed, current, remaining = _sliding_window_check(key, limit, window)

        if not allowed:
            logger.warning(
                f"[RATE_LIMIT] 429 ip={client_ip} path={path} "
                f"bucket={bucket_type} current={current} limit={limit}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Limit: {limit} requests per {window}s",
                    "retry_after": window,
                },
                headers={
                    "Retry-After": str(window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Window": str(window),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(window)
        response.headers["X-RateLimit-Bucket"] = bucket_type
        return response
