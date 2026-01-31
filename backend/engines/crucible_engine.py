"""
Crucible Simulation Engine v4.0
================================
Dynamic Possession-by-Possession Game Simulator

Features:
- 48-minute clock with ~100 possessions per team
- Markov Chain state transitions
- Foul trouble auto-benching
- Fatigue decay (-1% per 8 min continuous)
- Closer buff in clutch situations
- Blowout valve (empty bench at 18+ pts in Q4)
- Heat check momentum shifts
- Learning Ledger integration for next-day audit

This replaces the static Monte Carlo sampler with a realistic
game flow that accounts for tactical situations.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)

# Import Defense Friction Module for individual DFG% integration
try:
    from engines.defense_friction_module import get_defense_friction_module, DefenderProfile
    HAS_FRICTION_MODULE = True
except ImportError:
    HAS_FRICTION_MODULE = False
    logger.warning("DefenseFrictionModule not available - using flat modifiers")

# Import Automated Injury Worker for dynamic injury simulation
try:
    from services.automated_injury_worker import get_injury_worker
    HAS_INJURY_WORKER = True
except ImportError:
    HAS_INJURY_WORKER = False
    logger.warning("Injury worker not available")


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class PlayType(Enum):
    """Types of offensive plays"""
    TWO_POINT_ATTEMPT = "2PA"
    THREE_POINT_ATTEMPT = "3PA"
    FREE_THROW = "FT"
    TURNOVER = "TOV"
    PASS = "PASS"
    DRIVE = "DRIVE"


class GamePhase(Enum):
    """Game phases that affect strategy"""
    NORMAL = "normal"
    CLUTCH = "clutch"           # Score diff < 5, last 5 min
    BLOWOUT_WINNING = "blowout_winning"
    BLOWOUT_LOSING = "blowout_losing"
    GARBAGE_TIME = "garbage"


# Quarter length in seconds
QUARTER_LENGTH = 720  # 12 minutes
POSSESSION_LENGTH = 14  # Average seconds per possession
FATIGUE_PENALTY_INTERVAL = 480  # 8 minutes in seconds
BLOWOUT_THRESHOLD = 18  # Point differential for blowout
CLUTCH_TIME_THRESHOLD = 300  # Last 5 minutes
CLUTCH_SCORE_THRESHOLD = 5  # Within 5 points


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PlayerState:
    """Live state for a single player during simulation"""
    player_id: str
    name: str
    archetype: str  # 'Scorer', 'Playmaker', 'Slasher', etc.
    
    # Base stats (from EMA)
    base_fg2_pct: float = 0.52
    base_fg3_pct: float = 0.38
    base_ft_pct: float = 0.80
    base_usage: float = 0.20
    
    # Live game state
    points: int = 0
    rebounds: int = 0
    assists: int = 0
    threes_made: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fouls: int = 0
    minutes_played: float = 0.0
    
    # Tactical state
    consecutive_misses: int = 0
    consecutive_makes: int = 0
    is_on_court: bool = True
    benched_until_quarter: int = 0  # 0 = not benched
    continuous_floor_time: float = 0.0  # Seconds without rest
    last_rest_time: float = 0.0
    
    # Modifiers (dynamic)
    shot_probability_mod: float = 0.0  # -0.15 after cold streak
    pass_probability_mod: float = 0.0  # +0.15 after cold streak
    usage_mod: float = 0.0  # Closer buff, injury vacuum, etc.
    fatigue_penalty: float = 0.0  # -1% per 8 min continuous play


@dataclass
class TeamState:
    """Live state for a team during simulation"""
    team_id: str
    team_name: str
    players: List[PlayerState] = field(default_factory=list)
    starters: List[str] = field(default_factory=list)  # Player IDs
    
    score: int = 0
    timeouts_remaining: int = 7
    team_fouls: int = 0
    
    # Calculated dynamically
    def get_active_players(self) -> List[PlayerState]:
        return [p for p in self.players if p.is_on_court]
    
    def get_player(self, player_id: str) -> Optional[PlayerState]:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None


@dataclass
class LiveGameState:
    """Complete game state at any moment"""
    # Clock
    quarter: int = 1
    clock: float = QUARTER_LENGTH  # Seconds remaining in quarter
    
    # Teams
    home_team: Optional[TeamState] = None
    away_team: Optional[TeamState] = None
    possession: str = "home"  # 'home' or 'away'
    
    # Game flow
    phase: GamePhase = GamePhase.NORMAL
    possession_count: int = 0
    
    # Narrative tracking (for Learning Ledger)
    game_script: List[Dict] = field(default_factory=list)
    key_events: List[str] = field(default_factory=list)
    
    @property
    def score_differential(self) -> int:
        """Positive = home leading"""
        if self.home_team and self.away_team:
            return self.home_team.score - self.away_team.score
        return 0
    
    @property
    def game_time_elapsed(self) -> float:
        """Total seconds elapsed in game"""
        completed_quarters = (self.quarter - 1) * QUARTER_LENGTH
        current_quarter_elapsed = QUARTER_LENGTH - self.clock
        return completed_quarters + current_quarter_elapsed
    
    @property
    def is_clutch_time(self) -> bool:
        """Final 5 minutes with close score"""
        if self.quarter < 4:
            return False
        return self.clock <= CLUTCH_TIME_THRESHOLD and abs(self.score_differential) <= CLUTCH_SCORE_THRESHOLD


@dataclass 
class CrucibleResult:
    """Result of a single game simulation"""
    home_team_stats: Dict[str, Dict]  # player_id -> stats
    away_team_stats: Dict[str, Dict]
    final_score: Tuple[int, int]  # (home, away)
    game_script: List[Dict]
    key_events: List[str]
    execution_time_ms: float
    was_blowout: bool
    was_clutch: bool


# =============================================================================
# MARKOV CHAIN LOGIC
# =============================================================================

class MarkovPlaySelector:
    """
    Markov Chain logic for play selection.
    
    State transitions based on:
    - Player archetype
    - Game situation (clutch, blowout)
    - Recent performance (hot/cold streak)
    - Fatigue level
    """
    
    # Base transition probabilities by archetype
    ARCHETYPE_BASE_PROBS = {
        'Scorer': {
            PlayType.TWO_POINT_ATTEMPT: 0.25,
            PlayType.THREE_POINT_ATTEMPT: 0.20,
            PlayType.DRIVE: 0.20,
            PlayType.PASS: 0.25,
            PlayType.TURNOVER: 0.10,
        },
        'Playmaker': {
            PlayType.TWO_POINT_ATTEMPT: 0.15,
            PlayType.THREE_POINT_ATTEMPT: 0.15,
            PlayType.DRIVE: 0.15,
            PlayType.PASS: 0.45,
            PlayType.TURNOVER: 0.10,
        },
        'Slasher': {
            PlayType.TWO_POINT_ATTEMPT: 0.20,
            PlayType.THREE_POINT_ATTEMPT: 0.10,
            PlayType.DRIVE: 0.35,
            PlayType.PASS: 0.25,
            PlayType.TURNOVER: 0.10,
        },
        'Three-and-D': {
            PlayType.TWO_POINT_ATTEMPT: 0.15,
            PlayType.THREE_POINT_ATTEMPT: 0.30,
            PlayType.DRIVE: 0.10,
            PlayType.PASS: 0.35,
            PlayType.TURNOVER: 0.10,
        },
        'Rim Protector': {
            PlayType.TWO_POINT_ATTEMPT: 0.30,
            PlayType.THREE_POINT_ATTEMPT: 0.05,
            PlayType.DRIVE: 0.10,
            PlayType.PASS: 0.45,
            PlayType.TURNOVER: 0.10,
        },
        'Balanced': {
            PlayType.TWO_POINT_ATTEMPT: 0.20,
            PlayType.THREE_POINT_ATTEMPT: 0.15,
            PlayType.DRIVE: 0.20,
            PlayType.PASS: 0.35,
            PlayType.TURNOVER: 0.10,
        },
    }
    
    def get_play_probabilities(
        self,
        player: PlayerState,
        game_state: LiveGameState
    ) -> Dict[PlayType, float]:
        """
        Calculate play probabilities for a player given current game state.
        Applies Markov adjustments based on:
        - Cold streak (3+ misses → -15% shot, +15% pass)
        - Hot streak (3+ makes → +10% shot, -5% pass) 
        - Clutch time (Scorers +15% usage)
        - Fatigue
        """
        archetype = player.archetype if player.archetype in self.ARCHETYPE_BASE_PROBS else 'Balanced'
        probs = self.ARCHETYPE_BASE_PROBS[archetype].copy()
        
        # Cold streak adjustment: 3+ misses → pass more
        if player.consecutive_misses >= 3:
            shot_reduction = 0.15
            probs[PlayType.TWO_POINT_ATTEMPT] -= shot_reduction / 2
            probs[PlayType.THREE_POINT_ATTEMPT] -= shot_reduction / 2
            probs[PlayType.PASS] += shot_reduction
            
        # Hot streak / Heat Check: 3+ makes → shoot more
        elif player.consecutive_makes >= 3:
            shot_boost = 0.10
            probs[PlayType.TWO_POINT_ATTEMPT] += shot_boost / 2
            probs[PlayType.THREE_POINT_ATTEMPT] += shot_boost / 2
            probs[PlayType.PASS] -= shot_boost
        
        # Clutch time boost for Scorers and Playmakers
        if game_state.is_clutch_time and archetype in ['Scorer', 'Playmaker']:
            usage_boost = 0.15
            probs[PlayType.TWO_POINT_ATTEMPT] += usage_boost / 2
            probs[PlayType.THREE_POINT_ATTEMPT] += usage_boost / 2
            probs[PlayType.PASS] -= usage_boost
        
        # Fatigue increases turnover probability
        if player.fatigue_penalty > 0:
            tov_increase = player.fatigue_penalty / 2
            probs[PlayType.TURNOVER] += tov_increase
            probs[PlayType.PASS] -= tov_increase / 2
            probs[PlayType.DRIVE] -= tov_increase / 2
        
        # Normalize probabilities to sum to 1
        total = sum(probs.values())
        probs = {k: max(0, v / total) for k, v in probs.items()}
        
        return probs
    
    def select_play(
        self,
        player: PlayerState,
        game_state: LiveGameState
    ) -> PlayType:
        """Select a play type using weighted random selection"""
        probs = self.get_play_probabilities(player, game_state)
        
        play_types = list(probs.keys())
        weights = np.array(list(probs.values()))
        
        # Ensure no negative values and normalize to sum to exactly 1.0
        weights = np.maximum(weights, 0.0)
        weights = weights / weights.sum()
        
        return np.random.choice(play_types, p=weights)


# =============================================================================
# CRUCIBLE SIMULATOR
# =============================================================================

class CrucibleSimulator:
    """
    Dynamic Possession-by-Possession Game Simulator.
    
    Simulates a full NBA game with:
    - Realistic clock management
    - Player rotations and foul trouble
    - Fatigue accumulation
    - Markov-based play selection
    - Blowout detection and garbage time
    - Learning Ledger integration
    """
    
    def __init__(
        self,
        usage_vacuum: Optional[any] = None,
        learning_ledger: Optional[any] = None,
        verbose: bool = False
    ):
        self.markov = MarkovPlaySelector()
        self.usage_vacuum = usage_vacuum
        self.learning_ledger = learning_ledger
        self.verbose = verbose
        
        # Initialize Defense Friction Module for individual DFG% physics
        self.defense_friction = get_defense_friction_module() if HAS_FRICTION_MODULE else None
        
        # Track friction impact for tooltips/UI
        self.friction_log: List[Dict] = []
    
    def simulate_game(
        self,
        home_players: List[Dict],
        away_players: List[Dict],
        injuries: Optional[List[Dict]] = None
    ) -> CrucibleResult:
        """
        Simulate a complete game.
        
        Args:
            home_players: List of player dicts with stats
            away_players: List of player dicts with stats
            injuries: Optional list of injured players
        """
        start_time = time.perf_counter()
        
        # Initialize game state
        game_state = self._initialize_game(home_players, away_players)
        
        # Apply usage vacuum if injuries present
        if injuries and self.usage_vacuum:
            self._apply_usage_vacuum(game_state, injuries)
        
        # Main game loop
        while not self._is_game_over(game_state):
            self._simulate_possession(game_state)
        
        # Compile results
        result = self._compile_results(game_state, start_time)
        
        # Log to Learning Ledger
        if self.learning_ledger:
            self._log_to_ledger(result)
        
        return result
    
    def _apply_injury_penalties(self, players: List[Dict]) -> List[Dict]:
        """Apply smart performance degradation for injured players"""
        if not HAS_INJURY_WORKER:
            return players
            
        injury_worker = get_injury_worker()
        adjusted_players = []
        
        for player in players:
            player_copy = player.copy()
            player_id = str(player.get('player_id'))
            
            status = injury_worker.get_player_status(player_id)
            performance_factor = status.get('performance_factor', 1.0)
            
            if performance_factor < 1.0:
                # Apply degradation to shooting and usage
                player_copy['fg2_pct'] = player.get('fg2_pct', 0.5) * performance_factor
                player_copy['fg3_pct'] = player.get('fg3_pct', 0.35) * performance_factor
                player_copy['usage'] = player.get('usage', 0.15) * performance_factor
                
                if self.verbose:
                    logger.info(
                        f"⚠️ {player['name']} playing {status['status']}: "
                        f"{int(performance_factor*100)}% performance - {status.get('reason', '')}"
                    )
            
            adjusted_players.append(player_copy)
        
        return adjusted_players
    
    def _initialize_game(
        self,
        home_players: List[Dict],
        away_players: List[Dict]
    ) -> LiveGameState:
        """Initialize game state with both teams + injury penalties"""
        
        # Apply smart injury performance degradation
        home_players = self._apply_injury_penalties(home_players)
        away_players = self._apply_injury_penalties(away_players)
        
        home_team = TeamState(
            team_id="home",
            team_name="Home",
            players=[self._create_player_state(p) for p in home_players],
            starters=[p['player_id'] for p in home_players[:5]]
        )
        
        away_team = TeamState(
            team_id="away", 
            team_name="Away",
            players=[self._create_player_state(p) for p in away_players],
            starters=[p['player_id'] for p in away_players[:5]]
        )
        
        # Set starters on court
        for player in home_team.players[:5]:
            player.is_on_court = True
        for player in home_team.players[5:]:
            player.is_on_court = False
            
        for player in away_team.players[:5]:
            player.is_on_court = True
        for player in away_team.players[5:]:
            player.is_on_court = False
        
        return LiveGameState(
            home_team=home_team,
            away_team=away_team,
            possession="home" if np.random.random() < 0.5 else "away"
        )
    
    def _create_player_state(self, player_dict: Dict) -> PlayerState:
        """Create PlayerState from dict"""
        return PlayerState(
            player_id=player_dict.get('player_id', str(np.random.randint(100000))),
            name=player_dict.get('name', 'Unknown'),
            archetype=player_dict.get('archetype', 'Balanced'),
            base_fg2_pct=player_dict.get('fg2_pct', 0.52),
            base_fg3_pct=player_dict.get('fg3_pct', 0.38),
            base_ft_pct=player_dict.get('ft_pct', 0.80),
            base_usage=player_dict.get('usage', 0.20),
        )
    
    def _simulate_possession(self, game_state: LiveGameState):
        """Simulate a single possession"""
        
        # Get offensive team
        off_team = game_state.home_team if game_state.possession == "home" else game_state.away_team
        def_team = game_state.away_team if game_state.possession == "home" else game_state.home_team
        
        # Check game phase
        self._update_game_phase(game_state)
        
        # Handle blowout - empty bench
        if game_state.phase == GamePhase.GARBAGE_TIME:
            self._handle_garbage_time(off_team)
        
        # Select ball handler based on usage
        ball_handler = self._select_ball_handler(off_team, game_state)
        
        if ball_handler is None:
            # No players on court (shouldn't happen)
            self._advance_clock(game_state)
            self._switch_possession(game_state)
            return
        
        # Select play using Markov chain
        play = self.markov.select_play(ball_handler, game_state)
        
        # Execute play
        self._execute_play(ball_handler, play, off_team, def_team, game_state)
        
        # Update fatigue for all on-court players
        self._update_fatigue(off_team, game_state)
        self._update_fatigue(def_team, game_state)
        
        # Check foul trouble
        self._check_foul_trouble(off_team, game_state)
        self._check_foul_trouble(def_team, game_state)
        
        # Advance clock
        self._advance_clock(game_state)
        
        # Switch possession (unless free throws)
        if play != PlayType.FREE_THROW:
            self._switch_possession(game_state)
        
        game_state.possession_count += 1
    
    def _select_ball_handler(
        self,
        team: TeamState,
        game_state: LiveGameState
    ) -> Optional[PlayerState]:
        """Select ball handler based on usage rates"""
        active = team.get_active_players()
        if not active:
            return None
        
        # Weight by usage + modifiers
        weights = []
        for p in active:
            usage = p.base_usage + p.usage_mod
            # Closer buff
            if game_state.is_clutch_time and p.archetype in ['Scorer', 'Playmaker']:
                usage *= 1.15
            weights.append(max(0.05, usage))
        
        # Normalize
        total = sum(weights)
        weights = [w / total for w in weights]
        
        return np.random.choice(active, p=weights)
    
    def _execute_play(
        self,
        player: PlayerState,
        play: PlayType,
        off_team: TeamState,
        def_team: TeamState,
        game_state: LiveGameState
    ):
        """Execute a play and update stats - NOW WITH INDIVIDUAL DFG% FRICTION"""
        
        # Calculate base shooting percentage with fatigue
        fg2_pct = player.base_fg2_pct * (1 - player.fatigue_penalty)
        fg3_pct = player.base_fg3_pct * (1 - player.fatigue_penalty)
        ft_pct = player.base_ft_pct
        
        # =====================================================================
        # PHYSICS FRICTION: Apply individual DFG% from tracking data
        # =====================================================================
        primary_defender_name = None
        friction_reason = None
        
        if self.defense_friction:
            # Get a defender from the defensive team
            defenders = def_team.get_active_players()
            if defenders:
                # Select primary defender (for now, random from active)
                defender = np.random.choice(defenders)
                
                # Apply individual DFG% friction to shooting percentages
                adjusted_fg2, reason2 = self.defense_friction.apply_defender_friction(
                    fg2_pct, defender.player_id, '2PT'
                )
                adjusted_fg3, reason3 = self.defense_friction.apply_defender_friction(
                    fg3_pct, defender.player_id, '3PT'
                )
                
                # Use adjusted percentages
                if reason2 != "No defender data":
                    fg2_pct = adjusted_fg2
                    fg3_pct = adjusted_fg3
                    primary_defender_name = defender.name
                    friction_reason = reason2
                    
                    # Log for UI tooltips
                    self.friction_log.append({
                        'shooter': player.name,
                        'defender': defender.name,
                        'original_fg': player.base_fg2_pct,
                        'adjusted_fg': fg2_pct,
                        'reason': reason2,
                        'quarter': game_state.quarter,
                    })
        
        if play == PlayType.TWO_POINT_ATTEMPT:
            if np.random.random() < fg2_pct:
                player.points += 2
                off_team.score += 2
                player.consecutive_makes += 1
                player.consecutive_misses = 0
            else:
                player.consecutive_misses += 1
                player.consecutive_makes = 0
                # Rebound opportunity
                self._handle_rebound(off_team, def_team)
        
        elif play == PlayType.THREE_POINT_ATTEMPT:
            if np.random.random() < fg3_pct:
                player.points += 3
                player.threes_made += 1
                off_team.score += 3
                player.consecutive_makes += 1
                player.consecutive_misses = 0
            else:
                player.consecutive_misses += 1
                player.consecutive_makes = 0
                self._handle_rebound(off_team, def_team)
        
        elif play == PlayType.DRIVE:
            # Drive can result in basket, foul, or miss
            outcome = np.random.random()
            if outcome < 0.35:  # Make
                player.points += 2
                off_team.score += 2
                player.consecutive_makes += 1
                player.consecutive_misses = 0
            elif outcome < 0.55:  # And-1 or foul
                self._handle_foul(player, def_team, game_state)
                # Shoot free throws
                fts = 2 if outcome < 0.50 else 3  # And-1
                for _ in range(fts):
                    if np.random.random() < ft_pct:
                        player.points += 1
                        off_team.score += 1
            else:  # Miss
                player.consecutive_misses += 1
                player.consecutive_makes = 0
                self._handle_rebound(off_team, def_team)
        
        elif play == PlayType.PASS:
            # Pass leads to teammate shot
            active = [p for p in off_team.get_active_players() if p != player]
            if active:
                shooter = np.random.choice(active)
                if np.random.random() < shooter.base_fg2_pct * (1 - shooter.fatigue_penalty):
                    shooter.points += 2
                    off_team.score += 2
                    player.assists += 1
                else:
                    self._handle_rebound(off_team, def_team)
        
        elif play == PlayType.TURNOVER:
            player.turnovers += 1
            # Possible steal
            if np.random.random() < 0.5:
                defenders = def_team.get_active_players()
                if defenders:
                    stealer = np.random.choice(defenders)
                    stealer.steals += 1
    
    def _handle_rebound(self, off_team: TeamState, def_team: TeamState):
        """Handle rebound after missed shot"""
        # 70% defensive rebound, 30% offensive
        if np.random.random() < 0.70:
            players = def_team.get_active_players()
        else:
            players = off_team.get_active_players()
        
        if players:
            # Weight by position (bigs get more rebounds)
            rebounder = np.random.choice(players)
            rebounder.rebounds += 1
    
    def _handle_foul(
        self,
        fouled_player: PlayerState,
        def_team: TeamState,
        game_state: LiveGameState
    ):
        """Handle a defensive foul"""
        defenders = def_team.get_active_players()
        if defenders:
            fouler = np.random.choice(defenders)
            fouler.fouls += 1
            def_team.team_fouls += 1
    
    def _check_foul_trouble(self, team: TeamState, game_state: LiveGameState):
        """Check if any players need to be benched for foul trouble"""
        for player in team.get_active_players():
            # 2 fouls in first half → bench until Q3
            if player.fouls >= 2 and game_state.quarter <= 2:
                player.is_on_court = False
                player.benched_until_quarter = 3
                game_state.key_events.append(
                    f"{player.name} benched (foul trouble: {player.fouls} fouls)"
                )
                # Sub in reserve
                self._sub_in_reserve(team)
            
            # 5 fouls → bench until Q4
            elif player.fouls >= 5 and game_state.quarter <= 3:
                player.is_on_court = False
                player.benched_until_quarter = 4
            
            # 6 fouls → fouled out
            elif player.fouls >= 6:
                player.is_on_court = False
                player.benched_until_quarter = 99  # Never returns
                game_state.key_events.append(f"{player.name} FOULED OUT")
        
        # Check if benched players can return
        for player in team.players:
            if not player.is_on_court and player.benched_until_quarter == game_state.quarter:
                # Can return if we need players
                if len(team.get_active_players()) < 5:
                    player.is_on_court = True
                    player.benched_until_quarter = 0
    
    def _sub_in_reserve(self, team: TeamState):
        """Substitute in a reserve player"""
        for player in team.players:
            if not player.is_on_court and player.benched_until_quarter == 0:
                player.is_on_court = True
                return
    
    def _update_fatigue(self, team: TeamState, game_state: LiveGameState):
        """Update fatigue for all on-court players"""
        for player in team.get_active_players():
            player.continuous_floor_time += POSSESSION_LENGTH
            player.minutes_played += POSSESSION_LENGTH / 60
            
            # Calculate fatigue penalty: -1% per 8 min continuous
            minutes_continuous = player.continuous_floor_time / 60
            player.fatigue_penalty = (minutes_continuous // 8) * 0.01
    
    def _update_game_phase(self, game_state: LiveGameState):
        """Update game phase based on score and time"""
        diff = abs(game_state.score_differential)
        
        if game_state.quarter == 4 and diff >= BLOWOUT_THRESHOLD:
            game_state.phase = GamePhase.GARBAGE_TIME
            if game_state.score_differential > 0:
                game_state.key_events.append("🚨 BLOWOUT: Home team empties bench")
            else:
                game_state.key_events.append("🚨 BLOWOUT: Away team empties bench")
        elif game_state.is_clutch_time:
            game_state.phase = GamePhase.CLUTCH
        else:
            game_state.phase = GamePhase.NORMAL
    
    def _handle_garbage_time(self, team: TeamState):
        """Handle garbage time - bench starters"""
        # If leading big, bench starters
        for player in team.players:
            if player.player_id in team.starters and player.is_on_court:
                player.is_on_court = False
        
        # Ensure bench players are in
        active_count = len(team.get_active_players())
        for player in team.players:
            if active_count >= 5:
                break
            if not player.is_on_court and player.player_id not in team.starters:
                player.is_on_court = True
                active_count += 1
    
    def _advance_clock(self, game_state: LiveGameState):
        """Advance game clock"""
        game_state.clock -= POSSESSION_LENGTH
        
        if game_state.clock <= 0:
            game_state.quarter += 1
            game_state.clock = QUARTER_LENGTH
            # Reset team fouls
            if game_state.home_team:
                game_state.home_team.team_fouls = 0
            if game_state.away_team:
                game_state.away_team.team_fouls = 0
    
    def _switch_possession(self, game_state: LiveGameState):
        """Switch possession between teams"""
        game_state.possession = "away" if game_state.possession == "home" else "home"
    
    def _is_game_over(self, game_state: LiveGameState) -> bool:
        """Check if game is over"""
        if game_state.quarter > 4:
            # Check for tie (overtime)
            if game_state.score_differential == 0:
                return False  # Go to OT
            return True
        return False
    
    def _apply_usage_vacuum(self, game_state: LiveGameState, injuries: List[Dict]):
        """Apply usage vacuum for injured players"""
        if not self.usage_vacuum:
            return
        
        for injury in injuries:
            team = game_state.home_team if injury.get('team') == 'home' else game_state.away_team
            if not team:
                continue
            
            injured_id = injury.get('player_id')
            injured_usage = injury.get('usage', 0.20)
            
            # Mark injured player as inactive
            injured_player = team.get_player(injured_id)
            if injured_player:
                injured_player.is_on_court = False
                injured_player.benched_until_quarter = 99
            
            # Redistribute usage to active players
            active = [p for p in team.players if p.player_id != injured_id]
            if active:
                boost_per_player = injured_usage / len(active)
                for player in active:
                    player.usage_mod += boost_per_player * 0.5  # 50% conversion
    
    def _compile_results(
        self,
        game_state: LiveGameState,
        start_time: float
    ) -> CrucibleResult:
        """Compile simulation results"""
        
        def compile_team_stats(team: TeamState) -> Dict[str, Dict]:
            return {
                p.player_id: {
                    'name': p.name,
                    'points': p.points,
                    'rebounds': p.rebounds,
                    'assists': p.assists,
                    'threes': p.threes_made,
                    'steals': p.steals,
                    'blocks': p.blocks,
                    'turnovers': p.turnovers,
                    'fouls': p.fouls,
                    'minutes': round(p.minutes_played, 1),
                }
                for p in team.players
            }
        
        home_stats = compile_team_stats(game_state.home_team) if game_state.home_team else {}
        away_stats = compile_team_stats(game_state.away_team) if game_state.away_team else {}
        
        return CrucibleResult(
            home_team_stats=home_stats,
            away_team_stats=away_stats,
            final_score=(
                game_state.home_team.score if game_state.home_team else 0,
                game_state.away_team.score if game_state.away_team else 0
            ),
            game_script=game_state.game_script,
            key_events=game_state.key_events,
            execution_time_ms=(time.perf_counter() - start_time) * 1000,
            was_blowout=game_state.phase == GamePhase.GARBAGE_TIME,
            was_clutch=game_state.is_clutch_time
        )
    
    def _log_to_ledger(self, result: CrucibleResult):
        """Log game to Learning Ledger for next-day audit"""
        if self.learning_ledger:
            self.learning_ledger.log_game_script(
                result.game_script,
                result.key_events,
                result.final_score
            )


# =============================================================================
# BATCH SIMULATOR (for projections)
# =============================================================================

class CrucibleProjector:
    """
    Run multiple Crucible simulations to generate projections.
    
    Similar to the Monte Carlo approach but using full game simulation.
    """
    
    def __init__(self, n_simulations: int = 1000, verbose: bool = True):
        self.n_simulations = n_simulations
        self.verbose = verbose
        self.simulator = CrucibleSimulator(verbose=False)
    
    def project(
        self,
        home_players: List[Dict],
        away_players: List[Dict],
        injuries: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Run N simulations and compile projection distributions.
        """
        start_time = time.perf_counter()
        
        # Storage for all simulations
        all_results = []
        
        for i in range(self.n_simulations):
            result = self.simulator.simulate_game(home_players, away_players, injuries)
            all_results.append(result)
            
            if self.verbose and (i + 1) % 100 == 0:
                elapsed = time.perf_counter() - start_time
                rate = (i + 1) / elapsed
                remaining = (self.n_simulations - i - 1) / rate
                print(f"   {i+1}/{self.n_simulations} games ({elapsed:.1f}s, ~{remaining:.1f}s remaining)")
        
        # Compile projections
        projections = self._compile_projections(all_results, home_players, away_players)
        projections['execution_time_s'] = time.perf_counter() - start_time
        
        return projections
    
    def _compile_projections(
        self,
        results: List[CrucibleResult],
        home_players: List[Dict],
        away_players: List[Dict]
    ) -> Dict:
        """Compile projection distributions from all simulations"""
        
        projections = {'home': {}, 'away': {}}
        home_projs = projections['home']
        away_projs = projections['away']
        
        # Compile home team
        for player in home_players:
            pid = player['player_id']
            stats = {
                'points': [],
                'rebounds': [],
                'assists': [],
                'threes': [],
                'minutes': []
            }
            
            for result in results:
                if pid in result.home_team_stats:
                    ps = result.home_team_stats[pid]
                    stats['points'].append(ps['points'])
                    stats['rebounds'].append(ps['rebounds'])
                    stats['assists'].append(ps['assists'])
                    stats['threes'].append(ps['threes'])
                    stats['minutes'].append(ps['minutes'])
            
            home_projs[pid] = {
                'name': player['name'],
                'floor_20': {k: np.percentile(v, 20) for k, v in stats.items()},
                'ev': {k: np.mean(v) for k, v in stats.items()},
                'ceiling_80': {k: np.percentile(v, 80) for k, v in stats.items()},
            }
        
        # Compile away team
        for player in away_players:
            pid = player['player_id']
            stats = {
                'points': [],
                'rebounds': [],
                'assists': [],
                'threes': [],
                'minutes': []
            }
            
            for result in results:
                if pid in result.away_team_stats:
                    ps = result.away_team_stats[pid]
                    stats['points'].append(ps['points'])
                    stats['rebounds'].append(ps['rebounds'])
                    stats['assists'].append(ps['assists'])
                    stats['threes'].append(ps['threes'])
                    stats['minutes'].append(ps['minutes'])
            
            away_projs[pid] = {
                'name': player['name'],
                'floor_20': {k: np.percentile(v, 20) for k, v in stats.items()},
                'ev': {k: np.mean(v) for k, v in stats.items()},
                'ceiling_80': {k: np.percentile(v, 80) for k, v in stats.items()},
            }
        
        # Game-level stats
        home_scores = [r.final_score[0] for r in results]
        away_scores = [r.final_score[1] for r in results]
        
        projections['game'] = {
            'home_score': {'floor': np.percentile(home_scores, 20), 'ev': np.mean(home_scores), 'ceiling': np.percentile(home_scores, 80)},
            'away_score': {'floor': np.percentile(away_scores, 20), 'ev': np.mean(away_scores), 'ceiling': np.percentile(away_scores, 80)},
            'blowout_pct': sum(1 for r in results if r.was_blowout) / len(results),
            'clutch_pct': sum(1 for r in results if r.was_clutch) / len(results),
        }
        
        return projections


