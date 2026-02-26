"""Vanguard Bootstrap - Redis and lifespan management."""

from .redis_client import get_redis, get_redis_or_none, close_redis, ping_redis
from .lifespan import vanguard_lifespan

__all__ = ["get_redis", "get_redis_or_none", "close_redis", "ping_redis", "vanguard_lifespan"]
