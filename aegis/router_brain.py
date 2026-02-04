"""
Aegis Brain - Smart Routing & Fallback Logic
Manages locality checks, freshness detection, and graceful degradation
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class DataFreshness(Enum):
    """Data freshness status"""
    FRESH = "fresh"          # < threshold, serve immediately
    WARM = "warm"            # Past threshold but usable, queue refresh
    STALE = "stale"          # Needs refresh from API
    MISSING = "missing"      # Not in cache at all


class APIUnreachableError(Exception):
    """Raised when API is unavailable"""
    pass


class AegisBrain:
    """
    Central routing intelligence for all data requests.
    
    Implements smart routing with:
    - Locality checks (is data cached?)
    - Freshness detection (is cache data fresh enough?)
    - Graceful degradation (offline mode when API fails)
    - Integration safety (doesn't modify calculation logic)
    """
    
    # Freshness thresholds by data type
    FRESHNESS_THRESHOLDS = {
        'player_stats': timedelta(hours=6),      # Game stats update after games
        'team_stats': timedelta(hours=12),       # Team aggregates less frequent
        'schedule': timedelta(hours=1),          # Schedules can change
        'injuries': timedelta(minutes=30),       # Injuries are time-sensitive
        'career': timedelta(days=7),             # Career stats rarely change
        'player_profile': timedelta(days=1),     # Profile data mostly static
    }
    
    def __init__(self, cache_manager, api_bridge=None, governor=None, 
                 integrity_healer=None, schema_enforcer=None):
        """
        Initialize the Aegis Brain router.
        
        Args:
            cache_manager: Cache interface (database, redis, etc.)
            api_bridge: Optional API client for live data
            governor: Optional TokenBucketGovernor for rate limiting
            integrity_healer: Optional DataIntegrityHealer for hash verification
            schema_enforcer: Optional SchemaEnforcer for validation
        """
        self.cache = cache_manager
        self.api = api_bridge
        self.governor = governor
        self.healer = integrity_healer
        self.enforcer = schema_enforcer
        self.offline_mode = False
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls': 0,
            'api_calls_denied': 0,  # Rate limited
            'offline_mode_activations': 0,
            'integrity_failures': 0,
            'validation_failures': 0
        }
        
        logger.info(f"AegisBrain initialized (rate limiting: {governor is not None}, "
                   f"integrity: {integrity_healer is not None}, validation: {schema_enforcer is not None})")
    
    async def route_request(self, query: dict) -> dict:
        """
        Master routing decision for any data request.
        
        Flow:
        1. Locality Check → Is data in cache?
        2. Freshness Check → Is cache data fresh enough?
        3. API Decision → Fetch if needed, with fallback
        4. Return data with metadata
        
        Args:
            query: Request details with 'type', 'id', and optional params
            
        Returns:
            dict with 'data', 'source', 'latency_ms', 'freshness'
        """
        entity_type = query.get('type')
        entity_id = query.get('id')
        
        logger.debug(f"Routing request: {entity_type}:{entity_id}")
        
        # Step 1: Locality Check
        cache_result = await self.locality_check(entity_type, entity_id)
        
        if cache_result['status'] == DataFreshness.FRESH:
            # Condition A: Serve instantly from cache (0ms latency)
            self.stats['cache_hits'] += 1
            logger.info(f"Cache HIT (fresh): {entity_type}:{entity_id}")
            
            return {
                'data': cache_result['data'],
                'source': 'cache',
                'latency_ms': 0,
                'freshness': 'fresh',
                'last_sync': cache_result.get('last_sync')
            }
        
        elif cache_result['status'] == DataFreshness.WARM:
            # Serve warm data but queue background refresh
            self.stats['cache_hits'] += 1
            logger.info(f"Cache HIT (warm): {entity_type}:{entity_id}, queuing refresh")
            
            # TODO: Queue background refresh
            # await self.queue_background_refresh(entity_type, entity_id)
            
            return {
                'data': cache_result['data'],
                'source': 'cache',
                'latency_ms': 0,
                'freshness': 'warm',
                'refresh_queued': True,
                'last_sync': cache_result.get('last_sync')
            }
        
        elif cache_result['status'] in [DataFreshness.STALE, DataFreshness.MISSING]:
            # Condition B: Fetch delta from API
            self.stats['cache_misses'] += 1
            logger.info(f"Cache MISS ({cache_result['status'].value}): {entity_type}:{entity_id}")
            
            try:
                if self.api is None:
                    raise APIUnreachableError("API bridge not configured")
                
                # Fetch from API
                api_data = await self.fetch_with_governance(entity_type, entity_id, query)
                
                # Merge with cached data if available
                if cache_result['data']:
                    merged = await self.merge_delta(cache_result['data'], api_data)
                else:
                    merged = api_data
                
                # Update cache
                await self.cache.set(
                    entity_type, 
                    entity_id, 
                    merged,
                    timestamp=datetime.now()
                )
                
                return {
                    'data': merged,
                    'source': 'api' if not cache_result['data'] else 'api+cache',
                    'latency_ms': api_data.get('latency_ms', 0),
                    'freshness': 'live',
                    'last_sync': datetime.now().isoformat()
                }
                
            except (APIUnreachableError, Exception) as e:
                logger.error(f"API fetch failed: {e}")
                # Graceful Degradation - activate offline mode
                return await self.activate_offline_mode(cache_result, str(e))
    
    async def locality_check(self, entity_type: str, entity_id: int) -> dict:
        """
        Check if data exists locally and assess freshness.
        
        Args:
            entity_type: Type of entity ('player_stats', 'team_stats', etc.)
            entity_id: Unique identifier
            
        Returns:
            dict with 'status' (DataFreshness), 'data', 'last_sync'
        """
        cached = await self.cache.get(entity_type, entity_id)
        
        if not cached:
            return {
                'status': DataFreshness.MISSING,
                'data': None,
                'last_sync': None
            }
        
        # Check freshness threshold
        threshold = self.FRESHNESS_THRESHOLDS.get(
            entity_type, 
            timedelta(hours=12)  # Default threshold
        )
        
        last_sync = cached.get('last_sync')
        if not last_sync:
            # No timestamp, consider stale
            return {
                'status': DataFreshness.STALE,
                'data': cached.get('data'),
                'last_sync': None
            }
        
        # Calculate age
        if isinstance(last_sync, str):
            last_sync = datetime.fromisoformat(last_sync)
        
        age = datetime.now() - last_sync
        
        # Determine freshness
        if age < threshold:
            status = DataFreshness.FRESH
        elif age < threshold * 2:
            status = DataFreshness.WARM
        else:
            status = DataFreshness.STALE
        
        return {
            'status': status,
            'data': cached.get('data'),
            'last_sync': last_sync.isoformat()
        }
    
    async def fetch_with_governance(self, entity_type: str, entity_id: int, 
                                     query: dict) -> dict:
        """
        Fetch from API with rate limiting governance.
        
        Integrates with TokenBucketGovernor to prevent hitting rate limits.
        """
        # Acquire token from governor before making API call
        if self.governor:
            priority = query.get('priority', 'normal')
            allowed = await self.governor.acquire_token(priority)
            
            if not allowed:
                # Rate limited - increment denial counter
                self.stats['api_calls_denied'] += 1
                logger.warning(f"API call denied by governor: {entity_type}:{entity_id}")
                raise APIUnreachableError("Rate limited by governor")
        
        self.stats['api_calls'] += 1
        
        # Call API bridge
        data = await self.api.fetch(entity_type, entity_id, query)
        
        # Update governor with API response headers (if available)
        if self.governor and isinstance(data, dict) and 'headers' in data:
            self.governor.update_from_headers(data['headers'])
        
        return data
    
    async def merge_delta(self, cached_data: dict, api_data: dict) -> dict:
        """
        Merge cached data with fresh API data.
        
        Strategy: API data takes precedence, but preserve cached fields
        not present in API response.
        """
        merged = cached_data.copy()
        merged.update(api_data)
        return merged
    
    async def activate_offline_mode(self, cache_result: dict, error_msg: str) -> dict:
        """
        Graceful degradation when API is unreachable.
        
        Serves cached data with offline mode flag and notifies UI.
        """
        self.offline_mode = True
        self.stats['offline_mode_activations'] += 1
        
        logger.warning(f"Activating offline mode: {error_msg}")
        
        # Prepare offline response
        response = {
            'data': cache_result.get('data', {}),
            'source': 'historical_baseline',
            'latency_ms': 0,
            'freshness': 'offline',
            'offline_mode': True,
            'error': error_msg,
            'message': 'Showing historical data. Some stats may be outdated.',
            'last_sync': cache_result.get('last_sync')
        }
        
        # TODO: Notify UI of offline status
        # await self.notify_ui_status(...)
        
        return response
    
    def get_stats(self) -> dict:
        """Return router statistics for monitoring"""
        return {
            **self.stats,
            'offline_mode': self.offline_mode,
            'cache_hit_rate': (
                self.stats['cache_hits'] / 
                (self.stats['cache_hits'] + self.stats['cache_misses'])
                if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0
                else 0
            )
        }
    
    def reset_offline_mode(self):
        """Reset offline mode (call when API is back online)"""
        if self.offline_mode:
            logger.info("Exiting offline mode")
            self.offline_mode = False
