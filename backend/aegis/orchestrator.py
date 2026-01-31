"""
Aegis Orchestrator v3.1
=======================
Main orchestration layer for the Aegis-Inquisitor simulation pipeline.

Coordinates all components:
- Sovereign Router (data freshness)
- Vanguard-Forge (ensemble predictions)
- Vertex Monte Carlo (simulations)
- Confluence Scorer (confidence)
"""

import asyncio
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

# Core engines
from engines.ema_calculator import EMACalculator
from engines.vanguard_forge import VanguardForge
from engines.vertex_monte_carlo import VertexMonteCarloEngine
from engines.schedule_fatigue import ScheduleFatigueEngine
from engines.usage_vacuum import UsageVacuum
from engines.archetype_clusterer import ArchetypeClusterer

# Aegis components
from aegis.sovereign_router import SovereignRouter
from aegis.healer_protocol import HealerProtocol
from aegis.learning_ledger import LearningLedger
from aegis.confluence_scorer import ConfluenceScorer
from aegis.simulation_cache import SimulationCache

# Services
from services.truth_serum_filter import GarbageTimeFilter

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator"""
    n_simulations: int = 50_000
    cache_enabled: bool = True
    cache_ttl: int = 3600
    data_dir: Optional[Path] = None


@dataclass
class FullSimulationResult:
    """Complete simulation result with all metadata"""
    player_id: str
    opponent_id: str
    game_date: date
    
    # Projections
    floor: Dict[str, float]
    expected_value: Dict[str, float]
    ceiling: Dict[str, float]
    
    # Confidence
    confluence_score: float
    confluence_grade: str
    
    # Metadata
    archetype: str
    fatigue_modifier: float
    usage_boost: float
    execution_time_ms: float
    
    # NEW: Hidden Data Points
    schedule_context: Dict[str, Any]
    game_mode: Dict[str, Any]
    momentum: Dict[str, Any]
    defender_profile: Dict[str, Any]
    
    # Probabilities (if lines specified)
    hit_probabilities: Optional[Dict[str, float]] = None


class AegisOrchestrator:
    """
    Main orchestration layer.
    
    Coordinates all Aegis components for end-to-end simulation.
    Uses asyncio.gather for parallel data fetching (<500ms).
    """
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        
        # data_dir should be backend/data, not backend/aegis/data
        data_dir = self.config.data_dir or Path(__file__).parent.parent / "data"
        
        # Initialize all components
        self.ema = EMACalculator(alpha=0.15)
        self.forge = VanguardForge()
        self.monte_carlo = VertexMonteCarloEngine(
            n_simulations=self.config.n_simulations,
            ema_calculator=self.ema,
            vanguard_forge=self.forge
        )
        self.fatigue = ScheduleFatigueEngine()
        self.vacuum = UsageVacuum()
        self.archetype_classifier = ArchetypeClusterer()
        
        # Router and healer
        self.router = SovereignRouter(data_dir)
        self.healer = HealerProtocol(data_dir)
        
        # Feedback layer
        self.ledger = LearningLedger()
        self.scorer = ConfluenceScorer(learning_ledger=self.ledger)
        self.garbage_filter = GarbageTimeFilter()
        
        # Cache
        if self.config.cache_enabled:
            self.cache = SimulationCache(ttl_seconds=self.config.cache_ttl)
        else:
            self.cache = None
        
        logger.info("[ORCHESTRATOR] Initialized all components")
    
    async def run_simulation(
        self,
        player_id: str,
        opponent_id: str,
        game_date: Optional[date] = None,
        lines: Optional[Dict[str, float]] = None,
        injuries: Optional[List[Dict]] = None,
        force_fresh: bool = False
    ) -> FullSimulationResult:
        """
        Run complete simulation pipeline.
        
        Steps:
        1. Check cache
        2. Parallel data fetch via asyncio.gather
        3. Truth-Serum filter
        4. EMA calculation
        5. Modifiers (fatigue, friction, usage)
        6. Monte Carlo simulation
        7. Confluence scoring
        8. Cache result
        9. Save to ledger
        
        Args:
            player_id: NBA player ID
            opponent_id: Opponent team ID
            game_date: Date of game (default: today)
            lines: Optional stat lines for hit probability
            injuries: Optional list of injured teammates
            force_fresh: Skip cache
            
        Returns:
            FullSimulationResult with projections and metadata
        """
        import time
        start = time.perf_counter()
        
        game_date = game_date or date.today()
        
        # Step 1: Check cache
        if self.cache and not force_fresh:
            cached = self.cache.get(player_id, opponent_id, date=game_date.isoformat())
            if cached:
                logger.info(f"[ORCHESTRATOR] Cache hit for {player_id}")
                return cached
        
        # Step 2: Parallel data fetch
        data = await self._parallel_fetch(player_id, opponent_id, game_date)
        
        # Step 3: Truth-Serum filter
        game_logs = data.get('game_logs', [])
        true_avgs = self.garbage_filter.calculate_true_average(player_id, game_logs)
        
        # Step 4: EMA calculation
        ema_stats = self.ema.calculate(game_logs)
        
        # Step 5: Modifiers
        # Fatigue
        schedule = data.get('schedule', {})
        fatigue_result = self.fatigue.calculate_fatigue(
            game_date,
            schedule.get('is_road', False),
            game_logs[-10:] if game_logs else []
        )
        
        # Archetype friction
        player_stats = data.get('player_stats', {})
        archetype_result = self.archetype_classifier.classify(player_stats)
        team_defense = data.get('team_defense', {})
        friction = self.archetype_classifier.get_friction_for_team(
            archetype_result.archetype, team_defense
        )
        
        # Usage vacuum
        usage_boost = 0.0
        if injuries:
            usage_boost = self.vacuum.get_boost_for_player(player_id, injuries)
        
        # NEW: Calculate volatility factor (coefficient of variation)
        # High CV = volatile player = wider confidence bands
        volatility_factor = 1.0
        if game_logs and len(game_logs) >= 5:
            pts_values = [g.get('pts') or g.get('points') or 0 for g in game_logs[:15]]
            if pts_values:
                pts_mean = sum(pts_values) / len(pts_values)
                if pts_mean > 0:
                    pts_std = (sum((x - pts_mean) ** 2 for x in pts_values) / len(pts_values)) ** 0.5
                    cv = pts_std / pts_mean
                    # Scale CV to volatility factor (0.8 to 1.4 range)
                    # CV of 0.2 = consistent (vol=0.8), CV of 0.5 = volatile (vol=1.4)
                    volatility_factor = 0.8 + (cv * 1.2)
                    volatility_factor = max(0.7, min(1.5, volatility_factor))
                    logger.info(f"[ORCHESTRATOR] Volatility: CV={cv:.2f}, factor={volatility_factor:.2f}")
        
        # NEW: Calculate minutes modifier
        # If player expected to play fewer/more minutes, scale projection
        minutes_modifier = 1.0
        minutes_ema = ema_stats.get('minutes_ema', 0)
        if minutes_ema > 0:
            # Use 32 as baseline minutes for starters
            baseline_minutes = 32.0
            minutes_modifier = minutes_ema / baseline_minutes
            # Clamp to reasonable range (0.5 to 1.3)
            minutes_modifier = max(0.5, min(1.3, minutes_modifier))
            logger.info(f"[ORCHESTRATOR] Minutes: EMA={minutes_ema:.1f}, modifier={minutes_modifier:.2f}")
        
        # Step 6: Monte Carlo simulation
        pace_factor = data.get('pace_factor', 1.0)
        
        sim_result = self.monte_carlo.run_simulation(
            ema_stats=ema_stats,
            pace_factor=pace_factor,
            friction=friction,
            fatigue_modifier=fatigue_result.modifier,
            usage_boost=usage_boost,
            volatility_factor=volatility_factor,
            minutes_modifier=minutes_modifier
        )
        
        # Step 7: Confluence scoring
        forge_result = self.forge.predict_from_stats(ema_stats, pace_factor, friction)
        model_preds = {}
        if forge_result and 'points' in forge_result:
            model_preds = forge_result['points'].model_predictions
        
        confluence = self.scorer.calculate(
            model_predictions=model_preds,
            sample_size=len(game_logs),
            player_id=player_id
        )
        
        # Calculate hit probabilities if lines provided
        hit_probs = None
        if lines and sim_result.projection.simulations:
            hit_probs = self.monte_carlo.get_hit_probabilities(
                sim_result.projection.simulations,
                lines
            )
        
        execution_time = (time.perf_counter() - start) * 1000
        
        # Compile new hidden data objects
        schedule_ctx = {
            "is_road": schedule.get('is_road', False),
            "is_b2b": schedule.get('is_b2b', False),
            "days_rest": schedule.get('days_rest', 2),
            "modifier": fatigue_result.modifier
        }
        
        # Game Mode: Probability of blowout vs clutch
        # Derived from Monte Carlo variance
        g_mode = {
            "blowout_pct": 0.15, # Placeholder: would calculate from sim distribution
            "clutch_pct": 0.25,
            "mode": "standard"
        }
        
        # Momentum: Streaks (placeholder as actual Crucible run would set this)
        mom = {
            "consecutive_makes": 0,
            "consecutive_misses": 0,
            "hot_streak": False,
            "cold_streak": False
        }
        
        # Defender Profile: Friction data
        def_prof = {
            "primary_defender": "Unknown",
            "dfg_pct": team_defense.get('defensive_rating', 110.0), # Placeholder
            "pct_plusminus": 0.0,
            "rating": "average"
        }

        # Build result
        result = FullSimulationResult(
            player_id=player_id,
            opponent_id=opponent_id,
            game_date=game_date,
            floor=sim_result.projection.floor_20th,
            expected_value=sim_result.projection.expected_value,
            ceiling=sim_result.projection.ceiling_80th,
            confluence_score=confluence.score,
            confluence_grade=confluence.grade,
            archetype=archetype_result.archetype,
            fatigue_modifier=fatigue_result.modifier,
            usage_boost=usage_boost,
            execution_time_ms=round(execution_time, 1),
            schedule_context=schedule_ctx,
            game_mode=g_mode,
            momentum=mom,
            defender_profile=def_prof,
            hit_probabilities=hit_probs
        )
        
        # Step 8: Cache result
        if self.cache:
            self.cache.set(player_id, opponent_id, result, date=game_date.isoformat())
        
        # Step 9: Save to ledger
        self.ledger.record_projection(
            player_id=player_id,
            opponent_id=opponent_id,
            game_date=game_date,
            projection=sim_result.projection.to_dict(),
            confluence_score=confluence.score,
            model_weights=self.forge.weights if self.forge else None,
            execution_time_ms=execution_time
        )
        
        logger.info(f"[ORCHESTRATOR] Completed in {execution_time:.0f}ms - "
                   f"Confluence: {confluence.score} ({confluence.grade})")
        
        return result
    
    async def _parallel_fetch(
        self,
        player_id: str,
        opponent_id: str,
        game_date: date
    ) -> Dict[str, Any]:
        """
        Parallel data fetching using asyncio.gather.
        Target: <200ms for all fetches combined.
        """
        results = await asyncio.gather(
            self._fetch_player_data(player_id),
            self._fetch_team_defense(opponent_id),
            self._fetch_schedule_context(player_id, game_date),
            self._fetch_pace_data(player_id, opponent_id),
            return_exceptions=True
        )
        
        # Unpack results
        player_data, team_defense, schedule, pace_data = results
        
        # Handle exceptions gracefully
        if isinstance(player_data, Exception):
            logger.warning(f"[ORCHESTRATOR] Player fetch failed: {player_data}")
            player_data = {'game_logs': [], 'player_stats': {}}
        
        if isinstance(team_defense, Exception):
            team_defense = {}
        
        if isinstance(schedule, Exception):
            schedule = {}
        
        if isinstance(pace_data, Exception):
            pace_data = {'pace_factor': 1.0}
        
        return {
            'game_logs': player_data.get('game_logs', []),
            'player_stats': player_data.get('player_stats', {}),
            'team_defense': team_defense if not isinstance(team_defense, Exception) else {},
            'schedule': schedule if not isinstance(schedule, Exception) else {},
            'pace_factor': pace_data.get('pace_factor', 1.0) if not isinstance(pace_data, Exception) else 1.0
        }
    
    async def _fetch_player_data(self, player_id: str) -> Dict:
        """Fetch player game logs and stats"""
        result = await self.router.route_request(player_id)
        return {
            'game_logs': result.get('data', []),
            'player_stats': {}  # Would aggregate from game_logs
        }
    
    async def _fetch_team_defense(self, team_id: str) -> Dict:
        """Fetch opponent defensive metrics"""
        try:
            from services.defense_matrix import DefenseMatrix
            # Use static method - get_profile returns dict with paoa per position
            profile = DefenseMatrix.get_profile(team_id)
            return {
                'defensive_rating': profile.get('def_rating', 110.0) or 110.0,
                'primary_archetype': 'Balanced',
                'paoa': {
                    'PG': profile.get('vs_PG', 0.0),
                    'SG': profile.get('vs_SG', 0.0),
                    'SF': profile.get('vs_SF', 0.0),
                    'PF': profile.get('vs_PF', 0.0),
                    'C': profile.get('vs_C', 0.0)
                },
                'available': profile.get('available', False)
            }
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Defense Matrix lookup failed: {e}")
            return {'defensive_rating': 110.0, 'primary_archetype': 'Balanced'}
    
    async def _fetch_schedule_context(self, player_id: str, game_date: date) -> Dict:
        """Fetch schedule context for fatigue calculation - DYNAMICALLY calculated"""
        try:
            import csv
            from datetime import datetime
            
            # Get player's recent games from game_logs.csv
            data_dir = self.config.data_dir or Path(__file__).parent.parent / "data"
            csv_path = data_dir / "game_logs.csv"
            
            if not csv_path.exists():
                logger.warning(f"[ORCHESTRATOR] game_logs.csv not found at {csv_path}")
                return {'is_road': False, 'is_b2b': False, 'days_rest': 3}
            
            # Find player's most recent game dates
            player_game_dates = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Handle both uppercase and lowercase column names
                    row_player_id = row.get('PLAYER_ID') or row.get('player_id', '')
                    if str(row_player_id) == str(player_id):
                        date_str = row.get('GAME_DATE') or row.get('game_date', '')
                        if date_str:
                            try:
                                # Handle multiple date formats
                                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d']:
                                    try:
                                        gd = datetime.strptime(date_str[:10], fmt).date()
                                        player_game_dates.append(gd)
                                        break
                                    except ValueError:
                                        continue
                            except Exception:
                                continue
            
            if not player_game_dates:
                logger.info(f"[ORCHESTRATOR] No game logs found for player {player_id}")
                return {'is_road': False, 'is_b2b': False, 'days_rest': 7}
            
            # Sort and get most recent game
            player_game_dates.sort(reverse=True)
            last_game = player_game_dates[0]
            
            # Calculate days rest from GAME DATE (not today)
            days_rest = (game_date - last_game).days
            
            # Check for back-to-back (played yesterday)
            is_b2b = days_rest <= 1
            
            # Check for 3-in-4 pattern
            games_in_4_days = sum(1 for d in player_game_dates[:10] if (game_date - d).days <= 4)
            
            logger.info(f"[ORCHESTRATOR] Schedule context for {player_id}: last_game={last_game}, days_rest={days_rest}, is_b2b={is_b2b}")
            
            return {
                'is_road': False,  # Would need schedule API for accurate road/home
                'is_b2b': is_b2b,
                'days_rest': max(0, days_rest),
                'last_game_date': last_game.isoformat(),
                'games_in_4_days': games_in_4_days
            }
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Schedule context fetch failed: {e}")
            return {'is_road': False, 'is_b2b': False, 'days_rest': 3}
    
    async def _fetch_pace_data(self, player_id: str, opponent_id: str) -> Dict:
        """Fetch pace data for normalization"""
        try:
            from services.pace_engine import PaceEngine
            # Use static method to get matchup pace info
            # First need to get team IDs - for now return multiplier directly
            pace_info = PaceEngine.get_matchup_pace_info(player_id, opponent_id)
            return {
                'pace_factor': pace_info.get('multiplier', 1.0),
                'team_pace': pace_info.get('team1_pace', 99.5) or 99.5,
                'opponent_pace': pace_info.get('team2_pace', 99.5) or 99.5,
                'available': pace_info.get('available', False)
            }
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Pace Engine lookup failed: {e}")
            return {
                'pace_factor': 1.0,
                'team_pace': 99.5,
                'opponent_pace': 99.5
            }
    
    def get_system_health(self) -> Dict:
        """Return health status of all components"""
        return {
            'router': 'healthy',
            'forge': self.forge.get_model_status() if self.forge else 'unavailable',
            'cache': self.cache.get_metrics() if self.cache else 'disabled',
            'ledger': 'connected'
        }
