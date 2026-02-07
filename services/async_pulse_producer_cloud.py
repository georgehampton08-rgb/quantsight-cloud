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

# Shared core imports
# Docker layout: /app/shared_core/ (same level as services/)
# Local dev layout: ../shared_core relative to backend/
try:
    _shared_core_docker = _backend_path / 'shared_core'       # /app/shared_core (Docker)
    _shared_core_local = _backend_path.parent / 'shared_core'  # sibling dir (local dev)
    
    if _shared_core_docker.exists():
        sys.path.insert(0, str(_shared_core_docker))
    elif _shared_core_local.exists():
        sys.path.insert(0, str(_shared_core_local))
    else:
        # Fallback: try both
        sys.path.insert(0, str(_shared_core_docker))
        sys.path.insert(0, str(_shared_core_local))
    
    from adapters.nba_api_adapter import (
        AsyncNBAApiAdapter,
        NormalizedBoxScore,
        get_nba_adapter,
        is_garbage_time
    )
    from engines.pie_calculator import calculate_live_pie, calculate_pie_percentile
    from calculators.advanced_stats import (
        calculate_true_shooting, 
        calculate_effective_fg,
        calculate_in_game_usage,
        calculate_assist_rate,
        calculate_per_36
    )
    from engines.fatigue_engine import get_in_game_fatigue_penalty
    from calculators.matchup_grades import (
        calculate_matchup_grade,
        calculate_target_fade_classification,
        calculate_confidence_score
    )
    ADAPTER_AVAILABLE = True
    logging.info("✅ Shared core loaded successfully")
except ImportError as e:
    ADAPTER_AVAILABLE = False
    logging.error(f"❌ Shared core not available: {e}")

# Firebase service
from services.firebase_admin_service import get_firebase_service

