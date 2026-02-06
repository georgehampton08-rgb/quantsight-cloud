# Injury Report Setup Guide

## Overview

Simple manual injury tracking system - no unreliable APIs!

## Components

| File | Purpose |
|------|---------|
| [injury_manager.py](file:///C:/Users/georg/quantsight_engine/quantsight_dashboard_v1/backend/services/injury_manager.py) | Manual injury tracking database |
| [injury_scheduler.py](file:///C:/Users/georg/quantsight_engine/quantsight_dashboard_v1/backend/injury_scheduler.py) | 3x daily scheduler |

## Quick Start

### 1. Mark injuries manually

```python
from services.injury_manager import get_injury_manager

mgr = get_injury_manager()

# Mark player as OUT
mgr.mark_injured(
    player_id="2544",
    player_name="LeBron James",
    team="LAL",
    status="OUT",
    injury_desc="Left ankle sprain",
    return_date="2026-02-01"
)

# Clear injury
mgr.mark_healthy("2544")
```

### 2. Setup 3x daily scheduler

**Windows (Task Scheduler):**

```powershell
# Morning (8AM)
schtasks /create /tn "NBA Injury Morning" /tr "python C:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\injury_scheduler.py morning" /sc daily /st 08:00

# Pre-game (5PM - 2hrs before typical 7PM games)
schtasks /create /tn "NBA Injury PreGame" /tr "python C:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\injury_scheduler.py pregame" /sc daily /st 17:00

# Night (11PM)
schtasks /create /tn "NBA Injury Night" /tr "python C:\Users\georg\quantsight_engine\quantsight_dashboard_v1\backend\injury_scheduler.py night" /sc daily /st 23:00
```

**Linux/Mac (crontab):**

```bash
# Edit crontab
crontab -e

# Add these lines:
0 8 * * * cd /path/to/backend && python injury_scheduler.py morning
0 17 * * * cd /path/to/backend && python injury_scheduler.py pregame
0 23 * * * cd /path/to/backend && python injury_scheduler.py night
```

## Manual Test

```bash
# Test morning sync
python injury_scheduler.py morning

# Test pre-game sync
python injury_scheduler.py pregame

# Test night sync
python injury_scheduler.py night
```

## API Usage

```python
from services.injury_manager import get_injury_manager

mgr = get_injury_manager()

# Get player status
status = mgr.get_player_status("2544")
print(status['is_available'])  # True/False

# Get team injuries
lal_injuries = mgr.get_team_injuries("LAL")

# Filter roster (removes OUT/DOUBTFUL)
available, out = mgr.filter_available_players(roster)
```

## Database Tables

- **injuries_current**: Active injury list
- **injury_sync_log**: Sync history

## Future Enhancements

When a reliable injury API becomes available, update `injury_scheduler.py` to fetch automatically.
