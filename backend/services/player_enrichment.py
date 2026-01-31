"""
Player Enrichment Service v2
Orchestrates on-demand data fetching with Shadow-Fetch pattern.
Automatically queues 5 background fetch jobs when a matchup is searched.
"""
import asyncio
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from .freshness_tracker import get_freshness_tracker, FreshnessTracker
from .h2h_fetcher import get_h2h_fetcher, H2HFetcher
from .archetype_engine import get_archetype_engine, ArchetypeEngine
from .tracking_data_fetcher import get_tracking_fetcher, TrackingDataFetcher

logger = logging.getLogger(__name__)


class PlayerEnrichmentService:
    """
    Orchestrates player data enrichment with non-blocking Shadow-Fetch pattern.
    
    Key Features:
    - Returns cached data immediately (no blocking)
    - Triggers background refresh for stale data
    - Queues all 5 tracking data layers on matchup search
    - Thread-safe background job queue
    """
    
    # TTL for tracking data (hours)
    TRACKING_TTL_HOURS = 12
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        
        # Initialize sub-services
        self.freshness = get_freshness_tracker()
        self.h2h_fetcher = get_h2h_fetcher()
        self.archetype_engine = get_archetype_engine()
        self.tracking_fetcher = get_tracking_fetcher()
        
        # Background job queue (max 5 workers for parallel fetches)
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="enrichment")
        self._pending_jobs = set()
        self._job_lock = threading.Lock()
        
        # Callbacks for UI notifications
        self._on_refresh_complete: Optional[Callable] = None
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    # ==========================================================================
    # SHADOW-FETCH: Non-Blocking Data Access
    # ==========================================================================
    
    def ensure_fresh_h2h(self, player_id: str, opponent: str) -> Dict:
        """Shadow-Fetch for H2H data"""
        opponent = opponent.upper()
        job_key = f"h2h:{player_id}:{opponent}"
        
        cached = self.h2h_fetcher.get_h2h_stats(player_id, opponent)
        is_stale = self.freshness.is_stale(player_id, 'h2h', opponent)
        
        if is_stale:
            self._queue_background_job(job_key, self._refresh_h2h_async, player_id, opponent)
        
        return {
            'data': cached,
            'is_fresh': not is_stale,
            'refresh_queued': is_stale,
        }
    
    def ensure_fresh_archetype(self, player_id: str) -> Dict:
        """Shadow-Fetch for archetype data"""
        job_key = f"archetype:{player_id}"
        
        cached = self.archetype_engine.get_archetype(player_id)
        is_stale = self.freshness.is_stale(player_id, 'archetype')
        
        if is_stale:
            self._queue_background_job(job_key, self._refresh_archetype_async, player_id)
        
        return {
            'data': cached,
            'is_fresh': not is_stale,
            'refresh_queued': is_stale,
        }
    
    def ensure_fresh_tracking(self) -> Dict:
        """
        Shadow-Fetch for all tracking data layers.
        Checks staleness and queues batch refresh if needed.
        """
        fetch_status = self.tracking_fetcher.get_fetch_status()
        
        stale_layers = []
        for layer in ['hustle', 'defense', 'shot_clock', 'advanced']:
            layer_info = fetch_status.get(layer, {})
            last_fetch = layer_info.get('last_fetch')
            
            if not last_fetch:
                stale_layers.append(layer)
            else:
                last_dt = datetime.fromisoformat(last_fetch) if isinstance(last_fetch, str) else last_fetch
                if datetime.now() - last_dt > timedelta(hours=self.TRACKING_TTL_HOURS):
                    stale_layers.append(layer)
        
        if stale_layers:
            # Queue batch fetch for stale layers
            for layer in stale_layers:
                job_key = f"tracking:{layer}"
                if layer == 'hustle':
                    self._queue_background_job(job_key, self.tracking_fetcher.fetch_hustle_stats)
                elif layer == 'defense':
                    self._queue_background_job(job_key, self.tracking_fetcher.fetch_defense_tracking)
                elif layer == 'shot_clock':
                    self._queue_background_job(job_key, self.tracking_fetcher.fetch_shot_clock)
                elif layer == 'advanced':
                    self._queue_background_job(job_key, self.tracking_fetcher.fetch_advanced_stats)
        
        return {
            'stale_layers': stale_layers,
            'refresh_queued': len(stale_layers) > 0,
            'fetch_status': fetch_status,
        }
    
    def enrich_player_for_matchup(self, player_id: str, opponent: str) -> Dict:
        """
        Full enrichment for matchup analysis.
        Returns all cached data + queues any stale refreshes including 5 tracking layers.
        """
        opponent = opponent.upper()
        
        # 1. H2H data (shadow-fetch)
        h2h_result = self.ensure_fresh_h2h(player_id, opponent)
        
        # 2. Archetype (shadow-fetch)
        arch_result = self.ensure_fresh_archetype(player_id)
        
        # 3. Tracking data (shadow-fetch all 5 layers)
        tracking_result = self.ensure_fresh_tracking()
        
        # 4. Get player's tracking profile from cache
        tracking_profile = self.tracking_fetcher.get_player_full_profile(player_id)
        
        # 5. Calculate friction if archetypes available
        friction_data = None
        if arch_result.get('data'):
            friction_data = arch_result['data'].get('friction_matrix', {})
        
        # 6. Build enhanced profile with all data
        return {
            'player_id': player_id,
            'opponent': opponent,
            'h2h': h2h_result.get('data'),
            'h2h_fresh': h2h_result.get('is_fresh', False),
            'archetype': arch_result.get('data'),
            'archetype_fresh': arch_result.get('is_fresh', False),
            'friction_matrix': friction_data,
            'tracking': tracking_profile,
            'tracking_stale_layers': tracking_result.get('stale_layers', []),
            'refreshes_queued': (
                h2h_result.get('refresh_queued', False) or 
                arch_result.get('refresh_queued', False) or
                tracking_result.get('refresh_queued', False)
            ),
            'pending_jobs': self.get_pending_jobs_count(),
        }
    
    def enrich_matchup(self, home_team: str, away_team: str, player_ids: List[str]) -> Dict:
        """
        Enrich all players for a matchup (e.g., when Matchup Lab is opened).
        Queues background fetches for all players and all data layers.
        """
        # Ensure tracking data is fresh
        tracking_result = self.ensure_fresh_tracking()
        
        # Queue H2H for each player vs opponent
        enrichments = []
        for player_id in player_ids[:20]:  # Limit to top 20 players
            # Determine opponent based on player's team
            player_profile = self.tracking_fetcher.get_player_full_profile(player_id)
            if player_profile.get('advanced') and player_profile['advanced'].get('team') == home_team:
                opponent = away_team
            else:
                opponent = home_team
            
            result = self.enrich_player_for_matchup(player_id, opponent)
            enrichments.append(result)
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'player_count': len(enrichments),
            'tracking_status': tracking_result,
            'pending_jobs': self.get_pending_jobs_count(),
        }
    
    # ==========================================================================
    # BACKGROUND REFRESH JOBS
    # ==========================================================================
    
    def _queue_background_job(self, job_key: str, func: Callable, *args):
        """Queue a background job (non-blocking, deduped)"""
        with self._job_lock:
            if job_key in self._pending_jobs:
                logger.debug(f"Job already pending: {job_key}")
                return
            self._pending_jobs.add(job_key)
        
        def job_wrapper():
            try:
                logger.info(f"Starting background job: {job_key}")
                result = func(*args)
                logger.info(f"Completed background job: {job_key}")
                
                if self._on_refresh_complete:
                    self._on_refresh_complete(job_key, result)
                
                return result
            except Exception as e:
                logger.error(f"Background job failed: {job_key} - {e}")
            finally:
                with self._job_lock:
                    self._pending_jobs.discard(job_key)
        
        self._executor.submit(job_wrapper)
    
    def _refresh_h2h_async(self, player_id: str, opponent: str) -> Dict:
        """Background H2H refresh job"""
        import time
        start = time.time()
        
        result = self.h2h_fetcher.fetch_h2h(player_id, opponent)
        
        if result.get('success'):
            duration_ms = int((time.time() - start) * 1000)
            self.freshness.mark_fresh(player_id, 'h2h', opponent, duration_ms)
            
            # Also update archetype after new data
            self._queue_background_job(
                f"archetype:{player_id}",
                self._refresh_archetype_async,
                player_id
            )
        
        return result
    
    def _refresh_archetype_async(self, player_id: str) -> Dict:
        """Background archetype refresh job"""
        import time
        start = time.time()
        
        result = self.archetype_engine.classify_player(player_id)
        
        if result.get('primary'):
            duration_ms = int((time.time() - start) * 1000)
            self.freshness.mark_fresh(player_id, 'archetype', '', duration_ms)
        
        return result
    
    # ==========================================================================
    # QUERY METHODS
    # ==========================================================================
    
    def get_player_tracking(self, player_id: str) -> Dict:
        """Get all tracking data for a player"""
        return self.tracking_fetcher.get_player_full_profile(player_id)
    
    def get_player_defense_friction(self, player_id: str) -> Optional[float]:
        """Get player's defensive impact for friction calculation"""
        defense = self.tracking_fetcher.get_player_defense(player_id)
        if defense:
            return defense.get('pct_plusminus', 0)
        return None
    
    def get_enrichment_status(self, player_id: str, opponent: str = '') -> Dict:
        """Get detailed freshness status"""
        h2h_info = self.freshness.get_freshness_info(player_id, 'h2h', opponent)
        arch_info = self.freshness.get_freshness_info(player_id, 'archetype', '')
        tracking_status = self.tracking_fetcher.get_fetch_status()
        
        with self._job_lock:
            pending = list(self._pending_jobs)
        
        return {
            'player_id': player_id,
            'opponent': opponent,
            'h2h_freshness': h2h_info,
            'archetype_freshness': arch_info,
            'tracking_status': tracking_status,
            'pending_jobs': pending,
        }
    
    def force_refresh(self, player_id: str, opponent: str = ''):
        """Force immediate refresh (bypasses cache, still async)"""
        if opponent:
            self._queue_background_job(
                f"h2h:{player_id}:{opponent}:forced",
                self._refresh_h2h_async,
                player_id, opponent
            )
        
        self._queue_background_job(
            f"archetype:{player_id}:forced",
            self._refresh_archetype_async,
            player_id
        )
    
    def force_refresh_all_tracking(self):
        """Force refresh all tracking data layers"""
        self._queue_background_job("tracking:hustle:forced", self.tracking_fetcher.fetch_hustle_stats)
        self._queue_background_job("tracking:defense:forced", self.tracking_fetcher.fetch_defense_tracking)
        self._queue_background_job("tracking:shot_clock:forced", self.tracking_fetcher.fetch_shot_clock)
        self._queue_background_job("tracking:advanced:forced", self.tracking_fetcher.fetch_advanced_stats)
        
        return {'message': 'Queued 4 tracking refresh jobs'}
    
    def set_refresh_callback(self, callback: Callable):
        """Set callback for when background refreshes complete"""
        self._on_refresh_complete = callback
    
    def get_pending_jobs_count(self) -> int:
        """Get count of pending background jobs"""
        with self._job_lock:
            return len(self._pending_jobs)
    
    def shutdown(self):
        """Graceful shutdown of background workers"""
        self._executor.shutdown(wait=False)


