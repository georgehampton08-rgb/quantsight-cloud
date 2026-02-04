"""
Crucible Core - Pure Simulation Logic
======================================
Platform-agnostic core calculations for the Crucible simulation engine.

This module contains the pure mathematical logic without any I/O,
database access, or platform-specific code.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import random


class PlayType(Enum):
    """Types of offensive plays."""
    TWO_POINT_ATTEMPT = "2PA"
    THREE_POINT_ATTEMPT = "3PA"
    FREE_THROW = "FT"
    TURNOVER = "TOV"
    PASS = "PASS"
    DRIVE = "DRIVE"


class GamePhase(Enum):
    """Game phases that affect strategy."""
    NORMAL = "normal"
    CLUTCH = "clutch"           # Score diff < 5, last 5 min
    BLOWOUT_WINNING = "blowout_winning"
    BLOWOUT_LOSING = "blowout_losing"
    GARBAGE_TIME = "garbage"


# Constants
QUARTER_LENGTH = 720  # 12 minutes in seconds
POSSESSION_LENGTH = 14  # Average seconds per possession
BLOWOUT_THRESHOLD = 18  # Point differential for blowout
CLUTCH_TIME_THRESHOLD = 300  # Last 5 minutes
CLUTCH_SCORE_THRESHOLD = 5  # Within 5 points
BACK_TO_BACK_PENALTY = 0.02  # +2% flat fatigue penalty


@dataclass
class PlayerSimState:
    """Player state during simulation - pure data, no I/O."""
    player_id: str
    name: str
    archetype: str = "Balanced"
    
    # Base stats
    base_fg2_pct: float = 0.52
    base_fg3_pct: float = 0.38
    base_ft_pct: float = 0.80
    base_usage: float = 0.20
    
    # Advanced stats
    ast_pct: float = 0.15
    reb_pct: float = 0.10
    def_rating: float = 110.0
    pie: float = 0.10
    age: int = 25
    
    # Hustle stats
    off_boxouts: float = 0.0
    def_boxouts: float = 0.0
    
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
    fatigue_penalty: float = 0.0
    usage_mod: float = 0.0
    is_back_to_back: bool = False


# League average for assist percentage scaling
LEAGUE_AVG_AST_PCT = 0.15

# Base transition probabilities by archetype
ARCHETYPE_PLAY_PROBS = {
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


class CrucibleCore:
    """
    Pure calculation core for Crucible simulations.
    
    This class contains only mathematical/statistical logic with no I/O.
    Platform-specific adapters should wrap this class to handle data
    loading and persistence.
    """
    
    @staticmethod
    def get_play_probabilities(
        player: PlayerSimState,
        is_clutch_time: bool = False,
        is_highest_pie_on_floor: bool = False
    ) -> Dict[PlayType, float]:
        """
        Calculate play probabilities for a player.
        
        Applies Markov adjustments based on:
        - Cold streak (3+ misses → -15% shot, +15% pass)
        - Hot streak (3+ makes → +10% shot, -5% pass)
        - Clutch time (Highest PIE player gets +15% usage)
        - Fatigue (increases turnover probability)
        - Assist percentage (scales passing probability)
        
        Args:
            player: PlayerSimState with current stats
            is_clutch_time: Whether we're in clutch time
            is_highest_pie_on_floor: Whether this player has highest PIE
        
        Returns:
            Dictionary mapping PlayType to probability
        """
        archetype = player.archetype if player.archetype in ARCHETYPE_PLAY_PROBS else 'Balanced'
        probs = ARCHETYPE_PLAY_PROBS[archetype].copy()
        
        # Cold streak adjustment
        if player.consecutive_misses >= 3:
            shot_reduction = 0.15
            probs[PlayType.TWO_POINT_ATTEMPT] -= shot_reduction / 2
            probs[PlayType.THREE_POINT_ATTEMPT] -= shot_reduction / 2
            probs[PlayType.PASS] += shot_reduction
        
        # Hot streak / Heat Check
        elif player.consecutive_makes >= 3:
            shot_boost = 0.10
            probs[PlayType.TWO_POINT_ATTEMPT] += shot_boost / 2
            probs[PlayType.THREE_POINT_ATTEMPT] += shot_boost / 2
            probs[PlayType.PASS] -= shot_boost
        
        # Clutch time: "Hero Ball" effect
        if is_clutch_time and is_highest_pie_on_floor:
            usage_boost = 0.15
            probs[PlayType.TWO_POINT_ATTEMPT] += usage_boost / 2
            probs[PlayType.THREE_POINT_ATTEMPT] += usage_boost / 2
            probs[PlayType.PASS] -= usage_boost
        elif is_clutch_time and archetype in ['Scorer', 'Playmaker']:
            # Other scorers get small boost in clutch
            usage_boost = 0.05
            probs[PlayType.TWO_POINT_ATTEMPT] += usage_boost / 2
            probs[PlayType.THREE_POINT_ATTEMPT] += usage_boost / 2
            probs[PlayType.PASS] -= usage_boost
        
        # Fatigue increases turnover probability
        if player.fatigue_penalty > 0:
            tov_increase = player.fatigue_penalty / 2
            probs[PlayType.TURNOVER] += tov_increase
            probs[PlayType.PASS] -= tov_increase / 2
            probs[PlayType.DRIVE] -= tov_increase / 2
        
        # Scale PASS probability by player's ast_pct
        ast_multiplier = player.ast_pct / LEAGUE_AVG_AST_PCT
        ast_multiplier = min(2.0, max(0.5, ast_multiplier))  # Clamp 0.5x - 2x
        probs[PlayType.PASS] = probs[PlayType.PASS] * ast_multiplier
        
        # Normalize to sum to 1
        total = sum(probs.values())
        probs = {k: max(0, v / total) for k, v in probs.items()}
        
        return probs
    
    @staticmethod
    def get_effective_shooting_pct(
        base_pct: float,
        fatigue_penalty: float,
        defense_modifier: float = 1.0
    ) -> float:
        """
        Calculate effective shooting percentage with all modifiers.
        
        Args:
            base_pct: Base shooting percentage
            fatigue_penalty: Current fatigue penalty (0.0 to 0.15)
            defense_modifier: Defensive impact modifier (0.90 to 1.10)
        
        Returns:
            Adjusted shooting percentage
        """
        effective = base_pct * (1 - min(fatigue_penalty, 0.15)) * defense_modifier
        return max(0.15, min(0.85, effective))
    
    @staticmethod
    def calculate_rebound_weights(
        offensive_players: List[PlayerSimState],
        defensive_players: List[PlayerSimState],
        *,
        high_reb_threshold: float = 0.12,
        high_boxout_threshold: float = 2.0,
        positioning_bonus: float = 1.12,
        def_weight_multiplier: float = 2.5
    ) -> Tuple[List[Tuple[PlayerSimState, float]], List[Tuple[PlayerSimState, float]]]:
        """
        Calculate rebound probability weights for all players.
        
        Uses reb_pct with positioning bonus for high boxout players.
        Defensive rebounders get 2.5x weight (reflects ~70% DREB rate).
        
        Args:
            offensive_players: Active offensive team players
            defensive_players: Active defensive team players
            high_reb_threshold: Threshold for high rebound rate
            high_boxout_threshold: Threshold for high boxout frequency
            positioning_bonus: Multiplier for positioned players
            def_weight_multiplier: Weight advantage for defensive team
        
        Returns:
            Tuple of (offensive_weights, defensive_weights)
        """
        off_weights = []
        for p in offensive_players:
            weight = p.reb_pct * 1.0
            if p.reb_pct >= high_reb_threshold and p.off_boxouts >= high_boxout_threshold:
                weight *= positioning_bonus
            off_weights.append((p, weight))
        
        def_weights = []
        for p in defensive_players:
            weight = p.reb_pct * def_weight_multiplier
            if p.reb_pct >= high_reb_threshold and p.def_boxouts >= high_boxout_threshold:
                weight *= positioning_bonus
            def_weights.append((p, weight))
        
        return (off_weights, def_weights)
    
    @staticmethod
    def determine_game_phase(
        quarter: int,
        clock_remaining: float,
        score_differential: int
    ) -> GamePhase:
        """
        Determine current game phase based on situation.
        
        Args:
            quarter: Current quarter (1-4 or 5+ for OT)
            clock_remaining: Seconds remaining in quarter
            score_differential: Positive = home leading
        
        Returns:
            GamePhase enum value
        """
        if quarter < 4:
            if abs(score_differential) >= BLOWOUT_THRESHOLD:
                return GamePhase.BLOWOUT_WINNING if score_differential > 0 else GamePhase.BLOWOUT_LOSING
            return GamePhase.NORMAL
        
        # Q4 or OT
        if clock_remaining <= CLUTCH_TIME_THRESHOLD and abs(score_differential) <= CLUTCH_SCORE_THRESHOLD:
            return GamePhase.CLUTCH
        
        if abs(score_differential) >= BLOWOUT_THRESHOLD:
            return GamePhase.GARBAGE_TIME
        
        return GamePhase.NORMAL
    
    @staticmethod
    def calculate_usage_weights(
        players: List[PlayerSimState],
        is_clutch_time: bool = False
    ) -> List[float]:
        """
        Calculate usage weights for ball handler selection.
        
        Args:
            players: Active players on court
            is_clutch_time: Whether we're in clutch time
        
        Returns:
            List of weights corresponding to each player
        """
        weights = []
        for p in players:
            usage = p.base_usage + p.usage_mod
            if is_clutch_time and p.archetype in ['Scorer', 'Playmaker']:
                usage *= 1.15
            weights.append(max(0.05, usage))
        
        # Normalize
        total = sum(weights)
        return [w / total for w in weights]
