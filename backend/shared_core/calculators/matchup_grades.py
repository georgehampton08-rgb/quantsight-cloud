"""
Matchup Grades Calculator - Pure Functions
==========================================
Platform-agnostic matchup grading logic.
"""

from typing import Dict, Tuple


# Grade boundaries
GRADE_THRESHOLDS = {
    'A': 25,
    'B+': 20,
    'B': 16,
    'C+': 12,
    'C': 8,
    'D': 5,
}


def calculate_matchup_grade(
    projected_points: float,
    matchup_bonus: float = 0.0,
    friction_modifier: float = 0.0
) -> Tuple[str, float]:
    """
    Calculate matchup efficiency grade (A-F scale).
    
    Formula: Score = Projected Points + Matchup Bonus (+/- 3) + Friction Modifier (Friction * 10)
    
    Grade Scale:
    - A: Score >= 25 (Elite Performance)
    - B+: Score >= 20 (Advantaged)
    - B: Score >= 16 (Solid)
    - C+: Score >= 12 (Neutral)
    - C: Score >= 8 (Average)
    - D: Score >= 5 (Sub-optimal)
    - F: Score < 5 (Locked Down / Fade)
    
    Args:
        projected_points: Expected points for the matchup
        matchup_bonus: Positional/matchup advantage (+/- 3 typical)
        friction_modifier: Defensive friction impact (-1 to +1)
    
    Returns:
        Tuple of (grade letter, numeric score)
    
    Example:
        >>> grade, score = calculate_matchup_grade(22, 2.0, 0.15)
        >>> grade
        'A'
    """
    score = projected_points + matchup_bonus + (friction_modifier * 10)
    
    if score >= GRADE_THRESHOLDS['A']:
        grade = 'A'
    elif score >= GRADE_THRESHOLDS['B+']:
        grade = 'B+'
    elif score >= GRADE_THRESHOLDS['B']:
        grade = 'B'
    elif score >= GRADE_THRESHOLDS['C+']:
        grade = 'C+'
    elif score >= GRADE_THRESHOLDS['C']:
        grade = 'C'
    elif score >= GRADE_THRESHOLDS['D']:
        grade = 'D'
    else:
        grade = 'F'
    
    return (grade, score)


def calculate_target_fade_classification(
    projection: float,
    threshold: float,
    *,
    aggregate_variance: float = 0.0,
    stat_variance: float = 0.0,
    aggregate_threshold: float = 0.03,
    stat_threshold: float = 0.05
) -> Tuple[str, str]:
    """
    Classify a player prop as TARGET, FADE, or NEUTRAL.
    
    Uses the QuantSight threshold logic:
    - TARGET: Projection significantly above line
    - FADE: Projection significantly below line
    - NEUTRAL: Projection close to line
    
    Args:
        projection: Projected stat value
        threshold: Line/threshold to compare against
        aggregate_variance: Overall model variance (default 3%)
        stat_variance: Stat-specific variance (default 5%)
        aggregate_threshold: Minimum aggregate variance for classification
        stat_threshold: Minimum stat variance for classification
    
    Returns:
        Tuple of (classification, reason)
    """
    if threshold <= 0:
        return ('NEUTRAL', 'Invalid threshold')
    
    diff_pct = (projection - threshold) / threshold
    
    # Check if variance exceeds thresholds
    if abs(diff_pct) >= stat_threshold:
        if diff_pct > 0:
            return ('TARGET', f'+{diff_pct:.1%} above line')
        else:
            return ('FADE', f'{diff_pct:.1%} below line')
    elif abs(diff_pct) >= aggregate_threshold:
        if diff_pct > 0:
            return ('LEAN TARGET', f'+{diff_pct:.1%} slight edge')
        else:
            return ('LEAN FADE', f'{diff_pct:.1%} slight fade')
    else:
        return ('NEUTRAL', f'{diff_pct:+.1%} within threshold')


def calculate_confidence_score(
    sample_size: int,
    h2h_weight: float = 0.20,
    form_clarity: float = 0.10,
    environment_balance: float = 0.10
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate overall confidence score for a projection.
    
    Based on QuantSight analytical standards:
    - 60% Base Certainty: From stable historical averages
    - 20% H2H Sample: Weighted by sample size
    - 10% Form Clarity: Recent hot/cold streak impact
    - 10% Environmental Balance: Pace, defense, volatility
    
    Args:
        sample_size: Number of head-to-head games
        h2h_weight: Actual H2H contribution (0-0.20)
        form_clarity: Form contribution (0-0.10)
        environment_balance: Environment contribution (0-0.10)
    
    Returns:
        Tuple of (total confidence 0-1, breakdown dict)
    """
    # Base certainty from historical averages
    base = 0.60
    
    # H2H weight scales with sample size
    # 10+ games = full weight, fewer = proportionally less
    h2h_sample_factor = min(1.0, sample_size / 10)
    h2h_contribution = h2h_weight * h2h_sample_factor
    
    # Form and environment as-is
    form_contribution = min(0.10, form_clarity)
    env_contribution = min(0.10, environment_balance)
    
    total = base + h2h_contribution + form_contribution + env_contribution
    total = max(0.0, min(1.0, total))
    
    breakdown = {
        'base': base,
        'h2h': h2h_contribution,
        'form': form_contribution,
        'environment': env_contribution
    }
    
    return (total, breakdown)


def get_grade_color(grade: str) -> str:
    """
    Get display color for a grade.
    
    Args:
        grade: Letter grade (A, B+, B, C+, C, D, F)
    
    Returns:
        CSS color string
    """
    colors = {
        'A': '#22c55e',   # Green
        'B+': '#84cc16',  # Lime
        'B': '#eab308',   # Yellow
        'C+': '#f97316',  # Orange
        'C': '#ef4444',   # Red
        'D': '#dc2626',   # Dark Red
        'F': '#991b1b',   # Very Dark Red
    }
    return colors.get(grade, '#6b7280')  # Gray default
