"""
Shared Core Adapters
====================
Platform-agnostic adapters for external API normalization.
"""

from .nba_api_adapter import (
    NBAApiAdapter,
    AsyncNBAApiAdapter,
    NormalizedPlayerStats,
    NormalizedGameInfo,
    NormalizedBoxScore,
    get_nba_adapter
)

__all__ = [
    'NBAApiAdapter',
    'AsyncNBAApiAdapter', 
    'NormalizedPlayerStats',
    'NormalizedGameInfo',
    'NormalizedBoxScore',
    'get_nba_adapter'
]
