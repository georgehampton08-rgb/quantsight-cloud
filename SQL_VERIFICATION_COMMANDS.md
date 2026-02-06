# QuantSight Database Schema Verification Script

# Run these SQL commands in Google Cloud Shell to verify your database schema

## Connect to your database first

```bash
gcloud sql connect quantsight-db --user=quantsight --database=nba_data
# Enter password: QSInvest2026$
```

## Then run these SQL commands in the psql prompt

### 1. List all tables

```sql
\dt
```

### 2. Check teams table schema

```sql
\d teams
```

**Expected columns by backend code:**

- team_id
- full_name
- tricode
- city
- state  
- year_founded

### 3. Check players table schema

```sql
\d players
```

**Expected columns by backend code:**

- player_id
- full_name
- team_abbreviation
- position
- height
- weight

### 4. Check player_rolling_averages table schema

```sql
\d player_rolling_averages
```

**Expected columns by backend code:**

- player_id
- points_avg
- rebounds_avg
- assists_avg
- fg_pct
- three_pct
- ft_pct
- games_played
- last_updated

### 5. Test queries that backend uses

#### Test teams query

```sql
SELECT team_id, full_name, tricode, city, state, year_founded
FROM teams
WHERE UPPER(tricode) = 'LAL'
LIMIT 1;
```

#### Test players query

```sql
SELECT player_id, full_name, team_abbreviation, position, height, weight
FROM  players
WHERE player_id = '2544'
LIMIT 1;
```

#### Test player averages query

```sql
SELECT points_avg, rebounds_avg, assists_avg, fg_pct, three_pct, ft_pct, games_played
FROM player_rolling_averages
WHERE player_id = '2544'
ORDER BY last_updated DESC
LIMIT 1;
```

### 6. Check for common issues

#### Check if tables exist

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;
```

#### Check actual column names in teams

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'teams'
ORDER BY ordinal_position;
```

#### Check actual column names in players

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'players'
ORDER BY ordinal_position;
```

#### Check actual column names in player_rolling_averages

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'player_rolling_averages'
ORDER BY ordinal_position;
```

---

## What to look for

1. **Table names:** Are they exactly `teams`, `players`, `player_rolling_averages`?
2. **Column names:** Do they match exactly what the backend expects? (case-sensitive!)
3. **Data types:** Are player_id/team_id strings or integers?
4. **Data exists:** Are there actually rows in these tables?

## Share the output

Once you run these commands, copy the output and share it with me.  
I'll then update the backend code to match your actual database schema!
