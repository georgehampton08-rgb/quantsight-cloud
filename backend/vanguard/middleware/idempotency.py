import hashlib
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone, timedelta

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response as StarletteResponse

logger = logging.getLogger(__name__)

# In-memory fallback cache (used when Redis is unavailable).
_IDEMPOTENCY_CACHE: Dict[str, Dict[str, Any]] = {}

# Redis key prefix for idempotency records
_REDIS_PREFIX = "idem:"


class IdempotencyCache:
    """
    Storage layer for idempotency records.

    Phase 2: Redis-first with native TTL expiration.
    Fallback: In-memory dictionary (container-local) when Redis is unavailable.
    """

    @classmethod
    async def _get_redis(cls):
        """Get Redis client, returning None if unavailable."""
        try:
            from vanguard.bootstrap.redis_client import get_redis_or_none
            return await get_redis_or_none()
        except Exception:
            return None

    @classmethod
    async def get(cls, key: str) -> Optional[Dict[str, Any]]:
        # Try Redis first
        redis_client = await cls._get_redis()
        if redis_client is not None:
            try:
                raw = await redis_client.get(f"{_REDIS_PREFIX}{key}")
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception as e:
                logger.debug(f"Redis idempotency GET failed, falling back to memory: {e}")

        # Fallback: in-memory
        record = _IDEMPOTENCY_CACHE.get(key)
        if not record:
            return None

        # Check TTL for in-memory records
        expires_at = record.get("expires_at")
        if expires_at and datetime.now(timezone.utc) > expires_at:
            del _IDEMPOTENCY_CACHE[key]
            return None

        return record

    @classmethod
    async def set(cls, key: str, value: Dict[str, Any], ttl_seconds: int = 86400) -> None:
        # Try Redis first (TTL handled natively by Redis)
        redis_client = await cls._get_redis()
        if redis_client is not None:
            try:
                # Store without expires_at (Redis manages TTL)
                await redis_client.set(f"{_REDIS_PREFIX}{key}", json.dumps(value, default=str), ex=ttl_seconds)
                return
            except Exception as e:
                logger.debug(f"Redis idempotency SET failed, falling back to memory: {e}")

        # Fallback: in-memory with manual TTL
        value["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        _IDEMPOTENCY_CACHE[key] = value

    @classmethod
    async def delete(cls, key: str) -> None:
        """Remove a key from both Redis and in-memory cache."""
        redis_client = await cls._get_redis()
        if redis_client is not None:
            try:
                await redis_client.delete(f"{_REDIS_PREFIX}{key}")
            except Exception:
                pass
        _IDEMPOTENCY_CACHE.pop(key, None)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Enforces idempotency for mutating requests (POST, PUT, PATCH, DELETE).
    Requires the `Idempotency-Key` header.
    Rejects concurrently executing `IN_FLIGHT` requests with `409 Conflict`.
    Returns cached `COMPLETED` responses if payloads match.
    """

    def __init__(self, app, bypass_paths: Optional[list] = None):
        super().__init__(app)
        self.bypass_paths = bypass_paths or ["/healthz", "/readyz", "/health/deps", "/"]

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Skip GET/OPTIONS or bypassed paths
        if request.method in ("GET", "OPTIONS", "HEAD"):
            return await call_next(request)

        if request.url.path in self.bypass_paths:
            return await call_next(request)

        # 2. Check for Idempotency-Key header
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # We don't strictly enforce it system-wide yet to avoid breaking legacy clients,
            # but log a warning. For STRICT enforcement, return 400 here.
            logger.warning(f"Mutating request to {request.url.path} missing Idempotency-Key header.")
            return await call_next(request)

        # 3. Read and hash request body (only for JSON/Form)
        content_type = request.headers.get("Content-Type", "")
        body_hash = "no_body"
        
        # We must read the body carefully to not consume the stream
        body = b""
        if "application/json" in content_type or "application/x-www-form-urlencoded" in content_type:
            try:
                body = await request.body()
                if body:
                    body_hash = hashlib.sha256(body).hexdigest()
            except Exception as e:
                logger.error(f"Failed to read request body for idempotency hashing: {e}")
                
            # Important: Reset the request body so downstream handlers can read it
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive

        # 4. Generate Document ID Cache Key
        cache_key = hashlib.sha256(f"{request.url.path}:{idempotency_key}".encode()).hexdigest()

        # 5. Check Cache
        cached_record = await IdempotencyCache.get(cache_key)

        if cached_record:
            status = cached_record.get("status")

            # Validate Body Hash matches to prevent key reuse attacks
            if cached_record.get("request_body_hash") != body_hash:
                return JSONResponse(
                    status_code=422,
                    content={"error": "Idempotency-Key reuse detected with different request payload."}
                )

            # State Machine Evaluation
            if status == "IN_FLIGHT":
                # Strict 409 rejection for concurrency retry storms
                return JSONResponse(
                    status_code=409,
                    content={"error": "Concurrent request IN_FLIGHT. Please backoff and retry."},
                    headers={"Retry-After": "2"}
                )

            elif status == "COMPLETED":
                # Return cached response (128KB limit managed on storage)
                cached_body_str = cached_record.get("response_body")
                response_code = cached_record.get("response_code", 200)
                
                # If body was stripped due to size > 128KB
                if cached_body_str == "__PAYLOAD_TOO_LARGE_FINGERPRINT_ONLY__":
                    return JSONResponse(
                        status_code=202,
                        content={"message": "Request previously completed via idempotency cache.", "original_status": response_code},
                        headers={"X-Idempotency-Status": "Replayed-Fingerprint"}
                    )
                
                # Standard Cached Replay
                try:
                    cached_body = json.loads(cached_body_str) if cached_body_str else {}
                    return JSONResponse(
                        status_code=response_code,
                        content=cached_body,
                        headers={"X-Idempotency-Status": "Replayed"}
                    )
                except json.JSONDecodeError:
                    return Response(
                        status_code=response_code,
                        content=cached_body_str.encode() if cached_body_str else b"",
                        headers={"X-Idempotency-Status": "Replayed"}
                    )

            elif status == "FAILED":
                # Only allow retry if cooldown has passed
                failed_at_str = cached_record.get("failed_at")
                if failed_at_str:
                    try:
                        failed_at = datetime.fromisoformat(failed_at_str)
                        if (datetime.now(timezone.utc) - failed_at).total_seconds() < 2:
                            return JSONResponse(
                                status_code=409,
                                content={"error": "Request failed recently. Cooldown active."},
                                headers={"Retry-After": "2"}
                            )
                    except ValueError:
                        pass
                
                # Cooldown passed, proceed to retry (overwrite IN_FLIGHT below)
                pass

        # 6. Mark as IN_FLIGHT
        await IdempotencyCache.set(cache_key, {
            "status": "IN_FLIGHT",
            "request_body_hash": body_hash,
            "started_at": datetime.now(timezone.utc).isoformat()
        })

        # 7. Execute Request Handler
        try:
            response = await call_next(request)
            
            # Post-execution formatting (FastAPI specific logic for streaming/reading responses)
            # To cache the response, we actually have to consume it if we want to store it.
            # In a true middleware, capturing the response body of a streaming response is complex.
            # For this Phase 1 Implementation, we will store the status code immediately,
            # and only attempt to capture simple JSON bodies if possible, otherwise we store a fingerprint.
            
            resp_body_str = ""
            if isinstance(response, JSONResponse) and hasattr(response, "body"):
                 resp_body_str = response.body.decode()
            
            # 128KB max cache limit
            if len(resp_body_str) > 128000:
                resp_body_str = "__PAYLOAD_TOO_LARGE_FINGERPRINT_ONLY__"

            # 8. Store COMPLETED State
            # We don't cache 400-level client errors by default to allow corrections, EXCEPT 409
            if 200 <= response.status_code < 300:
                await IdempotencyCache.set(cache_key, {
                    "status": "COMPLETED",
                    "request_body_hash": body_hash,
                    "response_code": response.status_code,
                    "response_body": resp_body_str,
                    "completed_at": datetime.now(timezone.utc).isoformat()
                })
            elif response.status_code >= 500:
                await IdempotencyCache.set(cache_key, {
                    "status": "FAILED",
                    "request_body_hash": body_hash,
                    "response_code": response.status_code,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "failure_fingerprint": f"HTTP_500_ERROR"
                })
            else:
                 # Clean up cache for 400 validations so they can retry smoothly
                 await IdempotencyCache.delete(cache_key)

            return response

        except Exception as e:
            # 9. Handle Hard Crash
            logger.error(f"Idempotency intercepted unhandled exception: {e}")
            await IdempotencyCache.set(cache_key, {
                "status": "FAILED",
                "request_body_hash": body_hash,
                "response_code": 500,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "failure_fingerprint": "UNHANDLED_EXCEPTION"
            })
            raise e