# =============================================================================
# DEMO
# =============================================================================

def run_demo():
    """Demo the Crucible Engine"""
    print("=" * 70)
    print(" 🔥 CRUCIBLE SIMULATION ENGINE v4.0")
    print("=" * 70)
    
    # Sample players (Warriors @ Lakers)
    warriors = [
        {'player_id': '201939', 'name': 'Stephen Curry', 'archetype': 'Scorer', 'fg2_pct': 0.55, 'fg3_pct': 0.42, 'usage': 0.32},
        {'player_id': '203110', 'name': 'Draymond Green', 'archetype': 'Playmaker', 'fg2_pct': 0.52, 'fg3_pct': 0.30, 'usage': 0.14},
        {'player_id': '203952', 'name': 'Andrew Wiggins', 'archetype': 'Balanced', 'fg2_pct': 0.50, 'fg3_pct': 0.38, 'usage': 0.18},
        {'player_id': '1628398', 'name': 'Kevon Looney', 'archetype': 'Rim Protector', 'fg2_pct': 0.62, 'fg3_pct': 0.00, 'usage': 0.08},
        {'player_id': '1630228', 'name': 'Jonathan Kuminga', 'archetype': 'Slasher', 'fg2_pct': 0.54, 'fg3_pct': 0.32, 'usage': 0.16},
        # Bench
        {'player_id': 'bench1', 'name': 'Reserve 1', 'archetype': 'Balanced', 'usage': 0.10},
        {'player_id': 'bench2', 'name': 'Reserve 2', 'archetype': 'Balanced', 'usage': 0.10},
    ]
    
    lakers = [
        {'player_id': '2544', 'name': 'LeBron James', 'archetype': 'Scorer', 'fg2_pct': 0.58, 'fg3_pct': 0.38, 'usage': 0.30},
        {'player_id': '203076', 'name': 'Anthony Davis', 'archetype': 'Rim Protector', 'fg2_pct': 0.56, 'fg3_pct': 0.28, 'usage': 0.28},
        {'player_id': '1628398', 'name': "D'Angelo Russell", 'archetype': 'Playmaker', 'fg2_pct': 0.48, 'fg3_pct': 0.36, 'usage': 0.22},
        {'player_id': '203484', 'name': 'Austin Reaves', 'archetype': 'Three-and-D', 'fg2_pct': 0.50, 'fg3_pct': 0.40, 'usage': 0.15},
        {'player_id': '1629060', 'name': 'Rui Hachimura', 'archetype': 'Balanced', 'fg2_pct': 0.52, 'fg3_pct': 0.35, 'usage': 0.12},
        # Bench
        {'player_id': 'bench3', 'name': 'Reserve 3', 'archetype': 'Balanced', 'usage': 0.10},
        {'player_id': 'bench4', 'name': 'Reserve 4', 'archetype': 'Balanced', 'usage': 0.10},
    ]
    
    print("\n🏀 Warriors @ Lakers")
    print("   Running 500 simulations...")
    print()
    
    projector = CrucibleProjector(n_simulations=500, verbose=True)
    projections = projector.project(lakers, warriors)  # Lakers home
    
    print(f"\n{'=' * 70}")
    print(" CRUCIBLE PROJECTIONS")
    print('=' * 70)
    
    print("\n📊 Lakers (Home):")
    for pid, proj in projections['home'].items():
        # Safe access with .get()
        ev_mins = proj.get('ev', {}).get('minutes', 0)
        
        if ev_mins > 10:
            # Extract values safely
            p_floor = proj.get('floor_20', {}).get('points', 0)
            p_ev = proj.get('ev', {}).get('points', 0)
            p_ceil = proj.get('ceiling_80', {}).get('points', 0)
            reb = proj.get('ev', {}).get('rebounds', 0)
            ast = proj.get('ev', {}).get('assists', 0)
            threes = proj.get('ev', {}).get('threes', 0)
            
            print(f"   {proj['name']:<20} "
                  f"PTS: {p_floor:.1f}/{p_ev:.1f}/{p_ceil:.1f} | "
                  f"REB: {reb:.1f} | "
                  f"AST: {ast:.1f} | "
                  f"3PM: {threes:.1f}")
    
    print("\n📊 Warriors (Away):")
    for pid, proj in projections['away'].items():
        ev_mins = proj.get('ev', {}).get('minutes', 0)
        
        if ev_mins > 10:
            p_floor = proj.get('floor_20', {}).get('points', 0)
            p_ev = proj.get('ev', {}).get('points', 0)
            p_ceil = proj.get('ceiling_80', {}).get('points', 0)
            reb = proj.get('ev', {}).get('rebounds', 0)
            ast = proj.get('ev', {}).get('assists', 0)
            threes = proj.get('ev', {}).get('threes', 0)
            
            print(f"   {proj['name']:<20} "
                  f"PTS: {p_floor:.1f}/{p_ev:.1f}/{p_ceil:.1f} | "
                  f"REB: {reb:.1f} | "
                  f"AST: {ast:.1f} | "
                  f"3PM: {threes:.1f}")
    
    print(f"\n🏟️  Game Prediction:")
    # Safe access for game stats
    game_proj = projections.get('game', {})
    home_score = game_proj.get('home_score', {})
    away_score = game_proj.get('away_score', {})
    
    print(f"   Lakers: {home_score.get('floor',0):.0f} / {home_score.get('ev',0):.0f} / {home_score.get('ceiling',0):.0f}")
    print(f"   Warriors: {away_score.get('floor',0):.0f} / {away_score.get('ev',0):.0f} / {away_score.get('ceiling',0):.0f}")
    print(f"   Blowout Probability: {game_proj.get('blowout_pct',0):.1%}")
    print(f"   Clutch Game Probability: {game_proj.get('clutch_pct',0):.1%}")
    
    print(f"\n⏱️  Execution Time: {projections.get('execution_time_s',0):.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
