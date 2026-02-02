# QuantSight Shared Core

Platform-agnostic analytics engine for QuantSight Desktop and Mobile backends.

## Overview

This module contains pure calculation functions shared between:

- **Desktop**: Electron + SQLite (PostgreSQL for production)
- **Mobile**: Firebase + Firestore

All functions are **pure** - no I/O, no database access, no platform-specific code.

## Installation

```bash
# As submodule in Desktop project
cd quantsight_dashboard_v1
git submodule add https://github.com/YOUR_ORG/quantsight-shared-core.git shared_core

# As submodule in Cloud project
cd quantsight_cloud_build
git submodule add https://github.com/YOUR_ORG/quantsight-shared-core.git shared_core
```

## Usage

```python
from shared_core import (
    calculate_pie,
    calculate_fatigue_adjustment,
    calculate_true_shooting,
    calculate_matchup_grade,
)

# PIE Calculation
stats = {'pts': 25, 'fgm': 9, 'fga': 18, 'reb': 8, 'ast': 5, ...}
pie = calculate_pie(stats)

# Fatigue Adjustment
from datetime import date
result = calculate_fatigue_adjustment(
    date(2026, 2, 1), 
    is_road=True, 
    recent_games=[{'date': '2026-01-31'}]
)
print(result.modifier)  # -0.08 (B2B road penalty)

# Matchup Grading
grade, score = calculate_matchup_grade(22, matchup_bonus=2.0, friction_modifier=0.15)
print(grade)  # 'A'
```

## Module Structure

```
shared_core/
├── engines/
│   ├── crucible_core.py     # Simulation logic (Markov, play selection)
│   ├── pie_calculator.py    # Player Impact Estimate
│   ├── fatigue_engine.py    # Schedule-based fatigue
│   └── defense_matrix.py    # Defensive friction
├── calculators/
│   ├── advanced_stats.py    # TS%, eFG%, USG%
│   └── matchup_grades.py    # A-F grading, TARGET/FADE
└── tests/
    └── test_pure_functions.py
```

## Pure Function Rules

1. **No Database Imports**: No `sqlite3`, `firestore`, `sqlalchemy`
2. **No File I/O**: No `open()`, `Path().write_*()`
3. **No Platform Detection**: No `sys.platform`, `os.name`
4. **Data-In, Data-Out**: Accept dicts/dataframes, return results
5. **Type Hints Required**: All parameters and returns typed

## Running Tests

```bash
cd shared_core
python -m pytest tests/ -v
```

## Version

- **v1.0.0** - Initial release with core engines and calculators
