"""
Redis Client Management
========================
Async Redis connection pool with health checks.
"""

from typing import Optional
import os
import redis.asyncio as redis_async
from redis.asyncio import Redis, ConnectionPool

from ..core.config import get_vanguard_config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Global Redis client
_redis_client: Optional[Redis] = None
_redis_pool: Optional[ConnectionPool] = None


async def get_redis() -> Redis:
    """
    Get or create the global Redis client.
    Uses connection pooling for efficiency.
    """
    global _redis_client, _redis_pool
    
    if _redis_client is not None:
        return _redis_client
    
    config = get_vanguard_config()
    
    # Skip Redis if using default localhost on Cloud Run (no local Redis available)
    if 'localhost' in config.redis_url and os.getenv('K_SERVICE'):
        raise ConnectionError("Redis not available in Cloud Run (no REDIS_URL configured)")
    
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
        logger.info("redis_connected", url=config.redis_url)
        
        return _redis_client
    
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e), url=config.redis_url)
        raise


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
    """
    try:
        client = await get_redis()
        await client.ping()
        return True
    except Exception as e:
        # Only log warning once, not every 30s health check cycle
        if not getattr(ping_redis, '_warned', False):
            logger.warning("redis_ping_failed", error=str(e))
            ping_redis._warned = True
        return False
