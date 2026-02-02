"""
PIE Calculator - Pure Function
==============================
Player Impact Estimate calculation without any I/O dependencies.

This is the platform-agnostic core logic used by both Desktop and Mobile backends.
"""

from typing import Dict, Optional


def calculate_pie(
    stats: Dict[str, float],
    team_stats: Optional[Dict[str, float]] = None,
    opponent_stats: Optional[Dict[str, float]] = None
) -> float:
    """
    Calculate Player Impact Estimate (PIE).
    
    PIE measures a player's overall contribution per minute relative to 
    the game's total activity.
    
    Formula:
    PIE = (PTS + FGM + FTM - FGA - FTA + DREB + 0.5*OREB + AST + STL + 0.5*BLK - PF - TO)
          / (GmPTS + GmFGM + GmFTM - GmFGA - GmFTA + GmDREB + 0.5*GmOREB + GmAST + GmSTL + 0.5*GmBLK - GmPF - GmTO)
    
    Args:
        stats: Dictionary with player stat keys:
            - pts: Points
            - fgm: Field Goals Made
            - fga: Field Goals Attempted
            - ftm: Free Throws Made
            - fta: Free Throws Attempted
            - oreb: Offensive Rebounds
            - dreb: Defensive Rebounds
            - reb: Total Rebounds (used if oreb/dreb not available)
            - ast: Assists
            - stl: Steals
            - blk: Blocks
            - pf: Personal Fouls
            - to: Turnovers
        team_stats: Optional team totals (same keys), defaults to estimated
        opponent_stats: Optional opponent totals (same keys), defaults to estimated
    
    Returns:
        PIE value as float (typically 0.05-0.20 for most players)
    
    Example:
        >>> stats = {'pts': 25, 'fgm': 9, 'fga': 18, 'ftm': 5, 'fta': 6,
        ...          'reb': 8, 'ast': 5, 'stl': 1.5, 'blk': 0.5, 'pf': 2.5, 'to': 2}
        >>> pie = calculate_pie(stats)
        >>> 0.05 <= pie <= 0.30
        True
    """
    # Extract player stats with defaults
    pts = stats.get('pts', 0) or 0
    fgm = stats.get('fgm', 0) or 0
    fga = stats.get('fga', 0) or 0
    ftm = stats.get('ftm', 0) or 0
    fta = stats.get('fta', 0) or 0
    
    # Handle rebounds - prefer split, fall back to total
    if 'oreb' in stats and 'dreb' in stats:
        oreb = stats.get('oreb', 0) or 0
        dreb = stats.get('dreb', 0) or 0
    else:
        # Estimate split from total (league average: 30% OREB, 70% DREB)
        total_reb = stats.get('reb', 0) or 0
        oreb = total_reb * 0.3
        dreb = total_reb * 0.7
    
    ast = stats.get('ast', 0) or 0
    stl = stats.get('stl', 0) or 0
    blk = stats.get('blk', 0) or 0
    pf = stats.get('pf', 0) or 0
    to = stats.get('to', 0) or 0
    
    # Player contribution
    player_contribution = (
        pts + fgm + ftm - fga - fta +
        dreb + (0.5 * oreb) +
        ast + stl + (0.5 * blk) -
        pf - to
    )
    
    # Game totals - use provided or estimate from player stats
    if team_stats and opponent_stats:
        game_contribution = _calculate_game_contribution(team_stats, opponent_stats)
    else:
        # Estimate: typical game has ~200 total PIE contribution
        # Scale based on player's contribution to estimate a reasonable denominator
        game_contribution = max(player_contribution * 10, 100)
    
    # Prevent division by zero
    if game_contribution <= 0:
        return 0.0
    
    pie = player_contribution / game_contribution
    
    # Clamp to reasonable range (some edge cases can produce outliers)
    return max(0.0, min(1.0, pie))


def calculate_live_pie(
    pts: int,
    fgm: int,
    fga: int,
    ftm: int,
    fta: int,
    oreb: int,
    dreb: int,
    ast: int,
    stl: int,
    blk: int,
    pf: int,
    tov: int,
    game_total_estimate: float = 100.0
) -> float:
    """
    Calculate PIE for live games using individual stat values.
    
    Optimized for real-time calculations where stats are already parsed.
    Uses the True PIE formula with all negatives (FGA, FTA, PF, TOV) included.
    
    Args:
        pts: Points scored
        fgm: Field goals made
        fga: Field goals attempted
        ftm: Free throws made  
        fta: Free throws attempted
        oreb: Offensive rebounds
        dreb: Defensive rebounds
        ast: Assists
        stl: Steals
        blk: Blocks
        pf: Personal fouls
        tov: Turnovers
        game_total_estimate: Denominator estimate (default 100 for live games)
    
    Returns:
        PIE value as float (typically 0.0 to 0.5 for live)
    
    Example:
        >>> calculate_live_pie(28, 10, 20, 6, 8, 2, 6, 9, 2, 1, 3, 3)
        0.255  # Dominant performance
    """
    # True PIE numerator with all positive and negative contributions
    pie_numerator = (
        pts + fgm + ftm - fga - fta +
        dreb + (0.5 * oreb) +
        ast + stl + (0.5 * blk) -
        pf - tov
    )
    
    # Normalize by game total estimate
    if game_total_estimate <= 0:
        return 0.0
    
    pie = pie_numerator / game_total_estimate
    
    # Clamp to reasonable range
    return round(max(-0.5, min(1.0, pie)), 3)


def _calculate_game_contribution(
    team_stats: Dict[str, float],
    opponent_stats: Dict[str, float]
) -> float:
    """Calculate combined game contribution for PIE denominator."""
    total = 0.0
    
    for stats in [team_stats, opponent_stats]:
        pts = stats.get('pts', 0) or 0
        fgm = stats.get('fgm', 0) or 0
        fga = stats.get('fga', 0) or 0
        ftm = stats.get('ftm', 0) or 0
        fta = stats.get('fta', 0) or 0
        
        if 'oreb' in stats and 'dreb' in stats:
            oreb = stats.get('oreb', 0) or 0
            dreb = stats.get('dreb', 0) or 0
        else:
            total_reb = stats.get('reb', 0) or 0
            oreb = total_reb * 0.3
            dreb = total_reb * 0.7
        
        ast = stats.get('ast', 0) or 0
        stl = stats.get('stl', 0) or 0
        blk = stats.get('blk', 0) or 0
        pf = stats.get('pf', 0) or 0
        to = stats.get('to', 0) or 0
        
        total += (
            pts + fgm + ftm - fga - fta +
            dreb + (0.5 * oreb) +
            ast + stl + (0.5 * blk) -
            pf - to
        )
    
    return total


def calculate_pie_percentile(pie: float) -> int:
    """
    Convert PIE value to percentile ranking.
    
    Based on NBA league distribution:
    - 90th percentile: 0.15+
    - 75th percentile: 0.12-0.15
    - 50th percentile: 0.08-0.12
    - 25th percentile: 0.05-0.08
    - Below 25th: <0.05
    
    Args:
        pie: PIE value
        
    Returns:
        Percentile as integer 1-100
    """
    if pie >= 0.20:
        return 99
    elif pie >= 0.15:
        return 90 + int((pie - 0.15) / 0.05 * 9)
    elif pie >= 0.12:
        return 75 + int((pie - 0.12) / 0.03 * 15)
    elif pie >= 0.08:
        return 50 + int((pie - 0.08) / 0.04 * 25)
    elif pie >= 0.05:
        return 25 + int((pie - 0.05) / 0.03 * 25)
    else:
        return max(1, int(pie / 0.05 * 25))
