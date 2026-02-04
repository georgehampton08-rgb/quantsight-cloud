"""
NBA API Bridge for Aegis Router

Adapter that connects NBAAPIConnector (synchronous) with Aegis async interface
and integrates circuit breaker protection.
"""

import asyncio
from typing import Dict, Any, Optional
import logging
from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)


def normalize_stat(value, stat_type='ppg'):
    """
    Normalize stat values to handle data quality issues.
    e.g., if PPG > 60, it's likely total points, not average.
    """
    if value is None:
        return 0.0
    
    try:
        val = float(value)
        # Sanity check for per-game averages
        if stat_type in ('ppg', 'points_avg') and val > 60:
            val = val / 10  # Common data import error
        elif stat_type in ('rpg', 'rebounds_avg') and val > 25:
            val = val / 10
        elif stat_type in ('apg', 'assists_avg') and val > 20:
            val = val / 10
        return round(val, 1)
    except (TypeError, ValueError):
        return 0.0


class AegisNBABridge:
    """
    Bridge adapter connecting NBA API to Aegis router.
    
    Features:
    - Async/sync adapter (Aegis is async, NBAAPIConnector is sync)
    - Circuit breaker integration
    - Request type mapping
    - Error handling with graceful degradation
    """
    
    def __init__(self, nba_connector, circuit_breaker=None):
        """
        Initialize NBA bridge.
        
        Args:
            nba_connector: NBAAPIConnector instance
            circuit_breaker: Optional CircuitBreakerService
        """
        self.connector = nba_connector
        self.breaker = circuit_breaker
        self.call_count = 0
        self.error_count = 0
        
        logger.info(f"AegisNBABridge initialized (circuit breaker: {circuit_breaker is not None})")
    
    async def fetch(self, entity_type: str, entity_id: Any, query: Dict) -> Dict:
        """
        Fetch data from NBA API in Aegis-compatible format.
        
        Args:
            entity_type: Type of data ('player_stats', 'team_roster', 'schedule')
            entity_id: Player ID, team ID, etc.
            query: Additional parameters (season, etc.)
            
        Returns:
            Data dict with response and metadata
        """
        self.call_count += 1
        
        # Map Aegis request types to NBA API methods
        fetch_func = self._get_fetch_function(entity_type, entity_id, query)
        
        if not fetch_func:
            logger.warning(f"Unknown entity type: {entity_type}")
            return {'error': f'Unknown entity type: {entity_type}'}
        
        # Execute with circuit breaker if available
        try:
            if self.breaker:
                result = await self._fetch_with_breaker(fetch_func)
            else:
                result = await self._fetch_direct(fetch_func)
            
            return result
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"NBA API fetch failed: {e}")
            raise
    
    async def _fetch_with_breaker(self, fetch_func):
        """Execute fetch function through circuit breaker"""
        loop = asyncio.get_event_loop()
        
        def _sync_fetch():
            return self.breaker.call(fetch_func)
        
        # Run in executor to avoid blocking
        result = await loop.run_in_executor(None, _sync_fetch)
        return result
    
    async def _fetch_direct(self, fetch_func):
        """Execute fetch function directly (no circuit breaker)"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, fetch_func)
        return result
    
    def _get_fetch_function(self, entity_type: str, entity_id: Any, query: Dict):
        """
        Map Aegis entity types to NBA API connector methods.
        
        Returns:
            Callable that performs the fetch
        """
        season = query.get('season', CURRENT_SEASON)
        
        if entity_type == 'player_stats':
            def fetch():
                stats = self.connector.get_player_stats(str(entity_id), season)
                if stats:
                    return {'data': stats, 'latency_ms': 0}
                return None
            return fetch
        
        elif entity_type == 'team_roster':
            def fetch():
                roster = self.connector.get_team_roster(str(entity_id), season)
                if roster:
                    return {'data': roster, 'latency_ms': 0}
                return None
            return fetch
        
        elif entity_type == 'all_players':
            def fetch():
                players = self.connector.get_all_players(season)
                if players:
                    return {'data': players, 'latency_ms': 0}
                return None
            return fetch
        
        elif entity_type == 'player_profile':
            # Fetch complete player profile with stats
            def fetch():
                import sqlite3
                from pathlib import Path
                import os
                
                # Find correct database - check multiple locations
                base_path = Path(os.path.dirname(__file__)).parent
                possible_paths = [
                    base_path / 'data' / 'nba_data.db',
                    base_path / 'nba_data.db',
                    getattr(self.connector, 'db_path', None),
                ]
                
                db_path = None
                for p in possible_paths:
                    if p and Path(p).exists():
                        db_path = str(p)
                        break
                
                if not db_path:
                    logger.warning(f"No database found in paths: {possible_paths}")
                    # Fallback to NBA API
                    stats = self.connector.get_player_stats(str(entity_id), season)
                    return {
                        'data': {
                            'player': {'id': entity_id, 'name': f'Player {entity_id}'},
                            'current_stats': stats
                        },
                        'latency_ms': 0
                    }
                
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get player info
                cursor.execute("""
                    SELECT * FROM players WHERE player_id = ?
                """, (str(entity_id),))
                player_row = cursor.fetchone()
                
                stats = {}
                
                if player_row:
                    player = dict(player_row)
                    
                    # Get analytics from player_analytics table
                    cursor.execute("""
                        SELECT * FROM player_analytics 
                        WHERE player_id = ? AND season = ?
                    """, (str(entity_id), season))
                    analytics_row = cursor.fetchone()
                    
                    if analytics_row:
                        analytics = dict(analytics_row)
                        # Map analytics to expected stat names
                        stats = {
                            'true_shooting': analytics.get('true_shooting', 0),
                            'effective_fg': analytics.get('effective_fg', 0),
                            'usage_rate': analytics.get('usage_rate', 0),
                            'total_possessions': analytics.get('total_possessions', 0),
                            'best_play_type': analytics.get('best_play_type', ''),
                            'best_play_type_ppp': analytics.get('best_play_type_ppp', 0),
                        }
                    
                    conn.close()
                    
                    # If no DB stats, try live API for real-time stats
                    if not stats or not analytics_row:
                        live_stats = self.connector.get_player_stats(str(entity_id), season)
                        if live_stats:
                            stats = {
                                'points_avg': normalize_stat(live_stats.get('pts', live_stats.get('points', 0)), 'ppg'),
                                'rebounds_avg': normalize_stat(live_stats.get('reb', live_stats.get('rebounds', 0)), 'rpg'),
                                'assists_avg': normalize_stat(live_stats.get('ast', live_stats.get('assists', 0)), 'apg'),
                                'steals_avg': normalize_stat(live_stats.get('stl', live_stats.get('steals', 0)), 'ppg'),
                                'blocks_avg': normalize_stat(live_stats.get('blk', live_stats.get('blocks', 0)), 'ppg'),
                                'turnovers_avg': normalize_stat(live_stats.get('tov', live_stats.get('turnovers', 0)), 'ppg'),
                                'fg_pct': live_stats.get('fg_pct', live_stats.get('fg3_pct', 0)),
                                'three_p_pct': live_stats.get('fg3_pct', 0),
                                'ft_pct': live_stats.get('ft_pct', 0),
                                'plus_minus': live_stats.get('plus_minus', 0),
                                'games_played': live_stats.get('gp', live_stats.get('games', 0)),
                                'minutes_avg': live_stats.get('min', 0),
                            }
                    
                    # Normalize any cached stats from database as well
                    if 'points_avg' in stats:
                        stats['points_avg'] = normalize_stat(stats.get('points_avg'), 'ppg')
                        stats['rebounds_avg'] = normalize_stat(stats.get('rebounds_avg'), 'rpg')
                        stats['assists_avg'] = normalize_stat(stats.get('assists_avg'), 'apg')
                    
                    return {
                        'data': {
                            'player': {
                                'id': player.get('player_id'),
                                'name': player.get('name', 'Unknown'),
                                'team': player.get('team_id', ''),
                                'position': player.get('position', ''),
                            },
                            'current_stats': stats
                        },
                        'latency_ms': 0
                    }
                
                conn.close()
                
                # Player not in DB - try NBA API
                live_stats = self.connector.get_player_stats(str(entity_id), season)
                if live_stats:
                    return {
                        'data': {
                            'player': {'id': entity_id, 'name': f'Player {entity_id}', 'team': '', 'position': ''},
                            'current_stats': {
                                'points_avg': live_stats.get('pts', live_stats.get('points', 0)),
                                'rebounds_avg': live_stats.get('reb', live_stats.get('rebounds', 0)),
                                'assists_avg': live_stats.get('ast', live_stats.get('assists', 0)),
                                'steals_avg': live_stats.get('stl', live_stats.get('steals', 0)),
                                'blocks_avg': live_stats.get('blk', live_stats.get('blocks', 0)),
                                'turnovers_avg': live_stats.get('tov', live_stats.get('turnovers', 0)),
                                'fg_pct': live_stats.get('fg_pct', 0),
                                'three_p_pct': live_stats.get('fg3_pct', 0),
                                'ft_pct': live_stats.get('ft_pct', 0),
                                'plus_minus': live_stats.get('plus_minus', 0),
                                'games_played': live_stats.get('gp', 0),
                            }
                        },
                        'latency_ms': 0
                    }
                
                return None
            return fetch
        
        else:
            return None
    
    def get_stats(self) -> Dict:
        """Return bridge statistics"""
        return {
            'total_calls': self.call_count,
            'errors': self.error_count,
            'error_rate': self.error_count / self.call_count if self.call_count > 0 else 0,
            'circuit_breaker_active': self.breaker is not None
        }
