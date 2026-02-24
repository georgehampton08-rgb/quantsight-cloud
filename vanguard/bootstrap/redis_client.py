"""
Redis Client Management
========================
Async Redis connection pool with health checks.
"""

from typing import Optional
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
    
    try:
        # Create connection pool with connect timeout
        _redis_pool = ConnectionPool.from_url(
            config.redis_url,
            max_connections=config.redis_max_connections,
            decode_responses=True,  # Auto-decode bytes to strings
            socket_connect_timeout=3,  # Fail fast if Redis unreachable
            socket_timeout=3,
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


async def ping_redis() -> bool:
    """
    Health check: Ping Redis.
    Returns True if healthy, False otherwise.
    Uses a 2-second timeout to avoid blocking the health endpoint.
    """
    import asyncio
    try:
        client = await asyncio.wait_for(get_redis(), timeout=2.0)
        await asyncio.wait_for(client.ping(), timeout=2.0)
        return True
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("redis_ping_failed", error=str(e))
        return False
