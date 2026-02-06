"""
Game Status Normalizer - Pure Function Utility
===============================================
Converts NBA API game status codes to canonical strings.
Centralized source of truth to prevent string drift across services.
"""

from typing import Literal


# Canonical game status values
GameStatus = Literal['UPCOMING', 'LIVE', 'FINAL', 'UNKNOWN']


def normalize_game_status(status_code: int) -> GameStatus:
    """
    Convert NBA API game status codes to canonical strings.
    
    NBA API Status Codes:
        1 = Game not yet started (UPCOMING)
        2 = Game in progress (LIVE)
        3 = Game finished (FINAL)
    
    Args:
        status_code: Integer status from NBA API (gameStatus field)
    
    Returns:
        Canonical status string: 'UPCOMING', 'LIVE', 'FINAL', or 'UNKNOWN'
    """
    status_map = {
        1: 'UPCOMING',
        2: 'LIVE',
        3: 'FINAL'
    }
    return status_map.get(status_code, 'UNKNOWN')


def is_game_active(status_code: int) -> bool:
    """Check if a game is currently in progress."""
    return status_code == 2


def is_game_completed(status_code: int) -> bool:
    """Check if a game has finished."""
    return status_code == 3


def is_game_upcoming(status_code: int) -> bool:
    """Check if a game hasn't started yet."""
    return status_code == 1