# Season baselines service (Firestore-backed, replaces dead cloud_sql_data_service)
from services.season_baseline_service import (
    get_team_defense_rating,
    get_player_season_usage,
    get_player_rolling_ts,
    get_player_season_ppg,
    calculate_usage_vacuum,
    calculate_heat_scale,
    LEAGUE_AVG_DEF_RATING,
    warm_cache as warm_baseline_cache,
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
        
        # Warm season baseline cache at startup
        try:
            warm_baseline_cache()
        except Exception as e:
            logger.warning(f"Could not warm baseline cache at startup: {e}")
        
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
                
                # Phase 3: Game-level intelligence
                score_margin = abs(game_info.home_score - game_info.away_score)
                game_phase = self._determine_game_phase(
                    period=game_info.period,
                    score_margin=score_margin,
                    is_garbage_time=garbage_time_active
                )
                pace_multiplier = self._calculate_pace_multiplier(
                    game_info.home_team_tricode,
                    game_info.away_team_tricode
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
                    # Phase 3 additions
                    'game_phase': game_phase,
                    'score_margin': score_margin,
                    'pace_multiplier': pace_multiplier,
                    'leaders': leaders[:15]  # Top 15 for this game
                }
                
                # Write to Firebase (non-blocking)
                asyncio.create_task(self._firebase.upsert_game_state(game_data))
            
            # Step 5: Update global leaderboard (top 15 across all games)
            if all_leaders:
                all_leaders.sort(key=lambda x: x['pie'], reverse=True)
                top_15_leaders = all_leaders[:15]
                
                asyncio.create_task(self._firebase.upsert_live_leaders(top_15_leaders))
            
        except Exception as e:
            logger.error(f"❌ Firebase update failed: {e}", exc_info=True)
    
    def _parse_minutes(self, minutes_str: str) -> float:
        """Parse MM:SS or PT format minutes to float."""
        try:
            if ':' in minutes_str:
                parts = minutes_str.split(':')
                return float(parts[0]) + float(parts[1]) / 60
            return float(minutes_str) if minutes_str else 0.0
        except (ValueError, IndexError):
            return 0.0

    def _extract_leaders_from_normalized(
        self, 
        boxscore: 'NormalizedBoxScore',
        home_team: str = '',
        away_team: str = ''
    ) -> List[Dict]:
        """
        Extract per-player analytics from normalized boxscore.
        Phase 2: Enhanced with PIE percentile, assist rate, fatigue,
        per-36, +/- context, and Firestore-backed baselines.
        """
        leaders = []
        game_info = boxscore.game_info
        
        # ─── Precompute team-level stats once per extraction ─────────────
        home_stats = boxscore.get_team_stats(home_team) if home_team else {}
        away_stats = boxscore.get_team_stats(away_team) if away_team else {}
        
        # Real PIE game denominator from both teams
        game_pie_total = self._calculate_game_pie_denominator(home_stats, away_stats)
        
        # Elapsed game minutes for usage rate
        elapsed_minutes = min(game_info.period * 12, 48) if game_info.period else 12
        
        for player in boxscore.all_active_players():
            minutes_played = self._parse_minutes(player.minutes)
            opponent_team = away_team if player.team_tricode == home_team else home_team
            team_stats = home_stats if player.team_tricode == home_team else away_stats
            
            # ═══ CORE METRICS ═══════════════════════════════════════════
            
            # PIE — now with real game denominator
            pie = calculate_live_pie(
                pts=player.pts, fgm=player.fgm, fga=player.fga,
                ftm=player.ftm, fta=player.fta,
                oreb=player.oreb, dreb=player.dreb,
                ast=player.ast, stl=player.stl, blk=player.blk,
                pf=player.pf, tov=player.tov,
                game_total_estimate=game_pie_total
            )
            
            # PIE percentile (1-100 league ranking)
            pie_percentile = calculate_pie_percentile(pie)
            
            # Efficiency
            ts_pct = round(calculate_true_shooting(player.pts, player.fga, player.fta), 4)
            efg_pct = round(calculate_effective_fg(player.fgm, player.fg3m, player.fga), 4)
            
            # ═══ +/- CONTEXT ════════════════════════════════════════════
            pm_per_min = round(player.plus_minus / minutes_played, 3) if minutes_played > 0 else 0.0
            if pm_per_min > 0.5:
                pm_label = 'dominant'
            elif pm_per_min > 0:
                pm_label = 'positive'
            elif pm_per_min > -0.5:
                pm_label = 'negative'
            else:
                pm_label = 'liability'
            
            # ═══ ADVANCED METRICS ═══════════════════════════════════════
            
            # Assist rate
            ast_rate = 0.0
            try:
                if team_stats and minutes_played > 0:
                    ast_rate = round(calculate_assist_rate(
                        ast=player.ast,
                        minutes=minutes_played,
                        team_fgm=team_stats.get('fgm', 0),
                        player_fgm=player.fgm,
                        team_minutes=elapsed_minutes * 5
                    ), 4)
            except Exception:
                pass
            
            # In-game fatigue penalty
            fatigue_penalty = 0.0
            try:
                fatigue_penalty = round(get_in_game_fatigue_penalty(
                    continuous_minutes=minutes_played
                ), 4)
            except Exception:
                pass
            
            # Per-36 normalization
            pts_per_36 = round(calculate_per_36(player.pts, minutes_played), 1)
            reb_per_36 = round(calculate_per_36(player.reb, minutes_played), 1)
            
            # ═══ USAGE & VACUUM ═════════════════════════════════════════
            usage_rate = None
            usage_vacuum = False
            
            try:
                if team_stats and ADAPTER_AVAILABLE and minutes_played > 0:
                    usage_rate = round(calculate_in_game_usage(
                        fga=player.fga,
                        fta=player.fta,
                        tov=player.tov,
                        minutes=minutes_played,
                        team_fga=team_stats.get('fga', 0),
                        team_fta=team_stats.get('fta', 0),
                        team_tov=team_stats.get('tov', 0),
                        elapsed_game_minutes=elapsed_minutes
                    ), 2)
                    
                    season_avg_usage = get_player_season_usage(player.player_id)
                    usage_vacuum = calculate_usage_vacuum(
                        usage_rate / 100.0 if usage_rate else 0, 
                        season_avg_usage
                    )
            except Exception as e:
                logger.debug(f"Usage calculation failed for {player.name}: {e}")
            
            # ═══ MATCHUP & DEFENSE ══════════════════════════════════════
            opponent_def_rating, matchup_difficulty = get_team_defense_rating(opponent_team)
            
            # ═══ HEAT SCALE ═════════════════════════════════════════════
            season_avg_ts = get_player_rolling_ts(player.player_id)
            heat_scale = calculate_heat_scale(ts_pct, season_avg_ts)
            
            # ═══ GARBAGE TIME ═══════════════════════════════════════════
            player_is_garbage_time = is_garbage_time(
                period=game_info.period,
                clock_str=game_info.clock,
                home_score=game_info.home_score,
                away_score=game_info.away_score
            )
            
            # ═══ BETTING SIGNALS (Phase 4) ═══════════════════════════════
            betting_signals = {}
            try:
                season_ppg = get_player_season_ppg(player.player_id)
                
                # Project total points from current pace
                expected_minutes = 36.0  # Typical starter minutes
                projected_pts = round(pts_per_36 * (expected_minutes / 36), 1)
                
                # TARGET/FADE classification
                tf_class, tf_reason = calculate_target_fade_classification(
                    projection=projected_pts,
                    threshold=season_ppg
                )
                
                # Defense friction modifier (how much harder/easier the matchup is)
                defense_friction = (LEAGUE_AVG_DEF_RATING - opponent_def_rating) / 100.0
                
                # Matchup grade (A-F)
                grade, grade_score = calculate_matchup_grade(
                    projected_points=projected_pts,
                    matchup_bonus=0.0,
                    friction_modifier=defense_friction
                )
                
                # Confidence score
                confidence, conf_breakdown = calculate_confidence_score(
                    sample_size=0,  # No H2H data yet
                    h2h_weight=0.0,
                    form_clarity=0.05 if heat_scale == 'hot' else (0.02 if heat_scale == 'steady' else 0.0),
                    environment_balance=0.05
                )
                
                # Delta vs season average
                delta_vs_season = round(projected_pts - season_ppg, 1) if season_ppg > 0 else 0.0
                
                betting_signals = {
                    'target_fade': tf_class,
                    'target_fade_reason': tf_reason,
                    'matchup_grade': grade,
                    'matchup_score': round(grade_score, 1),
                    'confidence': round(confidence, 3),
                    'projected_pts': projected_pts,
                    'season_ppg': season_ppg,
                    'vs_season_avg': delta_vs_season,
                }
            except Exception as e:
                logger.debug(f"Betting signal calculation failed for {player.name}: {e}")
            
            # ═══ BUILD LEADER ENTRY ═════════════════════════════════════
            leaders.append({
                # Identity
                'player_id': player.player_id,
                'name': player.name,
                'team': player.team_tricode,
                'opponent': opponent_team,
                
                # Core metrics (improved)
                'pie': pie,
                'pie_percentile': pie_percentile,
                'ts_pct': ts_pct,
                'efg_pct': efg_pct,
                'plus_minus': player.plus_minus,
                'pm_per_min': pm_per_min,
                'pm_label': pm_label,
                'minutes': player.minutes,
                
                # Advanced metrics (new)
                'ast_rate': ast_rate,
                'fatigue_penalty': fatigue_penalty,
                'pts_per_36': pts_per_36,
                'reb_per_36': reb_per_36,
                
                # Context signals (now real from Firestore)
                'usage_rate': usage_rate,
                'usage_vacuum': usage_vacuum,
                'opponent_def_rating': opponent_def_rating,
                'matchup_difficulty': matchup_difficulty,
                'season_avg_ts': season_avg_ts,
                'heat_scale': heat_scale,
                
                # Betting signals (Phase 4 — frontend-facing)
                'betting_signals': betting_signals,
                
                # Game state
                'is_garbage_time': player_is_garbage_time,
                
                # Raw stats (expanded)
                'stats': {
                    'pts': player.pts,
                    'reb': player.reb,
                    'ast': player.ast,
                    'stl': player.stl,
                    'blk': player.blk,
                    'fg3m': player.fg3m,
                    'fgm': player.fgm,
                    'fga': player.fga,
                    'ftm': player.ftm,
                    'fta': player.fta,
                    'oreb': player.oreb,
                    'dreb': player.dreb,
                    'pf': player.pf,
                    'tov': player.tov
                }
            })
        
        # Sort by PIE descending
        leaders.sort(key=lambda x: x['pie'], reverse=True)
        return leaders
    
    @staticmethod
    def _calculate_game_pie_denominator(home_stats: dict, away_stats: dict) -> float:
        """Calculate real PIE game denominator from both teams' combined stats."""
        total = 0.0
        for stats in [home_stats, away_stats]:
            if not stats:
                continue
            pts = stats.get('pts', 0) or 0
            fgm = stats.get('fgm', 0) or 0
            fga = stats.get('fga', 0) or 0
            ftm = stats.get('ftm', 0) or 0
            fta = stats.get('fta', 0) or 0
            tov = stats.get('tov', 0) or 0
            total += (pts + fgm + ftm - fga - fta - tov)
        
        # Minimum 10 to prevent division issues early in games
        return max(total, 10.0)
    
    @staticmethod
    def _determine_game_phase(period: int, score_margin: int, is_garbage_time: bool) -> str:
        """
        Classify the current game phase for contextual decisions.
        
        Returns: 'clutch', 'blowout', 'garbage', or 'normal'
        """
        if is_garbage_time:
            return 'garbage'
        
        # Clutch: Q4 or OT with margin <= 5
        if period >= 4 and score_margin <= 5:
            return 'clutch'
        
        # Blowout: any period with margin >= 20
        if score_margin >= 20:
            return 'blowout'
        
        return 'normal'
    
    @staticmethod
    def _calculate_pace_multiplier(home_team: str, away_team: str) -> float:
        """
        Calculate game pace multiplier from team baselines.
        Uses average of both teams' pace / league average.
        
        Returns: ~1.0 for average pace, >1.0 for fast, <1.0 for slow.
        """
        try:
            from services.season_baseline_service import get_team_pace
            
            home_pace = get_team_pace(home_team)
            away_pace = get_team_pace(away_team)
            avg_pace = (home_pace + away_pace) / 2
            
            # Normalize to league average (100.0 possessions per 48 min)
            return round(avg_pace / 100.0, 3)
        except Exception:
            return 1.0
    
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
