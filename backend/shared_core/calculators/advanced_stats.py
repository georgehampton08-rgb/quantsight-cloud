"""
Advanced Stats Calculator - Pure Functions
==========================================
Platform-agnostic advanced NBA statistics calculations.
"""

from typing import Dict, Optional


def calculate_true_shooting(
    pts: float,
    fga: float,
    fta: float
) -> float:
    """
    Calculate True Shooting Percentage (TS%).
    
    TS% accounts for 2-pointers, 3-pointers, and free throws in one metric.
    Formula: PTS / (2 * (FGA + 0.44 * FTA))
    
    Args:
        pts: Points scored
        fga: Field goal attempts
        fta: Free throw attempts
    
    Returns:
        True Shooting Percentage as decimal (0.0 to 1.0)
    
    Example:
        >>> calculate_true_shooting(25, 18, 6)
        0.599...
    """
    if fga <= 0 and fta <= 0:
        return 0.0
    
    # 0.44 is the adjusted FTA weight (accounts for and-1s, technicals, etc.)
    tsa = fga + (0.44 * fta)
    
    if tsa <= 0:
        return 0.0
    
    ts_pct = pts / (2 * tsa)
    
    return max(0.0, min(1.0, ts_pct))


def calculate_effective_fg(
    fgm: float,
    fg3m: float,
    fga: float
) -> float:
    """
    Calculate Effective Field Goal Percentage (eFG%).
    
    eFG% adjusts FG% to account for the extra value of 3-pointers.
    Formula: (FGM + 0.5 * 3PM) / FGA
    
    Args:
        fgm: Field goals made
        fg3m: Three-pointers made
        fga: Field goal attempts
    
    Returns:
        Effective FG% as decimal (0.0 to 1.0)
    
    Example:
        >>> calculate_effective_fg(9, 3, 18)
        0.583...
    """
    if fga <= 0:
        return 0.0
    
    efg = (fgm + (0.5 * fg3m)) / fga
    
    return max(0.0, min(1.5, efg))  # Can exceed 1.0 theoretically


def calculate_usage_rate(
    fga: float,
    fta: float,
    tov: float,
    minutes: float,
    team_fga: float,
    team_fta: float,
    team_tov: float,
    team_minutes: float = 240.0
) -> float:
    """
    Calculate Usage Rate (USG%).
    
    Estimates the percentage of team plays used by a player while on court.
    Formula: 100 * ((FGA + 0.44 * FTA + TOV) * (Tm MP / 5)) / (MP * (Tm FGA + 0.44 * Tm FTA + Tm TOV))
    
    Args:
        fga: Player field goal attempts
        fta: Player free throw attempts
        tov: Player turnovers
        minutes: Player minutes played
        team_fga: Team field goal attempts
        team_fta: Team free throw attempts
        team_tov: Team turnovers
        team_minutes: Team total minutes (default 240 for full game)
    
    Returns:
        Usage rate as decimal (0.0 to 1.0)
    
    Example:
        >>> calculate_usage_rate(18, 6, 2, 36, 90, 25, 12)
        0.29...
    """
    if minutes <= 0 or team_fga <= 0:
        return 0.0
    
    player_usage = fga + (0.44 * fta) + tov
    team_usage = team_fga + (0.44 * team_fta) + team_tov
    
    if team_usage <= 0:
        return 0.0
    
    # Adjust for player's portion of team minutes
    usg = (player_usage * (team_minutes / 5)) / (minutes * team_usage)
    
    return max(0.0, min(1.0, usg))


