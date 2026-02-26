"""
Distributed Token Bucket Rate Limiter
=======================================
Redis-backed per-client-IP rate limiting middleware.

Algorithm: Token Bucket via atomic Lua script (INCR + EXPIRE).
Fail-open: If Redis is unavailable, all requests pass through with
           X-Rate-Limit-Status: degraded header.

Phase 2 — QuantSight Cloud Stabilization
"""

import json
import logging
import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Lua script for atomic token bucket check.
# KEYS[1] = bucket key (e.g., "rl:<ip>:<bucket>")
# ARGV[1] = max tokens (limit)
# ARGV[2] = window in seconds (TTL)
#
# Returns: number of requests made in current window (AFTER increment).
# If result > limit → reject.
_TOKEN_BUCKET_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return current
"""

# Paths that are NEVER rate-limited
_BYPASS_PATHS = frozenset({
    "/healthz",
    "/readyz",
    "/health/deps",
    "/health",
    "/",
    "/favicon.ico",
    "/manifest.json",
})


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For from Cloud Run load balancer."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in chain is the original client
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _is_admin_route(path: str) -> bool:
    """Check if the path is a Vanguard admin route (tighter bucket)."""
    return path.startswith("/vanguard/admin")


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Distributed rate limiter using Redis Token Bucket.

    Buckets:
      - Default:  60 requests per 60 seconds per client IP
      - Admin:    30 requests per 60 seconds per client IP

    Fail-open: If Redis is unavailable, requests pass through with
               X-Rate-Limit-Status: degraded header injected.
    """

    def __init__(
        self,
        app,
        default_limit: int = 60,
        default_window: int = 60,
        admin_limit: int = 30,
        admin_window: int = 60,
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        self.admin_limit = admin_limit
        self.admin_window = admin_window
        self._lua_sha: Optional[str] = None

    async def _get_lua_sha(self, redis_client) -> str:
        """Load and cache the Lua script SHA on the Redis server."""
        if self._lua_sha is None:
            self._lua_sha = await redis_client.script_load(_TOKEN_BUCKET_LUA)
        return self._lua_sha

    async def _check_rate_limit(self, client_ip: str, is_admin: bool) -> Optional[dict]:
        """
        Check rate limit against Redis.

        Returns None if Redis unavailable (fail open).
        Returns dict with {allowed: bool, current: int, limit: int, window: int} otherwise.
        """
        try:
            from vanguard.bootstrap.redis_client import get_redis_or_none

            redis_client = await get_redis_or_none()
            if redis_client is None:
                return None  # Fail open

            limit = self.admin_limit if is_admin else self.default_limit
            window = self.admin_window if is_admin else self.default_window
            bucket = "admin" if is_admin else "default"
            key = f"rl:{client_ip}:{bucket}"

            lua_sha = await self._get_lua_sha(redis_client)

            try:
                current = await redis_client.evalsha(lua_sha, 1, key, str(limit), str(window))
            except Exception:
                # Script may have been flushed (Redis restart) — reload
                self._lua_sha = None
                lua_sha = await self._get_lua_sha(redis_client)
                current = await redis_client.evalsha(lua_sha, 1, key, str(limit), str(window))

            return {
                "allowed": int(current) <= limit,
                "current": int(current),
                "limit": limit,
                "window": window,
                "remaining": max(0, limit - int(current)),
            }

        except Exception as e:
            logger.warning(f"Rate limiter Redis error (failing open): {e}")
            return None  # Fail open

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for bypassed paths
        if request.url.path in _BYPASS_PATHS:
            return await call_next(request)

        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        client_ip = _get_client_ip(request)
        is_admin = _is_admin_route(request.url.path)

        result = await self._check_rate_limit(client_ip, is_admin)

        # Fail open: Redis unavailable
        if result is None:
            response = await call_next(request)
            response.headers["X-Rate-Limit-Status"] = "degraded"
            return response

        # Inject rate limit headers on all responses
        if result["allowed"]:
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(result["limit"])
            response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
            response.headers["X-RateLimit-Window"] = str(result["window"])
            return response

        # Rate limit exceeded → 429
        retry_after = result["window"]

        # Structured JSON log for 429 events
        logger.warning(json.dumps({
            "event": "rate_limit_exceeded",
            "client_ip": client_ip,
            "path": request.url.path,
            "method": request.method,
            "bucket": "admin" if is_admin else "default",
            "current": result["current"],
            "limit": result["limit"],
            "window": result["window"],
        }))

        return JSONResponse(
            status_code=429,
            content={
                "error": "Too Many Requests",
                "retry_after": retry_after,
                "limit": result["limit"],
                "window": result["window"],
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(result["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Window": str(result["window"]),
            },
        )
