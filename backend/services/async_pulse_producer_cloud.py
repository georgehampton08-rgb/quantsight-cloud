"""
Cloud-Native Async Pulse Producer
==================================
Headless version for Cloud Run - writes ONLY to Firebase (no local cache/SSE).

Key Differences from Desktop Version:
  - NO local SQLite database
  - NO SSE cache broadcasting
  - NO local LivePulseCache
  - Writes directly to Firebase Firestore
  - Uses shared_core for all math (PIE, TS%, Usage)

Architecture:
  NBA API → AsyncPulseProducer → FirebaseAdminService → Firestore
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

# Import shared_core (platform-agnostic math)
import sys
from pathlib import Path
_root_path = Path(__file__).parent.parent.parent
if str(_root_path) not in sys.path:
    sys.path.insert(0, str(_root_path))

from shared_core.adapters.nba_api_adapter import (
    AsyncNBAApiAdapter,
    NormalizedBoxScore,
    get_nba_adapter,
    is_garbage_time
)
from shared_core.engines.pie_calculator import calculate_live_pie
from shared_core.calculators.advanced_stats import (
    calculate_true_shooting,
    calculate_effective_fg,
    calculate_in_game_usage
)

# Import Firebase Admin Service (cloud-only)
from services.firebase_admin_service import get_firebase_service

logger = logging.getLogger(__name__)

# Team Defense Cache (same as Desktop)
_TEAM_DEFENSE_CACHE: Dict[str, float] = {}
LEAGUE_AVG_DEF_RATING = 112.0


@dataclass
class LiveGameState:
    """Simplified game state for Firebase writes."""
    game_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    clock: str
    period: int
    status: str
    leaders: List[Dict]
    last_updated: str
    is_garbage_time: bool = False


class CloudAsyncPulseProducer:
    """
    Cloud-native pulse producer.
    Fetches NBA live data and writes ONLY to Firebase.
    """
    
    VERSION = "1.0.0-cloud"
    POLL_INTERVAL_SECONDS = 10
    
    def __init__(self):
        self._adapter = get_nba_adapter()
        self._firebase = get_firebase_service()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._update_count = 0
        self._last_update_duration: float = 0.0
        self._firebase_write_errors = 0
        
        if not self._firebase:
            logger.error("❌ Firebase not available - cloud producer will not function!")
        
        logger.info(f"🚀 CloudAsyncPulseProducer v{self.VERSION} initialized")
    
    async def start(self):
        """Start the producer loop."""
        if self._running:
            logger.warning("Producer already running")
            return
        
        if not self._firebase:
            logger.error("❌ Cannot start - Firebase not configured")
            return
        
        # TODO: Load team defense cache from Firestore or keep hardcoded
        await self._load_team_defense_cache()
        
        self._running = True
        self._task = asyncio.create_task(self._producer_loop())
        logger.info("🔥 Cloud pulse producer started")
    
    async def stop(self):
        """Stop the producer loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Cloud pulse producer stopped")
    
    async def _load_team_defense_cache(self):
        """
        Load team defense ratings.
        For Cloud Run, this could come from Firestore or be hardcoded.
        """
        global _TEAM_DEFENSE_CACHE
        
        # For now, use hardcoded NBA 2024-25 defense ratings
        # TODO: Load from Firestore collection 'team_defense'
        _TEAM_DEFENSE_CACHE = {
            'BOS': 106.5, 'OKC': 107.2, 'MEM': 108.1, 'HOU': 108.9, 
            'MIN': 109.4, 'NYK': 109.8, 'MIA': 110.2, 'LAC': 110.5,
            'CLE': 110.8, 'DEN': 111.1, 'MIL': 111.5, 'PHX': 111.8,
            'LAL': 112.2, 'DAL': 112.5, 'GSW': 112.9, 'SAC': 113.2,
            # ... (add all 30 teams for production)
        }
        logger.info(f"🛡️ Loaded {len(_TEAM_DEFENSE_CACHE)} team defense ratings")
    
    async def _producer_loop(self):
        """Main loop - runs every POLL_INTERVAL_SECONDS."""
        while self._running:
            try:
                start_time = time.perf_counter()
                await self._update_firebase_async()
                self._last_update_duration = time.perf_counter() - start_time
                
                self._update_count += 1
                if self._update_count % 6 == 0:  # Every minute
                    logger.info(
                        f"⚡ Update #{self._update_count}: "
                        f"{self._last_update_duration:.2f}s | "
                        f"Firebase errors: {self._firebase_write_errors}"
                    )
            except Exception as e:
                logger.error(f"❌ Update failed: {e}", exc_info=True)
            
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
    
    async def _update_firebase_async(self):
        """
        Fetch all live games and write to Firebase.
        NO local cache, NO SSE - pure Firebase writes.
        """
        if not self._adapter or not self._firebase:
            return
        
        try:
            # Step 1: Fetch scoreboard
            games = await self._adapter.fetch_scoreboard_async()
            if not games:
                logger.debug("No games found")
                return
            
            # Step 2: Get live game IDs
            live_game_ids = [g.game_id for g in games if g.status == 'LIVE']
            
            # Step 3: Fetch all boxscores concurrently
            boxscores: Dict[str, Optional[NormalizedBoxScore]] = {}
            if live_game_ids:
                boxscores = await self._adapter.fetch_all_live_boxscores_async(live_game_ids)
            
            # Step 4: Process and write each game to Firebase
            for game_info in games:
                if game_info.status != 'LIVE':
                    continue  # Only write live games
                
                game_id = game_info.game_id
                boxscore = boxscores.get(game_id)
                
                if not boxscore:
                    continue
                
                # Extract leaders
                leaders = self._extract_leaders(
                    boxscore,
                    home_team=game_info.home_team_tricode,
                    away_team=game_info.away_team_tricode
                )
                
                # Detect garbage time
                garbage_time_active = is_garbage_time(
                    period=game_info.period,
                    clock_str=game_info.clock,
                    home_score=game_info.home_score,
                    away_score=game_info.away_score
                )
                
                # Create game state
                game_state = LiveGameState(
                    game_id=game_id,
                    home_team=game_info.home_team_tricode,
                    away_team=game_info.away_team_tricode,
                    home_score=game_info.home_score,
                    away_score=game_info.away_score,
                    clock=game_info.status_text,
                    period=game_info.period,
                    status=game_info.status,
                    leaders=leaders[:10],
                    last_updated=datetime.now().isoformat(),
                    is_garbage_time=garbage_time_active
                )
                
                # Write to Firebase (blocking - we NEED this to succeed)
                success = await self._firebase.upsert_game_state(game_state)
                if not success:
                    self._firebase_write_errors += 1
                    logger.warning(f"⚠️ Firebase write failed for {game_id}")
        
        except Exception as e:
            logger.error(f"❌ Firebase update failed: {e}", exc_info=True)
    
    def _extract_leaders(
        self,
        boxscore: NormalizedBoxScore,
        home_team: str = '',
        away_team: str = ''
    ) -> List[Dict]:
        """
        Extract leaders using shared_core (no DB dependencies).
        Simplified version without rolling averages.
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
            
            # Calculate efficiency using shared_core
            ts_pct = round(calculate_true_shooting(player.pts, player.fga, player.fta), 4)
            efg_pct = round(calculate_effective_fg(player.fgm, player.fg3m, player.fga), 4)
            
            # Basic heat status (no rolling averages in cloud)
            heat_status = 'steady'
            if pie >= 0.25:
                heat_status = 'hot'
            elif pie < 0.05:
                heat_status = 'cold'
            
            # Matchup difficulty
            opponent_team = away_team if player.team_tricode == home_team else home_team
            opponent_def_rating = _TEAM_DEFENSE_CACHE.get(opponent_team, LEAGUE_AVG_DEF_RATING)
            
            if opponent_def_rating <= 108:
                matchup_difficulty = 'elite'
            elif opponent_def_rating >= 115:
                matchup_difficulty = 'soft'
            else:
                matchup_difficulty = 'average'
            
            # Contextual heat
            contextual_heat = heat_status
            if heat_status == 'hot' and matchup_difficulty == 'elite':
                contextual_heat = 'blazing'
            elif heat_status == 'cold' and matchup_difficulty == 'soft':
                contextual_heat = 'freezing'
            
            leaders.append({
                'player_id': player.player_id,
                'name': player.name,
                'team': player.team_tricode,
                'pie': pie,
                'plus_minus': player.plus_minus,
                'ts_pct': ts_pct,
                'efg_pct': efg_pct,
                'heat_status': contextual_heat,
                'efficiency_trend': 'steady',
                'opponent_team': opponent_team,
                'opponent_def_rating': round(opponent_def_rating, 1),
                'matchup_difficulty': matchup_difficulty,
                'has_usage_vacuum': False,  # Simplified for cloud
                'usage_bump': None,
                'stats': {
                    'pts': player.pts,
                    'reb': player.reb,
                    'ast': player.ast,
                    'stl': player.stl,
                    'blk': player.blk
                },
                'min': player.minutes
            })
        
        # Sort by PIE
        leaders.sort(key=lambda x: x['pie'], reverse=True)
        return leaders
    
    def get_status(self) -> Dict:
        """Get status for health checks."""
        return {
            "version": self.VERSION,
            "running": self._running,
            "update_count": self._update_count,
            "last_update_duration_seconds": round(self._last_update_duration, 3),
            "poll_interval_seconds": self.POLL_INTERVAL_SECONDS,
            "firebase_enabled": self._firebase is not None and self._firebase.enabled,
            "firebase_write_errors": self._firebase_write_errors
        }


# Global producer instance
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
    """Get the current cloud producer instance."""
    return _cloud_producer
