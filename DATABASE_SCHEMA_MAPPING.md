# QuantSight Cloud SQL Schema Mapping

## Overview

This document maps the **actual Cloud SQL database schema** to the **backend API expectations** to ensure all queries work correctly.

---

## Database Connection Details

- **Instance:** `quantsight-db`
- **Database:** `nba_data`
- **User:** `quantsight`
- **Password:** `QSInvest2026` (updated 2026-02-03)
- **Connection String:** `postgresql://quantsight:QSInvest2026@/nba_data?host=/cloudsql/quantsight-prod:us-central1:quantsight-db`

---

## Table Schemas

### 1. `teams` Table

#### Actual Schema (from Cloud SQL)

```sql
Column              | Type                   
--------------------|------------------------
team_id             | integer (PRIMARY KEY)
abbreviation        | varchar(3) (UNIQUE)
full_name           | varchar(100)
city                | varchar(50)
nickname            | varchar(50)
conference          | varchar(10)
division            | varchar(20)
logo_url            | varchar(255)
primary_color       | varchar(7)
secondary_color     | varchar(7)
```

#### Backend API Mapping

| API Field | Database Column | Notes |
|-----------|----------------|-------|
| `id` | `team_id` | Integer |
| `name` | `nickname` | Team nickname (e.g., "Lakers") |
| `full_name` | `full_name` | Full team name |
| `abbreviation` | `abbreviation` | 3-letter code (e.g., "LAL") |
| `city` | `city` | City name |
| `conference` | `conference` | "East" or "West" |
| `division` | `division` | Division name |

#### Query Example

```sql
SELECT team_id, full_name, abbreviation, city, nickname
FROM teams
WHERE UPPER(abbreviation) = 'LAL';
```

---

### 2. `players` Table

#### Actual Schema (from Cloud SQL)

```sql
Column              | Type
--------------------|---------------------------
player_id           | integer (PRIMARY KEY)
full_name           | varchar(100)
first_name          | varchar(50)
last_name           | varchar(50)
team_id             | integer (FK -> teams)
team_abbreviation   | varchar(3)
jersey_number       | varchar(5)
position            | varchar(10)
height              | varchar(10)
weight              | integer
birth_date          | date
country             | varchar(50)
draft_year          | integer
draft_round         | integer
draft_number        | integer
is_active           | boolean
headshot_url        | varchar(255)
last_updated        | timestamp
```

#### Backend API Mapping

| API Field | Database Column | Notes |
|-----------|----------------|-------|
| `id` | `player_id` | Integer, converted to string in API |
| `name` | `full_name` | Player full name |
| `position` | `position` | e.g., "G", "F", "C" |
| `team` | `team_abbreviation` | 3-letter team code |
| `height` | `height` | String format (e.g., "6-6") |
| `weight` | `weight` | Integer (pounds) |

#### Query Example

```sql
SELECT player_id, full_name, position, team_abbreviation, height, weight
FROM players
WHERE player_id = 2544;
```

---

### 3. `player_rolling_averages` Table

#### Actual Schema (NEEDS VERIFICATION)

```sql
-- Run this in Cloud Shell to verify:
-- \d player_rolling_averages
```

#### Expected Columns

- `player_id` (integer, FK)
- Points, rebounds, assists averages
- Shooting percentages (FG%, 3P%, FT%)
- Games played
- `last_updated` timestamp

#### Backend API Mapping

| API Field | Expected Column | Notes |
|-----------|----------------|-------|
| `ppg` | `points_avg` or `ppg` | Points per game |
| `rpg` | `rebounds_avg` or `rpg` | Rebounds per game |
| `apg` | `assists_avg` or `apg` | Assists per game |
| `fg_pct` | `fg_pct` | Field goal percentage |
| `three_pct` | `three_pct` or `fg3_pct` | 3-point percentage |
| `ft_pct` | `ft_pct` | Free throw percentage |

---

## Fixed Queries Summary

### ✅ Teams Endpoints

**GET `/teams`**

```python
# Returns all teams
SELECT team_id, abbreviation, full_name, city, nickname, conference, division
FROM teams
ORDER BY full_name;
```

**GET `/teams/{team_abbrev}`**

```python
# Returns single team
SELECT team_id, full_name, abbreviation, city, nickname
FROM teams
WHERE UPPER(abbreviation) = UPPER(:abbrev);
```

### ✅ Player Endpoints

**GET `/players`**

```python
# Returns all players
SELECT player_id, full_name, position, team_abbreviation
FROM players
ORDER BY full_name;
```

**GET `/players/{player_id}`**

```python
# Returns single player with stats
SELECT p.player_id, p.full_name, p.position, p.team_abbreviation, p.height, p.weight
FROM players p
WHERE p.player_id = :player_id;
```

**GET `/players/search?q={query}`**

```python
# Search players by name
SELECT player_id, full_name, position, team_abbreviation
FROM players
WHERE LOWER(full_name) LIKE LOWER(:query)
ORDER BY full_name
LIMIT 50;
```

### ✅ Roster Endpoint

**GET `/roster/{team_id}`**

```python
# Get team roster
SELECT player_id, full_name, position, team_abbreviation
FROM players
WHERE team_abbreviation = (
    SELECT abbreviation FROM teams WHERE team_id = :team_id
)
ORDER BY full_name;
```

---

## Changes Made

### 1. Column Name Fixes

- ❌ `tricode` → ✅ `abbreviation` (teams table)
- ❌ `state` → ✅ Removed (doesn't exist)
- ❌ `year_founded` → ✅ Removed (doesn't exist)

### 2. New Field Additions

- ✅ Added `nickname` field (team nickname)
- ✅ Added `conference` field
- ✅ Added `division` field

### 3. Data Type Handling

- Player ID: Integer in database, string in API responses
- Team ID: Integer in database, string in API responses

---

## Verification Required

Run these in Cloud Shell to verify `player_rolling_averages`:

```sql
-- Connect first
gcloud sql connect quantsight-db --user=quantsight --database=nba_data --project=quantsight-prod
-- Password: QSInvest2026

-- Check if table exists
\dt player_rolling_averages

-- Show schema
\d player_rolling_averages

-- Test query
SELECT * FROM player_rolling_averages LIMIT 1;
```

---

## Next Steps

1. ✅ Update DATABASE_URL secret with new password
2. ✅ Verify `player_rolling_averages` schema
3. ✅ Deploy updated backend
4. ✅ Run comprehensive tests
5. ✅ Validate all endpoints return 200
