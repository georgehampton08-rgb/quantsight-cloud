"""
Shared Core Utils
=================
Platform-agnostic utility functions.
"""

from .game_status import (
    normalize_game_status,
    is_game_active,
    is_game_completed,
    is_game_upcoming,
    GameStatus
)

__all__ = [
    'normalize_game_status',
    'is_game_active',
    'is_game_completed',
    'is_game_upcoming',
    'GameStatus'
]
