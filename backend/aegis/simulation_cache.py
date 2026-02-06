"""
Simulation Cache v3.1
=====================
TTL-based cache for simulation results.

1-hour TTL, 1000-entry max.
Repeat queries served in <5ms.
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import hashlib
import logging

try:
    from cachetools import TTLCache
    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry"""
    key: str
    result: Any
    created_at: datetime
    hit_count: int = 0


class SimulationCache:
    """
    TTL-based cache for simulation results.
    
    Features:
    - 1-hour TTL for data freshness
    - 1000 entry max to limit memory
    - Cache key includes all simulation parameters
    """
    
    DEFAULT_TTL = 3600  # 1 hour
    MAX_SIZE = 1000
    
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL,
        max_size: int = MAX_SIZE
    ):
        self.ttl = ttl_seconds
        self.max_size = max_size
        
        if CACHETOOLS_AVAILABLE:
            self._cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        else:
            # Simple dict fallback
            self._cache: Dict[str, CacheEntry] = {}
        
        # Metrics
        self._metrics = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def get(
        self,
        player_id: str,
        opponent_id: str,
        **kwargs
    ) -> Optional[Any]:
        """
        Get cached simulation result.
        
        Returns:
            Cached result if fresh, None if expired/missing
        """
        key = self._make_key(player_id, opponent_id, **kwargs)
        
        if CACHETOOLS_AVAILABLE:
            result = self._cache.get(key)
            if result:
                self._metrics['hits'] += 1
                logger.debug(f"[CACHE] Hit for {player_id}")
                return result
        else:
            entry = self._cache.get(key)
            if entry:
                # Check if expired
                if datetime.now() - entry.created_at < timedelta(seconds=self.ttl):
                    self._metrics['hits'] += 1
                    entry.hit_count += 1
                    return entry.result
                else:
                    # Expired - remove
                    del self._cache[key]
        
        self._metrics['misses'] += 1
        return None
    
    def set(
        self,
        player_id: str,
        opponent_id: str,
        result: Any,
        **kwargs
    ):
        """
        Cache a simulation result.
        """
        key = self._make_key(player_id, opponent_id, **kwargs)
        
        if CACHETOOLS_AVAILABLE:
            self._cache[key] = result
        else:
            # Simple size-limited cache
            if len(self._cache) >= self.max_size:
                # Remove oldest
                oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
                del self._cache[oldest_key]
                self._metrics['evictions'] += 1
            
            self._cache[key] = CacheEntry(
                key=key,
                result=result,
                created_at=datetime.now()
            )
        
        logger.debug(f"[CACHE] Stored result for {player_id}")
    
    def _make_key(
        self,
        player_id: str,
        opponent_id: str,
        **kwargs
    ) -> str:
        """Create cache key from parameters"""
        params = f"{player_id}:{opponent_id}"
        
        # Include other params in key
        for k, v in sorted(kwargs.items()):
            params += f":{k}={v}"
        
        # Hash for consistent key length
        return hashlib.md5(params.encode()).hexdigest()
    
    def invalidate(self, player_id: str):
        """Invalidate all cache entries for a player"""
        if CACHETOOLS_AVAILABLE:
            # cachetools doesn't support partial invalidation easily
            # Iterate and collect keys to remove
            keys_to_remove = [k for k in list(self._cache.keys()) if player_id in k]
            for key in keys_to_remove:
                try:
                    del self._cache[key]
                except KeyError:
                    pass
            logger.info(f"[CACHE] Invalidated {len(keys_to_remove)} entries for {player_id}")
        else:
            keys_to_remove = [
                k for k in self._cache 
                if player_id in str(self._cache[k].key)
            ]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"[CACHE] Invalidated {len(keys_to_remove)} entries for {player_id}")
    
    def invalidate_player(self, player_id: str):
        """Alias for invalidate - used by refresh endpoint"""
        self.invalidate(player_id)
    
    def clear(self):
        """Clear entire cache"""
        if CACHETOOLS_AVAILABLE:
            self._cache.clear()
        else:
            self._cache = {}
        
        logger.info("[CACHE] Cleared all entries")
    
    def get_metrics(self) -> Dict:
        """Get cache performance metrics"""
        total = self._metrics['hits'] + self._metrics['misses']
        hit_rate = self._metrics['hits'] / total if total > 0 else 0
        
        return {
            **self._metrics,
            'size': len(self._cache),
            'max_size': self.max_size,
            'hit_rate': round(hit_rate, 3),
            'ttl_seconds': self.ttl
        }
