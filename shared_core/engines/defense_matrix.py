"""
Defense Matrix - Pure Function
==============================
Defensive friction and shooting adjustments without any I/O dependencies.

This is the platform-agnostic core logic for defensive impact calculations.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class DefenderProfile:
    """Defensive profile for a player."""
    player_id: str
    name: str
    d_fg_pct: float       # Opponent FG% (lower = better defender)
    d_fg3_pct: float      # Opponent 3PT% (lower = better defender)
    def_rating: float     # Defensive rating (lower = better)
    contests_per_game: float = 0.0
    
    @property
    def is_elite_defender(self) -> bool:
        """Check if this is an elite defender (top tier)."""
        return self.def_rating < 108
    
    @property
    def is_poor_defender(self) -> bool:
        """Check if this is a poor defender."""
        return self.def_rating > 115


# League averages for normalization
LEAGUE_AVG_FG_PCT = 0.471
LEAGUE_AVG_FG3_PCT = 0.365
LEAGUE_AVG_DEF_RATING = 112.0


def calculate_defense_friction(
    base_fg_pct: float,
    defender_d_fg_pct: float,
    shot_type: str = '2PT',
    *,
    league_avg_fg: float = LEAGUE_AVG_FG_PCT,
    league_avg_fg3: float = LEAGUE_AVG_FG3_PCT
) -> Tuple[float, str]:
    """
    Apply defensive friction to shooting percentage.
    
    Uses individual DFG% (Defended Field Goal Percentage) to adjust
    shooter's expected accuracy based on defender quality.
    
    Args:
        base_fg_pct: Shooter's base field goal percentage
        defender_d_fg_pct: Defender's opponent FG% allowed
        shot_type: '2PT' or '3PT'
        league_avg_fg: League average 2PT FG% for comparison
        league_avg_fg3: League average 3PT FG% for comparison
    
    Returns:
        Tuple of (adjusted_fg_pct, reason_string)
    
    Example:
        >>> adjusted, reason = calculate_defense_friction(0.52, 0.42, '2PT')
        >>> adjusted < 0.52  # Elite defender reduces shooting
        True
    """
    # Determine league average based on shot type
    if shot_type == '3PT':
        league_avg = league_avg_fg3
    else:
        league_avg = league_avg_fg
    
    # Calculate defender impact relative to league average
    defender_impact = defender_d_fg_pct - league_avg
    
    # Apply friction: positive impact = poor defender (boost), negative = elite (penalty)
    # Scale factor: each 1% difference from league avg = ~0.8% adjustment
    adjustment = defender_impact * 0.8
    
    adjusted_pct = base_fg_pct + adjustment
    
    # Clamp to reasonable bounds
    adjusted_pct = max(0.20, min(0.75, adjusted_pct))
    
    # Generate reason
    if defender_impact < -0.03:
        reason = f"Elite DFG% ({defender_d_fg_pct:.1%})"
    elif defender_impact > 0.03:
        reason = f"Weak DFG% ({defender_d_fg_pct:.1%})"
    else:
        reason = f"Average DFG% ({defender_d_fg_pct:.1%})"
    
    return (adjusted_pct, reason)


def apply_def_rating_modifier(
    fg_pct: float,
    def_rating: float,
    *,
    elite_threshold: float = 108.0,
    poor_threshold: float = 115.0,
    elite_modifier: float = 0.95,
    poor_modifier: float = 1.05
) -> Tuple[float, str]:
    """
    Apply defensive rating modifier on top of DFG% friction.
    
    Elite defenders (def_rating < 108) apply additional 5% shooting penalty.
    Poor defenders (def_rating > 115) give shooter a 5% bonus.
    
    Args:
        fg_pct: Field goal percentage after DFG% adjustment
        def_rating: Defender's defensive rating
        elite_threshold: Threshold for elite defender classification
        poor_threshold: Threshold for poor defender classification
        elite_modifier: Multiplier for elite defenders
        poor_modifier: Multiplier for poor defenders
    
    Returns:
        Tuple of (adjusted_fg_pct, modifier_reason)
    """
    if def_rating < elite_threshold:
        modifier = elite_modifier
        reason = f"Elite DEF ({def_rating:.0f})"
    elif def_rating > poor_threshold:
        modifier = poor_modifier
        reason = f"Weak DEF ({def_rating:.0f})"
    else:
        modifier = 1.0
        reason = "Average DEF"
    
    return (fg_pct * modifier, reason)


def calculate_full_defensive_adjustment(
    base_fg_pct: float,
    defender_profile: Optional[DefenderProfile],
    shot_type: str = '2PT'
) -> Tuple[float, str]:
    """
    Calculate complete defensive adjustment using DFG% + DEF rating.
    
    Args:
        base_fg_pct: Shooter's base field goal percentage
        defender_profile: DefenderProfile or None for no adjustment
        shot_type: '2PT' or '3PT'
    
    Returns:
        Tuple of (adjusted_fg_pct, full_reason)
    """
    if defender_profile is None:
        return (base_fg_pct, "No defender data")
    
    # Get appropriate DFG% based on shot type
    d_fg = defender_profile.d_fg3_pct if shot_type == '3PT' else defender_profile.d_fg_pct
    
    # Apply DFG% friction
    adjusted, dfg_reason = calculate_defense_friction(base_fg_pct, d_fg, shot_type)
    
    # Apply DEF rating modifier
    final, def_reason = apply_def_rating_modifier(adjusted, defender_profile.def_rating)
    
    # Combine reasons
    if def_reason != "Average DEF":
        full_reason = f"{dfg_reason} + {def_reason}"
    else:
        full_reason = dfg_reason
    
    return (final, full_reason)


def calculate_team_defense_modifier(
    team_def_rating: float,
    *,
    league_avg_def_rating: float = LEAGUE_AVG_DEF_RATING
) -> float:
    """
    Calculate team-level defensive modifier.
    
    Used for adjusting projections based on opposing team's overall defense.
    
    Args:
        team_def_rating: Team's defensive rating
        league_avg_def_rating: League average for normalization
    
    Returns:
        Modifier as decimal (0.90 to 1.10 typically)
    
    Example:
        >>> modifier = calculate_team_defense_modifier(105.0)
        >>> modifier < 1.0  # Elite defense = negative modifier
        True
    """
    # Difference from league average
    diff = team_def_rating - league_avg_def_rating
    
    # Convert to percentage modifier
    # Each point of DEF rating = ~0.5% impact
    modifier = 1.0 + (diff * 0.005)
    
    # Clamp to reasonable bounds
    return max(0.85, min(1.15, modifier))