def calculate_in_game_usage(
    fga: float,
    fta: float,
    tov: float,
    minutes: float,
    team_fga: float,
    team_fta: float,
    team_tov: float,
    elapsed_game_minutes: float = 48.0
) -> float:
    """
    Calculate real-time in-game usage rate.
    
    Simplified version of usage rate for live game calculations.
    Uses elapsed game time instead of full 240 team minutes.
    
    Formula: (FGA + 0.44*FTA + TOV) / (Team_FGA + 0.44*Team_FTA + Team_TOV) * (elapsed/5) / minutes
    
    Args:
        fga: Player field goal attempts
        fta: Player free throw attempts
        tov: Player turnovers
        minutes: Player minutes played
        team_fga: Team field goal attempts
        team_fta: Team free throw attempts
        team_tov: Team turnovers
        elapsed_game_minutes: Total game minutes elapsed (max 48)
    
    Returns:
        Usage rate as percentage (0-100 scale)
    
    Example:
        >>> calculate_in_game_usage(12, 4, 1, 24, 45, 18, 8, 24)
        28.5...  # Player using ~28.5% of team possessions
    """
    if minutes <= 0 or team_fga <= 0:
        return 0.0
    
    player_usage = fga + (0.44 * fta) + tov
    team_usage = team_fga + (0.44 * team_fta) + team_tov
    
    if team_usage <= 0:
        return 0.0
    
    # Calculate share of team possessions
    # Normalized to expected 5-man rotation share (elapsed_game_minutes / 5)
    expected_team_minutes = elapsed_game_minutes * 5  # 5 players on court
    usg = 100 * (player_usage / team_usage) * (expected_team_minutes / 5) / minutes
    
    # Clamp to reasonable bounds (0-50% is realistic)
    return max(0.0, min(50.0, usg))



def calculate_assist_rate(
    ast: float,
    minutes: float,
    team_fgm: float,
    player_fgm: float,
    team_minutes: float = 240.0
) -> float:
    """
    Calculate Assist Rate (AST%).
    
    Estimates the percentage of teammate field goals assisted by a player.
    Formula: 100 * AST / (((MP / (Tm MP / 5)) * Tm FGM) - FGM)
    
    Args:
        ast: Player assists
        minutes: Player minutes played
        team_fgm: Team field goals made
        player_fgm: Player field goals made
        team_minutes: Team total minutes
    
    Returns:
        Assist rate as decimal (0.0 to 1.0)
    """
    if minutes <= 0:
        return 0.0
    
    teammate_fgm = team_fgm - player_fgm
    minutes_ratio = minutes / (team_minutes / 5)
    
    eligible_fgm = teammate_fgm * minutes_ratio
    
    if eligible_fgm <= 0:
        return 0.0
    
    ast_pct = ast / eligible_fgm
    
    return max(0.0, min(1.0, ast_pct))


def calculate_per_36(
    stat_value: float,
    minutes_played: float
) -> float:
    """
    Calculate per-36-minutes stat.
    
    Args:
        stat_value: Raw stat count
        minutes_played: Minutes played
    
    Returns:
        Stat normalized to 36 minutes
    """
    if minutes_played <= 0:
        return 0.0
    
    return (stat_value / minutes_played) * 36


def calculate_stats_from_box_score(
    box_score: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate all advanced stats from a standard box score.
    
    Args:
        box_score: Dictionary with keys:
            - pts, fgm, fga, fg3m, fg3a, ftm, fta, min
            - team_fgm, team_fga, team_fta, team_tov (optional)
    
    Returns:
        Dictionary with calculated advanced stats
    """
    result = {}
    
    pts = box_score.get('pts', 0) or 0
    fgm = box_score.get('fgm', 0) or 0
    fga = box_score.get('fga', 0) or 0
    fg3m = box_score.get('fg3m', 0) or 0
    ftm = box_score.get('ftm', 0) or 0
    fta = box_score.get('fta', 0) or 0
    tov = box_score.get('tov', 0) or box_score.get('to', 0) or 0
    minutes = box_score.get('min', 0) or box_score.get('minutes', 0) or 0
    
    # True Shooting
    result['ts_pct'] = calculate_true_shooting(pts, fga, fta)
    
    # Effective FG
    result['efg_pct'] = calculate_effective_fg(fgm, fg3m, fga)
    
    # Usage Rate (if team stats available)
    if 'team_fga' in box_score:
        result['usg_pct'] = calculate_usage_rate(
            fga, fta, tov, minutes,
            box_score.get('team_fga', 90),
            box_score.get('team_fta', 25),
            box_score.get('team_tov', 12)
        )
    
    return result
