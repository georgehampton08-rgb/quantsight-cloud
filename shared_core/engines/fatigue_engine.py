"""
Fatigue Engine - Pure Function
==============================
Schedule-based fatigue calculations without any I/O dependencies.

This is the platform-agnostic core logic for rest-decay adjustments.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union


@dataclass
class FatigueResult:
    """Result of fatigue calculation."""
    modifier: float  # Percentage adjustment (-0.08 to +0.03)
    reason: str      # Human-readable explanation
    days_rest: int   # Days since last game
    is_b2b: bool     # Back-to-back game
    is_road: bool    # Away game


# Fatigue modifier constants
FATIGUE_MODIFIERS = {
    'B2B_road': -0.08,     # Back-to-back on road
    'B2B_home': -0.05,     # Back-to-back at home
    '3_in_4': -0.06,       # 3 games in 4 nights
    '4_in_6': -0.04,       # 4 games in 6 nights
    'rest_3plus': +0.03,   # 3+ days rest bonus
    'rest_2': 0.0,         # Normal rest
    'rest_1': -0.02,       # One day rest
}


def calculate_fatigue_adjustment(
    game_date: Union[date, str],
    is_road: bool,
    recent_games: List[Dict[str, Union[str, date, datetime]]],
    *,
    date_keys: Tuple[str, ...] = ('date', 'game_date', 'GAME_DATE')
) -> FatigueResult:
    """
    Calculate fatigue modifier based on schedule.
    
    NBA schedule fatigue significantly impacts performance:
    - B2B on road: Players average -8% in scoring
    - 3 games in 4 nights: -6% penalty
    - Extended rest (3+ days): +3% boost
    
    Args:
        game_date: Date of upcoming game (date object or ISO string)
        is_road: Whether game is on the road
        recent_games: List of recent game dicts containing date information
        date_keys: Tuple of possible keys to look for date in game dicts
    
    Returns:
        FatigueResult with modifier and context
    
    Example:
        >>> from datetime import date
        >>> games = [{'date': '2026-01-31'}, {'date': '2026-01-30'}]
        >>> result = calculate_fatigue_adjustment(date(2026, 2, 1), is_road=True, recent_games=games)
        >>> result.is_b2b
        True
        >>> result.modifier
        -0.08
    """
    # Parse game_date if string
    if isinstance(game_date, str):
        game_date = _parse_single_date(game_date)
    
    if not recent_games:
        return FatigueResult(
            modifier=0.0,
            reason="No recent game data",
            days_rest=7,
            is_b2b=False,
            is_road=is_road
        )
    
    # Parse game dates from recent games
    game_dates = _parse_dates(recent_games, date_keys)
    
    if not game_dates:
        return FatigueResult(
            modifier=0.0,
            reason="Could not parse game dates",
            days_rest=7,
            is_b2b=False,
            is_road=is_road
        )
    
    # Get most recent game date
    last_game = max(game_dates)
    days_rest = (game_date - last_game).days
    
    # Check for back-to-back
    is_b2b = days_rest <= 1
    
    # Check for compressed schedule
    games_in_4 = sum(1 for d in game_dates if 0 < (game_date - d).days <= 4)
    games_in_6 = sum(1 for d in game_dates if 0 < (game_date - d).days <= 6)
    
    # Determine modifier (priority order matters)
    if is_b2b and is_road:
        modifier = FATIGUE_MODIFIERS['B2B_road']
        reason = "Back-to-back on road"
    elif is_b2b:
        modifier = FATIGUE_MODIFIERS['B2B_home']
        reason = "Back-to-back at home"
    elif games_in_4 >= 3:
        modifier = FATIGUE_MODIFIERS['3_in_4']
        reason = "3 games in 4 nights"
    elif games_in_6 >= 4:
        modifier = FATIGUE_MODIFIERS['4_in_6']
        reason = "4 games in 6 nights"
    elif days_rest >= 3:
        modifier = FATIGUE_MODIFIERS['rest_3plus']
        reason = f"{days_rest} days rest (well-rested)"
    elif days_rest == 1:
        modifier = FATIGUE_MODIFIERS['rest_1']
        reason = "One day rest"
    else:
        modifier = 0.0
        reason = "Normal rest"
    
    return FatigueResult(
        modifier=modifier,
        reason=reason,
        days_rest=days_rest,
        is_b2b=is_b2b,
        is_road=is_road
    )


def apply_fatigue_to_mean(base_mean: float, fatigue_result: FatigueResult) -> float:
    """
    Apply fatigue modifier to a statistical mean.
    
    Args:
        base_mean: Original EMA/rolling mean
        fatigue_result: Result from calculate_fatigue_adjustment()
    
    Returns:
        Adjusted mean with fatigue modifier applied
    
    Example:
        >>> result = FatigueResult(modifier=-0.08, reason="B2B", days_rest=1, is_b2b=True, is_road=True)
        >>> apply_fatigue_to_mean(25.0, result)
        23.0
    """
    return base_mean * (1 + fatigue_result.modifier)


def get_in_game_fatigue_penalty(
    continuous_minutes: float,
    age: int = 25,
    *,
    penalty_interval_minutes: float = 8.0,
    base_penalty_per_interval: float = 0.01,
    max_penalty: float = 0.15
) -> float:
    """
    Calculate in-game fatigue penalty based on continuous floor time.
    
    Players accumulate fatigue at -1% per 8 minutes of continuous play.
    Older players (30+) fatigue faster.
    
    Args:
        continuous_minutes: Minutes without rest
        age: Player age (affects fatigue rate)
        penalty_interval_minutes: Minutes per penalty interval
        base_penalty_per_interval: Penalty per interval
        max_penalty: Maximum fatigue penalty cap
    
    Returns:
        Fatigue penalty as decimal (0.0 to max_penalty)
    
    Example:
        >>> get_in_game_fatigue_penalty(24.0, age=25)
        0.03
        >>> get_in_game_fatigue_penalty(24.0, age=35)
        0.045
    """
    intervals = continuous_minutes / penalty_interval_minutes
    
    # Age modifier: older players fatigue faster
    age_modifier = 1.0
    if age >= 35:
        age_modifier = 1.5
    elif age >= 30:
        age_modifier = 1.25
    
    penalty = intervals * base_penalty_per_interval * age_modifier
    
    return min(penalty, max_penalty)


def _parse_single_date(date_str: str) -> date:
    """Parse a single date string to date object."""
    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d']:
        try:
            return datetime.strptime(date_str[:10], fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str}")


def _parse_dates(
    games: List[Dict],
    date_keys: Tuple[str, ...] = ('date', 'game_date', 'GAME_DATE')
) -> List[date]:
    """Parse game dates from various formats."""
    dates = []
    
    for game in games:
        date_val = None
        for key in date_keys:
            if key in game:
                date_val = game[key]
                break
        
        if date_val is None:
            continue
        
        try:
            if isinstance(date_val, date):
                dates.append(date_val)
            elif isinstance(date_val, datetime):
                dates.append(date_val.date())
            else:
                dates.append(_parse_single_date(str(date_val)))
        except (ValueError, AttributeError):
            continue
    
    return dates