# Singleton
_service = None

def get_enrichment_service() -> PlayerEnrichmentService:
    global _service
    if _service is None:
        _service = PlayerEnrichmentService()
    return _service


if __name__ == "__main__":
    import time
    import json
    
    logging.basicConfig(level=logging.INFO)
    
    service = get_enrichment_service()
    
    print("="*60)
    print("Testing Player Enrichment Service v2")
    print("="*60)
    
    # Test full enrichment (will queue background jobs)
    print("\nEnriching LeBron vs GSW...")
    result = service.enrich_player_for_matchup("2544", "GSW")
    print(json.dumps({k: v for k, v in result.items() if k != 'tracking'}, indent=2, default=str))
    
    print(f"\nPending jobs: {service.get_pending_jobs_count()}")
    
    # Wait for background jobs
    print("\nWaiting for background jobs...")
    time.sleep(5)
    
    print(f"Pending jobs after wait: {service.get_pending_jobs_count()}")
    
    # Get tracking data
    print("\nTracking profile:")
    tracking = service.get_player_tracking("2544")
    if tracking.get('hustle'):
        print(f"  Hustle: Contested={tracking['hustle'].get('contested_shots')}, "
              f"Deflections={tracking['hustle'].get('deflections')}")
    if tracking.get('defense'):
        print(f"  Defense: DFG%={tracking['defense'].get('d_fg_pct')}, "
              f"Impact={tracking['defense'].get('pct_plusminus')}")
    
    service.shutdown()
