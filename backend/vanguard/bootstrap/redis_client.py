"""
Redis Client Management — Phase 5 HA Upgrade
===============================================
Async Redis connection pool with:
  - 3-attempt retry on initial connect (1s exponential backoff)
  - Failover detection with Vanguard incident posting
  - Connection recovery mechanism
  - FAIL OPEN semantics (get_redis_or_none() never raises)
"""

import asyncio
from typing import Optional
import os
from datetime import datetime, timezone

import redis.asyncio as redis_async
from redis.asyncio import Redis, ConnectionPool

from ..core.config import get_vanguard_config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Global Redis client
_redis_client: Optional[Redis] = None
_redis_pool: Optional[ConnectionPool] = None

# ── HA Constants ─────────────────────────────────────────────────────────────
_CONNECT_MAX_RETRIES = 3
_CONNECT_BACKOFF_BASE_S = 1.0  # 1s → 2s → 4s
_failover_incident_posted = False
_last_healthy = True


async def get_redis() -> Redis:
    """
    Get or create the global Redis client.
    Uses connection pooling with retry logic on initial connect.
    """
    global _redis_client, _redis_pool
    
    if _redis_client is not None:
        return _redis_client
    
    config = get_vanguard_config()
    
    # Skip Redis if using default localhost on Cloud Run (no local Redis available)
    if 'localhost' in config.redis_url and os.getenv('K_SERVICE'):
        raise ConnectionError("Redis not available in Cloud Run (no REDIS_URL configured)")
    
    last_error = None

    for attempt in range(1, _CONNECT_MAX_RETRIES + 1):
        try:
            # Create connection pool
            _redis_pool = ConnectionPool.from_url(
                config.redis_url,
                max_connections=config.redis_max_connections,
                decode_responses=True,  # Auto-decode bytes to strings
            )
            
            # Create Redis client
            _redis_client = Redis(connection_pool=_redis_pool)
            
            # Test connection
            await _redis_client.ping()
            logger.info(
                "redis_connected",
                url=config.redis_url,
                attempt=attempt,
            )

            # If we recovered from a previous failure, post recovery incident
            await _post_failover_event(recovered=True)
            
            return _redis_client
        
        except Exception as e:
            last_error = e
            logger.warning(
                "redis_connect_retry",
                attempt=attempt,
                max_retries=_CONNECT_MAX_RETRIES,
                error=str(e),
            )
            # Clean up failed pool/client
            if _redis_client:
                try:
                    await _redis_client.aclose()
                except Exception:
                    pass
                _redis_client = None
            if _redis_pool:
                try:
                    await _redis_pool.aclose()
                except Exception:
                    pass
                _redis_pool = None

            if attempt < _CONNECT_MAX_RETRIES:
                backoff = _CONNECT_BACKOFF_BASE_S * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

    # All retries exhausted
    logger.error(
        "redis_connection_failed_all_retries",
        retries=_CONNECT_MAX_RETRIES,
        error=str(last_error),
        url=config.redis_url,
    )
    await _post_failover_event(recovered=False)
    raise last_error


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_client, _redis_pool
    
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("redis_connection_closed")
    
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


async def get_redis_or_none() -> Optional[Redis]:
    """
    Safe wrapper around get_redis().
    Returns the Redis client if available, None otherwise.
    Never raises — suitable for middleware and non-critical paths.
    """
    try:
        return await get_redis()
    except Exception:
        return None


async def ping_redis() -> bool:
    """
    Health check: Ping Redis.
    Returns True if healthy, False otherwise.
    Posts Vanguard incidents on state transitions (healthy → unhealthy, unhealthy → healthy).
    """
    global _last_healthy

    try:
        client = await get_redis()
        await client.ping()

        if not _last_healthy:
            # Transition: unhealthy → healthy
            logger.info("redis_recovered")
            await _post_failover_event(recovered=True)
        _last_healthy = True
        return True

    except Exception as e:
        if _last_healthy:
            # Transition: healthy → unhealthy (first failure after being healthy)
            logger.warning("redis_ping_failed", error=str(e))
            await _post_failover_event(recovered=False)
        _last_healthy = False

        # Attempt reconnect: clear stale client so next get_redis() retries
        global _redis_client, _redis_pool
        if _redis_client:
            try:
                await _redis_client.aclose()
            except Exception:
                pass
            _redis_client = None
        if _redis_pool:
            try:
                await _redis_pool.aclose()
            except Exception:
                pass
            _redis_pool = None

        return False


async def _post_failover_event(recovered: bool) -> None:
    """
    Post a Vanguard incident for Redis failover state transitions.
    Only posts on actual state changes (healthy→unhealthy or unhealthy→healthy).
    """
    global _failover_incident_posted

    try:
        # Avoid posting duplicate incidents
        if not recovered and _failover_incident_posted:
            return
        if recovered and not _failover_incident_posted:
            return  # No failure was posted, so no recovery to announce

        from ..archivist.storage import get_incident_storage

        storage = get_incident_storage()

        if recovered:
            incident = {
                "fingerprint": "redis-ha-failover-recovery",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "GREEN",
                "status": "resolved",
                "error_type": "REDIS_HA_RECOVERED",
                "error_message": "Redis connection recovered after failover",
                "endpoint": "system/redis",
                "request_id": "redis-ha-monitor",
                "traceback": None,
                "context_vector": {},
                "remediation_log": [],
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }
            _failover_incident_posted = False
            logger.info("redis_ha_recovery_incident_posted")
        else:
            incident = {
                "fingerprint": "redis-ha-failover-detected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "severity": "RED",
                "status": "ACTIVE",
                "error_type": "REDIS_HA_FAILOVER",
                "error_message": f"Redis connection failed after {_CONNECT_MAX_RETRIES} retries — operating in FAIL OPEN mode",
                "endpoint": "system/redis",
                "request_id": "redis-ha-monitor",
                "traceback": None,
                "context_vector": {"max_retries": _CONNECT_MAX_RETRIES},
                "remediation_log": [],
                "resolved_at": None,
            }
            _failover_incident_posted = True
            logger.warning("redis_ha_failover_incident_posted")

        await storage.store(incident)

    except Exception as e:
        # Incident posting NEVER crashes the Redis client
        logger.error(f"Redis HA incident post failed: {e}")

