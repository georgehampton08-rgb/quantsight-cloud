"""
Presence Manager — Phase 8 Step 8.3
=====================================
Tracks anonymous session presence using Redis sorted sets.
Shows which sessions are viewing which player, game, or incident.

Key pattern: presence:{context_type}:{context_id}
Value: session_token with score = UNIX timestamp
TTL: 90s (refreshed on activity)

FAIL OPEN: If Redis is unavailable, presence returns 0 viewers.
No Vanguard incident for presence failure (Redis health already monitored).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
TTL_SECONDS = 90
MAX_PRESENCE_DISPLAY = 50


class PresenceManager:
    """
    Tracks anonymous session presence using Redis sorted sets.
    Shared across all Cloud Run instances via Redis.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client

    def set_redis(self, redis_client):
        """Update the Redis client (for lazy initialization)."""
        self._redis = redis_client

    async def _get_redis(self):
        """Get Redis client, lazy-loading if not set."""
        if self._redis is not None:
            return self._redis
        try:
            from vanguard.bootstrap.redis_client import get_redis_or_none
            self._redis = await get_redis_or_none()
            return self._redis
        except Exception:
            return None

    async def join(
        self,
        session_token: str,
        connection_id: str,
        context: dict,
    ):
        """
        Register a session as viewing the specified contexts.
        context format: { "player_id": "2544", "team": "LAL" }
        """
        redis = await self._get_redis()
        if not redis:
            return  # FAIL OPEN — no presence without Redis

        try:
            now = datetime.now(timezone.utc).timestamp()
            pipe = redis.pipeline(transaction=False)
            for context_type, context_id in context.items():
                key = f"presence:{context_type}:{context_id}"
                pipe.zadd(key, {session_token: now})
                pipe.expire(key, TTL_SECONDS)
            await pipe.execute()
        except Exception as e:
            logger.debug(f"presence_join_failed: {e}")
            # Presence failure is silent — never crashes

    async def leave(
        self,
        session_token: str,
        connection_id: Optional[str] = None,
    ):
        """
        Remove a session from all presence keys.
        Called on disconnect.
        """
        redis = await self._get_redis()
        if not redis:
            return

        try:
            # Scan for all presence keys containing this token
            removed = 0
            async for key in redis.scan_iter(match="presence:*", count=100):
                result = await redis.zrem(key, session_token)
                removed += result
            if removed:
                logger.debug(f"presence_leave: removed {removed} entries for {session_token[:8]}")
        except Exception as e:
            logger.debug(f"presence_leave_failed: {e}")

    async def update_context(
        self,
        session_token: str,
        new_context: dict,
    ):
        """
        Update a session's presence to new contexts.
        Removes from old contexts, adds to new ones.
        """
        await self.leave(session_token, None)
        if new_context:
            await self.join(session_token, None, new_context)

    async def get_viewers(
        self,
        context_type: str,
        context_id: str,
    ) -> int:
        """
        Returns count of active viewers for a given context.
        Prunes expired entries before counting.
        """
        redis = await self._get_redis()
        if not redis:
            return 0

        try:
            key = f"presence:{context_type}:{context_id}"
            cutoff = datetime.now(timezone.utc).timestamp() - TTL_SECONDS
            # Remove stale entries
            await redis.zremrangebyscore(key, "-inf", cutoff)
            return await redis.zcard(key)
        except Exception as e:
            logger.debug(f"presence_get_viewers_failed: {e}")
            return 0

    async def get_viewers_batch(
        self,
        contexts: list[tuple[str, str]],
    ) -> dict[str, int]:
        """
        Batch get viewer counts. Returns { "context_type:context_id": count }.
        Optimized for pulse cycle enrichment.
        """
        redis = await self._get_redis()
        if not redis:
            return {}

        results = {}
        try:
            cutoff = datetime.now(timezone.utc).timestamp() - TTL_SECONDS
            pipe = redis.pipeline(transaction=False)
            keys = []
            for ctx_type, ctx_id in contexts:
                key = f"presence:{ctx_type}:{ctx_id}"
                keys.append(f"{ctx_type}:{ctx_id}")
                pipe.zremrangebyscore(key, "-inf", cutoff)
                pipe.zcard(key)

            raw = await pipe.execute()

            # Results alternate: zremrangebyscore result, zcard result
            for i, composite_key in enumerate(keys):
                results[composite_key] = raw[i * 2 + 1]  # zcard is at odd indices
        except Exception as e:
            logger.debug(f"presence_batch_failed: {e}")

        return results


# ── Global singleton ─────────────────────────────────────────────────────────
_presence: Optional[PresenceManager] = None


def get_presence_manager() -> PresenceManager:
    """Get or create the global presence manager."""
    global _presence
    if _presence is None:
        _presence = PresenceManager()
    return _presence
