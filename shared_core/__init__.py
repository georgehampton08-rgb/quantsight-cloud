"""
QuantSight Shared Core - Platform-Agnostic Analytics Engine

This module contains pure functions and calculation logic that is shared
between Desktop (Electron/SQLite) and Mobile (Firebase/Firestore) backends.

NO PLATFORM-SPECIFIC IMPORTS ALLOWED:
- No sqlite3, firestore, sqlalchemy
- No file I/O (open, Path.write_*)
- No sys.platform or os.name checks

All functions must be pure: data-in, data-out.
"""

__version__ = "1.1.0"
__author__ = "QuantSight Team"

from shared_core.engines import (
    CrucibleCore,
    calculate_pie,
    calculate_live_pie,
    calculate_fatigue_adjustment,
    calculate_defense_friction,
)

from shared_core.calculators import (
    calculate_true_shooting,
    calculate_effective_fg,
    calculate_usage_rate,
    calculate_matchup_grade,
)

from shared_core.utils import (
    normalize_game_status,
    is_game_active,
    is_game_completed,
    is_game_upcoming,
)

__all__ = [
    # Engines
    "CrucibleCore",
    "calculate_pie",
    "calculate_live_pie",
    "calculate_fatigue_adjustment",
    "calculate_defense_friction",
    # Calculators
    "calculate_true_shooting",
    "calculate_effective_fg",
    "calculate_usage_rate",
    "calculate_matchup_grade",
    # Utils
    "normalize_game_status",
    "is_game_active",
    "is_game_completed",
    "is_game_upcoming",
]

