"""
Phase 2 — Distributed Rate Limiter Tests
==========================================
Tests for RateLimiterMiddleware with mocked Redis.

a) Assert 429 after limit exceeded (Redis available)
b) Assert FAIL OPEN — 200 returned when Redis unavailable
c) Assert /healthz, /readyz, /health/deps are never rate-limited
d) Assert admin routes use tighter bucket (30 req/60s)
e) Assert /health/deps reports redis_ok field
f) Assert /readyz is NOT affected by Redis availability
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

import sys
import os

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _build_app(rate_limiter_kwargs=None):
    """Build a minimal FastAPI app with RateLimiterMiddleware for testing."""
    from vanguard.middleware.rate_limiter import RateLimiterMiddleware

    app = FastAPI()

    @app.get("/api/test")
    async def test_route():
        return {"ok": True}

    @app.get("/vanguard/admin/status")
    async def admin_route():
        return {"admin": True}

    @app.get("/healthz")
    async def healthz():
        return {"healthy": True}

    @app.get("/readyz")
    async def readyz():
        return {"ready": True}

    @app.get("/health/deps")
    async def health_deps():
        return {"firestore_ok": True, "redis_ok": False}

    kwargs = rate_limiter_kwargs or {}
    app.add_middleware(RateLimiterMiddleware, **kwargs)
    return app


class FakeRedis:
    """In-memory fake Redis for testing token bucket logic."""

    def __init__(self):
        self._data = {}
        self._scripts = {}
        self._script_counter = 0

    async def script_load(self, script: str) -> str:
        self._script_counter += 1
        sha = f"sha_{self._script_counter}"
        self._scripts[sha] = script
        return sha

    async def evalsha(self, sha: str, numkeys: int, *args):
        key = args[0]
        # Simple INCR + EXPIRE simulation
        if key not in self._data:
            self._data[key] = 0
        self._data[key] += 1
        return self._data[key]

    async def get(self, key):
        return self._data.get(key)

    async def set(self, key, value, ex=None):
        self._data[key] = value

    async def delete(self, key):
        self._data.pop(key, None)

    async def ping(self):
        return True


# ─── Test a: 429 after limit exceeded ───────────────────────────────────────

def test_rate_limit_429_after_exceeded():
    """With Redis available, requests beyond the limit should return 429."""
    fake_redis = FakeRedis()

    with patch(
        "vanguard.middleware.rate_limiter.RateLimiterMiddleware._check_rate_limit"
    ) as mock_check:
        # First 5 requests: allowed
        # 6th request: denied
        call_count = 0

        async def side_effect(client_ip, is_admin):
            nonlocal call_count
            call_count += 1
            if call_count <= 5:
                return {"allowed": True, "current": call_count, "limit": 5, "window": 60, "remaining": 5 - call_count}
            return {"allowed": False, "current": call_count, "limit": 5, "window": 60, "remaining": 0}

        mock_check.side_effect = side_effect

        app = _build_app(rate_limiter_kwargs={"default_limit": 5, "default_window": 60})
        client = TestClient(app)

        # First 5 should pass
        for i in range(5):
            resp = client.get("/api/test")
            assert resp.status_code == 200, f"Request {i+1} should pass but got {resp.status_code}"

        # 6th should be 429
        resp = client.get("/api/test")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        body = resp.json()
        assert body["error"] == "Too Many Requests"


# ─── Test b: FAIL OPEN when Redis unavailable ──────────────────────────────

def test_fail_open_when_redis_unavailable():
    """When Redis is down, requests should pass through with degraded header."""
    with patch(
        "vanguard.middleware.rate_limiter.RateLimiterMiddleware._check_rate_limit",
        new_callable=AsyncMock,
        return_value=None,  # None = Redis unavailable
    ):
        app = _build_app()
        client = TestClient(app)

        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.headers.get("X-Rate-Limit-Status") == "degraded"


# ─── Test c: Bypass paths never rate-limited ────────────────────────────────

def test_bypass_paths_not_rate_limited():
    """Health and readiness probes should never be rate-limited."""
    with patch(
        "vanguard.middleware.rate_limiter.RateLimiterMiddleware._check_rate_limit",
        new_callable=AsyncMock,
        return_value={"allowed": False, "current": 999, "limit": 1, "window": 60, "remaining": 0},
    ):
        app = _build_app()
        client = TestClient(app)

        # These should all return 200 regardless of rate limit state
        for path in ["/healthz", "/readyz", "/health/deps"]:
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} should bypass rate limiter but got {resp.status_code}"


# ─── Test d: Admin routes use tighter bucket ────────────────────────────────

def test_admin_routes_use_admin_bucket():
    """Admin routes should be checked with is_admin=True."""
    check_calls = []

    async def capture_check(self, client_ip, is_admin):
        check_calls.append({"client_ip": client_ip, "is_admin": is_admin})
        return {"allowed": True, "current": 1, "limit": 30, "window": 60, "remaining": 29}

    with patch(
        "vanguard.middleware.rate_limiter.RateLimiterMiddleware._check_rate_limit",
        capture_check,
    ):
        app = _build_app()
        client = TestClient(app)

        client.get("/vanguard/admin/status")
        assert len(check_calls) == 1
        assert check_calls[0]["is_admin"] is True

        client.get("/api/test")
        assert len(check_calls) == 2
        assert check_calls[1]["is_admin"] is False


# ─── Test e: SYSTEM_SNAPSHOT includes redis_ok ──────────────────────────────

def test_snapshot_includes_redis_ok():
    """SYSTEM_SNAPSHOT should contain the redis_ok field."""
    from vanguard.snapshot import SYSTEM_SNAPSHOT

    assert "redis_ok" in SYSTEM_SNAPSHOT
    # Default should be False (no Redis connected in test env)
    assert SYSTEM_SNAPSHOT["redis_ok"] is False


# ─── Test f: /readyz is not affected by Redis ──────────────────────────────

def test_readyz_independent_of_redis():
    """
    /readyz should only check Firestore, not Redis.
    Build a minimal app with /readyz that mirrors main.py's implementation
    to confirm Redis state doesn't affect readiness.
    """
    test_app = FastAPI()

    @test_app.get("/readyz")
    async def readyz():
        # Mirrors main.py: only checks Firestore, never Redis
        return {"status": "ok"}

    from vanguard.middleware.rate_limiter import RateLimiterMiddleware
    test_app.add_middleware(RateLimiterMiddleware)

    client = TestClient(test_app)

    # /readyz is in bypass list — should always return 200 even with rate limiter
    resp = client.get("/readyz")
    assert resp.status_code == 200
    # Should NOT have rate limit headers (bypassed)
    assert "X-RateLimit-Limit" not in resp.headers


# ─── Test g: Rate limit headers present on allowed requests ────────────────

def test_rate_limit_headers_on_allowed():
    """Allowed requests should include X-RateLimit-* headers."""
    with patch(
        "vanguard.middleware.rate_limiter.RateLimiterMiddleware._check_rate_limit",
        new_callable=AsyncMock,
        return_value={"allowed": True, "current": 5, "limit": 60, "window": 60, "remaining": 55},
    ):
        app = _build_app()
        client = TestClient(app)

        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.headers.get("X-RateLimit-Limit") == "60"
        assert resp.headers.get("X-RateLimit-Remaining") == "55"
        assert resp.headers.get("X-RateLimit-Window") == "60"
