# QuantSight API Endpoint Mapping

## Overview

This document maps frontend API calls to their corresponding backend endpoints, enabling AI-assisted analysis and debugging.

---

## Frontend → Backend Endpoint Map

### Player Endpoints

| Frontend Call | Backend Route | File | Method | Status |
|--------------|---------------|------|--------|--------|
| `/players/search?q={query}` | `/players/search` | `public_routes.py` | GET | ✅ Active |
| `/players/{id}` | `/players/{player_id}` | `public_routes.py` | GET | ✅ Active |
| `/players/{id}/play-types` | `/players/{player_id}/play-types` | `public_routes.py` | GET | ⚠️ Stub (returns empty) |
| `/players/{id}/refresh` | `/players/{player_id}/refresh` | `public_routes.py` | POST | ✅ Active |

### Team & Roster Endpoints

| Frontend Call | Backend Route | File | Method | Status |
|--------------|---------------|------|--------|--------|
| `/teams` | `/teams` | `public_routes.py` | GET | ✅ Active |
| `/roster/{team_id}` | `/roster/{team_id}` | `public_routes.py` | GET | ✅ Active (wrapped format) |

### Matchup & Analysis Endpoints

| Frontend Call | Backend Route | File | Method | Status |
|--------------|---------------|------|--------|--------|
| `/matchup/analyze?player_id={id}&opponent={team}` | `/matchup/analyze` | `public_routes.py` | GET | ⚠️ Param mismatch see note |
| `/radar/{player_id}?opponent_id={team}` | `/radar/{player_id}` | (Unknown) | GET | 🔍 Verify existence |

> **Note on `/matchup/analyze`**: Frontend passes `player_id` and `opponent`, but backend expects `home_team` and `away_team`. This mismatch causes "Analysis Data Unavailable" errors.

### Simulation & AI Endpoints

| Frontend Call | Backend Route | File | Method | Status |
|--------------|---------------|------|--------|--------|
| `/api/simulate` (from Aegis) | Unknown | - | POST | 🔍 Verify existence |
| `/ai/insights/{player_id}` | Unknown | - | GET | 🔍 Verify existence |

### Schedule & Game Endpoints

| Frontend Call | Backend Route | File | Method | Status |
|--------------|---------------|------|--------|--------|
| `/schedule` | `/schedule` | `public_routes.py` | GET | ✅ Active |
| `/schedule/today` | `/schedule/today` | `public_routes.py` | GET | ✅ Active |
| `/game-logs` | `/api/game-logs` | `public_routes.py` | GET | ✅ Active |

---

## Response Format Contracts

### Player Profile (`/players/{id}`)

```json
{
  "id": "string",
  "name": "string",
  "team": "string",
  "position": "string",
  "avatar": "string",
  "height": "string",        // Added Rev 00060
  "weight": "string",        // Added Rev 00060
  "experience": "string",    // Added Rev 00060
  "stats": {
    "ppg": number,
    "rpg": number,
    "apg": number,
    "confidence": number
  },
  "narrative": "string",
  "hitProbability": number,
  "impliedOdds": "string"
}
```

### Roster (`/roster/{team_id}`)

```json
{
  "roster": [
    {
      "player_id": "string",
      "name": "string",
      "position": "string",
      "jersey_number": "string",
      "status": "string"
    }
  ]
}
```

### Play Types Stub (`/players/{id}/play-types`)

```json
{
  "player_id": "string",
  "player_name": "string",
  "season": "string",
  "play_types": []
}
```

### Simulation Result (from Aegis Orchestrator)

```json
{
  "projections": {
    "floor": { "points": number, "rebounds": number, "assists": number, "threes": number },
    "expected_value": { ... },
    "ceiling": { ... }
  },
  "confidence": {
    "score": number,
    "grade": "string"
  },
  "modifiers": {
    "archetype": "string",
    "usage_boost": number
  },
  "schedule_context": {
    "is_road": boolean,
    "is_b2b": boolean,
    "days_rest": number,
    "modifier": number
  },
  "game_mode": {
    "blowout_pct": number,   // Critical: Must exist or use optional chaining
    "clutch_pct": number,
    "mode": "string"
  },
  "momentum": {
    "hot_streak": boolean,
    "cold_streak": boolean
  },
  "defender_profile": {
    "primary_defender": "string",
    "dfg_pct": number,
    "pct_plusminus": number
  }
}
```

---

## Known Issues & Fixes

### 1. Game Mode Undefined Error

**Problem**: `Cannot read properties of undefined (reading 'blowout_pct')`  
**Root Cause**: `game_mode` object missing from simulation response  
**Fix**: Added optional chaining in `ProjectionMatrix.tsx`:

```tsx
blowoutPct={game_mode?.blowout_pct || 0}
clutchPct={game_mode?.clutch_pct || 0}
```

### 2. Matchup Analyze Parameter Mismatch

**Problem**: Frontend passes `player_id` and `opponent`, backend expects `home_team` and `away_team`  
**Status**: ⚠️ Unresolved - causes "Analysis Data Unavailable"  
**Recommendation**: Update frontend call or create adapter endpoint

### 3. Missing Player Vitals

**Problem**: HEIGHT, WEIGHT, EXP showing blank  
**Root Cause**: Firestore player documents missing these fields  
**Fix**: Added fallback displays (`player.height || "N/A"`) in `HeroSection.tsx`

---

## Frontend Components → API Mapping

| Component | Endpoints Used | Purpose |
|-----------|----------------|---------|
| `PlayerProfilePage.tsx` | `/players/{id}`, `/game-logs`, `/matchup/analyze` | Main player view |
| `MatchupEnginePage.tsx` | `/teams`, `/matchup/analyze`, `/players/search`, `/radar/{id}` | Matchup analysis |
| `ProjectionMatrix.tsx` | (Receives simulation data from parent) | Display projections |
| `HeroSection.tsx` | (Receives player profile from parent) | Display player vitals |
| `CascadingSelector.tsx` | `/teams`, `/roster/{team}` | Team/player selection |

---

## Deployment History

| Revision | Date | Changes |
|----------|------|---------|
| 00060 | 2026-02-06 | Added player vitals, play-types stub |
| 00059 | 2026-02-06 | H2H hierarchical migration, AI upgrade |
| Frontend f52679 | 2026-02-06 | Game mode null safety, vitals fallbacks |

---

## Testing Endpoints

```bash
# Test player profile
curl https://quantsight-cloud-458498663186.us-central1.run.app/players/2544

# Test roster
curl https://quantsight-cloud-458498663186.us-central1.run.app/roster/LAL

# Test play-types stub
curl https://quantsight-cloud-458498663186.us-central1.run.app/players/2544/play-types

# Test matchup analyze (note parameter requirements)
curl "https://quantsight-cloud-458498663186.us-central1.run.app/matchup/analyze?home_team=LAL&away_team=GSW"
```

---

## AI Analysis Context

This document enables AI to:

- **Map frontend errors to backend routes** (e.g., 404s → missing endpoints)
- **Trace data flow** (Component → API call → Backend handler)
- **Identify contract mismatches** (Parameter names, response formats)
- **Suggest fixes** (Add stubs, update parameters, add null safety)

**Last Updated**: 2026-02-06  
**Maintained By**: Deployment automation
