"""
Async Pulse Producer - Cloud Mode (Firebase Only)
===================================================
Refactored version for Cloud Run deployment.
Removes LivePulseCache and SSE - writes directly to Firestore.

Key Changes from Desktop:
- NO local cache (LivePulseCache removed)
- NO SSE broadcasting (replaced by Firebase real-time listeners)
- Writes to Firestore: live_games, live_leaders collections
- Lightweight for Cloud Run (minimal memory footprint)
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta

# Import shared_core for math parity with desktop
import sys
from pathlib import Path
_backend_path = Path(__file__).parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

# Shared core imports (copied from desktop)
try:
    sys.path.insert(0, str(_backend_path.parent / 'shared_core'))
    from adapters.nba_api_adapter import (
        AsyncNBAApiAdapter,
        NormalizedBoxScore,
        get_nba_adapter,
        is_garbage_time
    )
    from engines.pie_calculator import calculate_live_pie
    from calculators.advanced_stats import (
        calculate_true_shooting, 
        calculate_effective_fg,
        calculate_in_game_usage
    )
    ADAPTER_AVAILABLE = True
except ImportError as e:
    ADAPTER_AVAILABLE = False
    logging.warning(f"Shared core not available: {e}")

# Firebase service
from services.firebase_admin_service import get_firebase_service

# Cloud SQL data service for Alpha metrics
from services.cloud_sql_data_service import (
    get_team_defense_rating,
    get_player_season_usage,
    get_player_rolling_ts,
    calculate_usage_vacuum,
    calculate_heat_scale,
    LEAGUE_AVG_DEF_RATING
)

logger = logging.getLogger(__name__)


class CloudAsyncPulseProducer:
    """
    Cloud-native pulse producer for Firebase writes.
    NO local cache, NO SSE - pure Firestore updates.
    """
    
    VERSION = "4.0.0-cloud"
    POLL_INTERVAL_SECONDS = 10
    
    def __init__(self):
        self._adapter = get_nba_adapter() if ADAPTER_AVAILABLE else None
        self._firebase = get_firebase_service()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._update_count = 0
        self._last_update_duration: float = 0.0
        self._firebase_write_errors = 0
        
        logger.info(f"🚀 CloudAsyncPulseProducer v{self.VERSION} initialized")
        if self._firebase:
            logger.info("   └─ Firebase: ENABLED")
        else:
            logger.warning("   └─ Firebase: DISABLED - producer will run in degraded mode")
    
    async def start(self):
        """Start the cloud producer loop."""
        if self._running:
            logger.warning("Cloud producer already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._producer_loop())
        logger.info("🔥 Cloud pulse producer started")
    
    async def stop(self):
        """Stop the cloud producer loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Cloud pulse producer stopped")
    
    async def _producer_loop(self):
        """Main producer loop - polls NBA API and writes to Firebase."""
        while self._running:
            try:
                start_time = time.perf_counter()
                await self._update_firebase()
                self._last_update_duration = time.perf_counter() - start_time
                
                self._update_count += 1
                if self._update_count % 6 == 0:  # Every minute
                    logger.info(
                        f"⚡ Cloud update #{self._update_count}: "
                        f"completed in {self._last_update_duration:.2f}s"
                    )
                
            except Exception as e:
                logger.error(f"❌ Cloud update failed: {e}")
            
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
    
    async def _update_firebase(self):
        """
        Fetch live game data and write to Firebase.
        This is the core replacement for desktop's cache update logic.
        """
        if not self._adapter:
            logger.warning("NBA API adapter not available")
            return
        
        if not self._firebase:
            logger.warning("Firebase not available - skipping update")
            return
        
        try:
            # Step 1: Fetch scoreboard
            games = await self._adapter.fetch_scoreboard_async()
            
            if not games:
                logger.debug("No games found in scoreboard")
                return
            
            # Step 2: Identify live games
            live_game_ids = [g.game_id for g in games if g.status == 'LIVE']
            
            if not live_game_ids:
                logger.debug("No live games currently")
                return
            
            # Step 3: Fetch all live boxscores concurrently
            boxscores: Dict[str, Optional[NormalizedBoxScore]] = {}
            if live_game_ids:
                boxscores = await self._adapter.fetch_all_live_boxscores_async(live_game_ids)
            
            # Step 4: Process each game and write to Firebase
            all_leaders = []
            
            for game_info in games:
                if game_info.status != 'LIVE':
                    continue
                
                game_id = game_info.game_id
                boxscore = boxscores.get(game_id)
                
                if not boxscore:
                    continue
                
                # Extract leaders from boxscore
                leaders = self._extract_leaders_from_normalized(
                    boxscore,
                    home_team=game_info.home_team_tricode,
                    away_team=game_info.away_team_tricode
                )
                
                # Collect for leaderboard
                all_leaders.extend(leaders)
                
                # Detect garbage time
                garbage_time_active = is_garbage_time(
                    period=game_info.period,
                    clock_str=game_info.clock,
                    home_score=game_info.home_score,
                    away_score=game_info.away_score
                )
                
                # Build game state for Firebase
                game_data = {
                    'game_id': game_id,
                    'home_team': game_info.home_team_tricode,
                    'away_team': game_info.away_team_tricode,
                    'home_score': game_info.home_score,
                    'away_score': game_info.away_score,
                    'clock': game_info.status_text,
                    'period': game_info.period,
                    'status': game_info.status,
                    'is_garbage_time': garbage_time_active,
                    'leaders': leaders[:10]  # Top 10 for this game
                }
                
                # Write to Firebase (non-blocking)
                asyncio.create_task(self._firebase.upsert_game_state(game_data))
            
            # Step 5: Update global leaderboard (top 10 across all games)
            if all_leaders:
                all_leaders.sort(key=lambda x: x['pie'], reverse=True)
                top_10_leaders = all_leaders[:10]
                
                asyncio.create_task(self._firebase.upsert_live_leaders(top_10_leaders))
            
        except Exception as e:
            logger.error(f"❌ Firebase update failed: {e}", exc_info=True)
    
    def _extract_leaders_from_normalized(
        self, 
        boxscore: 'NormalizedBoxScore',  # String annotation to avoid import-time NameError
        home_team: str = '',
        away_team: str = ''
    ) -> List[Dict]:

        """
        Extract player stats from normalized boxscore.
        Simplified cloud version - no rolling averages (for now).
        """
        leaders = []
        
        for player in boxscore.all_active_players():
            # Calculate PIE using shared_core
            pie = calculate_live_pie(
                pts=player.pts, fgm=player.fgm, fga=player.fga,
                ftm=player.ftm, fta=player.fta,
                oreb=player.oreb, dreb=player.dreb,
                ast=player.ast, stl=player.stl, blk=player.blk,
                pf=player.pf, tov=player.tov
            )
            
            # Calculate efficiency metrics
            ts_pct = round(calculate_true_shooting(player.pts, player.fga, player.fta), 4)
            efg_pct = round(calculate_effective_fg(player.fgm, player.fg3m, player.fga), 4)
            
            # Determine opponent for matchup context
            opponent_team = away_team if player.team_tricode == home_team else home_team
            
            # =================================================================
            # ALPHA PATCHER: USAGE VACUUM DETECTION (LIVE)
            # =================================================================
            usage_rate = None
            usage_vacuum = False
            
            try:
                # Calculate current in-game usage rate
                team_stats = boxscore.get_team_stats(player.team_tricode)
                if team_stats and ADAPTER_AVAILABLE:
                    usage_rate = calculate_in_game_usage(
                        player_pts=player.pts,
                        player_fga=player.fga,
                        player_fta=player.fta,
                        player_tov=player.tov,
                        team_fga=team_stats.fga,
                        team_fta=team_stats.fta,
                        team_tov=team_stats.tov
                    )
                    
                    # Query season baseline from Cloud SQL
                    season_avg_usage = get_player_season_usage(player.player_id)
                    usage_vacuum = calculate_usage_vacuum(usage_rate, season_avg_usage)
            except Exception as e:
                logger.debug(f"Usage calculation failed for {player.name}: {e}")
            
            # =================================================================
            # ALPHA PATCHER: MATCHUP DIFFICULTY DETECTION (LIVE)
            # =================================================================
            opponent_def_rating, matchup_difficulty = get_team_defense_rating(opponent_team)
            
            # =================================================================
            # ALPHA PATCHER: HEAT SCALE CALCULATION (LIVE)
            # =================================================================
            season_avg_ts = get_player_rolling_ts(player.player_id)
            heat_scale = calculate_heat_scale(ts_pct, season_avg_ts)
            
            # Detect garbage time
            game_info = boxscore.game_info
            player_is_garbage_time = is_garbage_time(
                period=game_info.period,
                clock_str=game_info.clock,
                home_score=game_info.home_score,
                away_score=game_info.away_score
            )
            
            leaders.append({
                'player_id': player.player_id,
                'name': player.name,
                'team': player.team_tricode,
                'pie': pie,
                'plus_minus': player.plus_minus,
                'ts_pct': ts_pct,
                'efg_pct': efg_pct,
                'opponent': opponent_team,
                'minutes': player.minutes,
                'is_garbage_time': player_is_garbage_time,
                # Alpha metrics (placeholders until Cloud SQL)
                'usage_rate': usage_rate,
                'usage_vacuum': usage_vacuum,
                'opponent_def_rating': opponent_def_rating,
                'matchup_difficulty': matchup_difficulty,
                'season_avg_ts': season_avg_ts,
                'heat_scale': heat_scale,
                'stats': {
                    'pts': player.pts,
                    'fga': player.fga,  # Field goals attempted
                    'fg3m': player.fg3m,  # 3-pointers made
                    'reb': player.reb,
                    'ast': player.ast,
                    'stl': player.stl,
                    'blk': player.blk,
                    'pf': player.pf,  # Personal fouls
                    'tov': player.tov,  # Turnovers
                    'min': player.minutes  # Minutes played
                }
            })

        
        # Sort by PIE descending
        leaders.sort(key=lambda x: x['pie'], reverse=True)
        return leaders
    
    def get_status(self) -> Dict:
        """Get producer status for health checks."""
        return {
            "version": self.VERSION,
            "running": self._running,
            "adapter_available": ADAPTER_AVAILABLE,
            "firebase_enabled": self._firebase is not None,
            "update_count": self._update_count,
            "last_update_duration_seconds": round(self._last_update_duration, 3),
            "poll_interval_seconds": self.POLL_INTERVAL_SECONDS,
            "firebase_write_errors": self._firebase_write_errors
        }


# ============================================================================
# GLOBAL PRODUCER MANAGEMENT
# ============================================================================

_cloud_producer: Optional[CloudAsyncPulseProducer] = None


async def start_cloud_producer() -> CloudAsyncPulseProducer:
    """Start the global cloud producer."""
    global _cloud_producer
    
    if _cloud_producer is None:
        _cloud_producer = CloudAsyncPulseProducer()
    
    await _cloud_producer.start()
    return _cloud_producer


async def stop_cloud_producer():
    """Stop the global cloud producer."""
    global _cloud_producer
    
    if _cloud_producer:
        await _cloud_producer.stop()


def get_cloud_producer() -> Optional[CloudAsyncPulseProducer]:
    """Get the current cloud producer instance (if running)."""
    return _cloud_producer
