"""
Public API Routes for Cloud Backend - FIRESTORE VERSION
Provides endpoints for frontend consumption using Firebase Firestore
"""
from fastapi import APIRouter, HTTPException, Query, Request
import os
import logging
from typing import Optional
from datetime import datetime, date as date_type

# Import Firestore helpers
from firestore_db import (
    get_all_teams,
    get_team_by_tricode,
    get_all_players,
    get_player_by_id as firestore_get_player,
    get_players_by_team,
    get_player_stats,
    get_team_stats,
    get_firestore_db
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ==================== LIVE PULSE CACHE (VPC-ENABLED) ====================
# Initialize hot cache for live game stats (desktop pattern with VPC)
try:
    from services.live_pulse_service_cloud import get_pulse_cache
    pulse_cache = get_pulse_cache()
    pulse_cache_thread = pulse_cache.start_producer()  # Background NBA API polling every 10s
    HAS_PULSE_CACHE = True
    logger.info(f"[OK] LivePulseCache v{pulse_cache.VERSION} producer started (VPC-enabled)")
except Exception as e:
    logger.warning(f"[WARN] LivePulseCache not available: {e}")
    HAS_PULSE_CACHE = False
    pulse_cache = None

# ================== TEAMS ENDPOINTS ==================

@router.get("/debug/teams-schema")
async def debug_teams_schema():
    """Debug endpoint to check teams collection structure"""
    try:
        teams = get_all_teams()
        
        if not teams:
            return {
                "status": "empty",
                "message": "No teams found in Firestore",
                "teams_count": 0
            }
        
        # Return first team as sample
        sample_team = teams[0]
        
        return {
            "status": "success",
            "teams_count": len(teams),
            "sample_team": sample_team,
            "fields": list(sample_team.keys())
        }
    except Exception as e:
        logger.error(f"Error debugging teams schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/teams")
async def get_teams():
    """
    Get all NBA teams organized by conference and division.
    Returns structure expected by CascadingSelector:
    {
        "conferences": [
            {
                "name": "Eastern",
                "divisions": [
                    {"name": "Atlantic", "teams": [...]}
                ]
            }
        ]
    }
    """
    try:
        teams = get_all_teams()
        
        # NBA division structure
        NBA_STRUCTURE = {
            "Eastern": {
                "Atlantic": ["BOS", "BKN", "NYK", "PHI", "TOR"],
                "Central": ["CHI", "CLE", "DET", "IND", "MIL"],
                "Southeast": ["ATL", "CHA", "MIA", "ORL", "WAS"]
            },
            "Western": {
                "Northwest": ["DEN", "MIN", "OKC", "POR", "UTA"],
                "Pacific": ["GSW", "LAC", "LAL", "PHX", "SAC"],
                "Southwest": ["DAL", "HOU", "MEM", "NOP", "SAS"]
            }
        }
        
        # Create team lookup by abbreviation
        team_lookup = {}
        for team in teams:
            abbr = team.get("abbreviation") or team.get("id") or ""
            team_lookup[abbr.upper()] = {
                "id": abbr.upper(),
                "name": team.get("full_name", team.get("name", abbr)),
                "abbreviation": abbr.upper()
            }
        
        # Build conferences structure
        conferences = []
        for conf_name, divisions in NBA_STRUCTURE.items():
            conf_divisions = []
            for div_name, team_abbrs in divisions.items():
                div_teams = []
                for abbr in team_abbrs:
                    if abbr in team_lookup:
                        div_teams.append(team_lookup[abbr])
                    else:
                        # Placeholder for missing teams
                        div_teams.append({
                            "id": abbr,
                            "name": abbr,
                            "abbreviation": abbr
                        })
                conf_divisions.append({
                    "name": div_name,
                    "teams": div_teams
                })
            conferences.append({
                "name": conf_name,
                "divisions": conf_divisions
            })
        
        logger.info(f"✅ Returned {len(teams)} teams organized in conferences/divisions")
        return {"conferences": conferences}
        
    except Exception as e:
        logger.error(f"Error fetching teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players")
async def get_all_players_endpoint(is_active: Optional[bool] = Query(None)):
    """
    Get all players for OmniSearch
    Query params:
        is_active: Filter for active players only (default: None, returns all)
    """
    try:
        # Default to active only if parameter not specified
        active_filter = is_active if is_active is not None else True
        
        players = get_all_players(active_only=active_filter)
        
        logger.info(f"✅ Returned {len(players)} players (active_only={active_filter})")
        return players
        
    except Exception as e:
        logger.error(f"Error fetching players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players/search")
async def search_players_endpoint(q: str = Query("")):
    """
    Search for players by name (for OmniSearch)
    Query params:
        q: Search query string
    Returns standardized format for frontend Fuse.js:
        - id: player ID
        - name: player name
        - team: team abbreviation
        - position: position
    """
    try:
        # Get ACTIVE players only (current rosters)
        all_players = get_all_players(active_only=True)
        
        def normalize_player(p):
            """Normalize player data to standard frontend format"""
            return {
                'id': p.get('player_id') or p.get('id') or '',
                'name': p.get('name') or p.get('player_name') or p.get('fullName') or 'Unknown',
                'team': p.get('team') or p.get('team_id') or '',
                'position': p.get('position') or '',
                'avatar': p.get('headshot_url') or ''
            }
        
        if not q:
            # Return all active players normalized
            normalized = [normalize_player(p) for p in all_players[:100]]
            return normalized
        
        # Case-insensitive search
        query_lower = q.lower()
        filtered = []
        for p in all_players:
            # Check multiple common name fields
            name = p.get('name') or p.get('player_name') or p.get('playerName') or p.get('fullName') or ""
            if query_lower in name.lower():
                filtered.append(normalize_player(p))
        
        logger.info(f"✅ Search '{q}' returned {len(filtered)} active players")
        return filtered[:50]  # Limit results
        
    except Exception as e:
        logger.error(f"Error searching players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roster/{team_id}")
async def get_team_roster(team_id: str):
    """
    Get roster (players) for a specific team
    """
    try:
        players = get_players_by_team(team_id.upper())
        
        logger.info(f"✅ Returned {len(players)} players for team {team_id}")
        return players
        
    except Exception as e:
        logger.error(f"Error fetching roster for {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== NEXUS ENDPOINTS ==================
# Nexus service now implemented in backend/nexus/routes.py
# Old stub endpoints deleted - new service provides full functionality


# ================== GAME LOGS ENDPOINTS ==================

@router.get("/api/game-logs")
async def game_logs_alias(
    player_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Alias for /game-logs to handle legacy /api/ prefix
    Redirects to main game_logs endpoint
    """
    return await get_game_logs(player_id, team_id, start_date, end_date, limit)


@router.get("/injuries")
async def get_injuries():
    """
    Get injury data (placeholder - returns empty for now)
    TODO: Implement injury data from Firestore
    """
    return []


@router.get("/schedule")
async def get_schedule(date: Optional[str] = Query(None)):
    """
    Get NBA game schedule from NBA API (VPC-enabled with caching)
    Cache TTL: 10 minutes
    Query params:
        date: Date in YYYY-MM-DD format (default: today)
    """
    try:
        # Import cache
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from nba_cache import nba_cache
        import asyncio
        
        target_date = date or str(datetime.now().date())
        cache_key = f"schedule_{target_date}"
        
        # Check cache first (10 min TTL)
        cached_data = nba_cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ [CACHE HIT] Schedule for {target_date} ({len(cached_data.get('games', []))} games)")
            return cached_data
        
        # Cache miss - fetch from NBA API via VPC
        logger.info(f"⏳ [VPC] Fetching schedule from NBA API for {target_date}")
        
        def fetch_nba_schedule():
            """NBA API call (runs through VPC connector)"""
            from nba_api.live.nba.endpoints import scoreboard
            import time
            time.sleep(0.6)  # Rate limit
            return scoreboard.ScoreBoard().get_dict()
        
        # Async execution
        loop = asyncio.get_event_loop()
        scoreboard_data = await loop.run_in_executor(None, fetch_nba_schedule)
        
        games = []
        if 'scoreboard' in scoreboard_data and 'games' in scoreboard_data['scoreboard']:
            for game in scoreboard_data['scoreboard']['games']:
                home_tricode = game.get("homeTeam", {}).get("teamTricode", "")
                away_tricode = game.get("awayTeam", {}).get("teamTricode", "")
                home_score = game.get("homeTeam", {}).get("score", 0)
                away_score = game.get("awayTeam", {}).get("score", 0)
                game_status = game.get("gameStatus", 1)
                game_status_text = game.get("gameStatusText", "Scheduled")
                
                # Determine status string
                status_str = "SCHEDULED"
                if game_status == 2:
                    status_str = "LIVE"
                elif game_status == 3:
                    status_str = "FINAL"
                
                games.append({
                    # NBA API format (nested)
                    "gameId": game.get("gameId"),
                    "game_code": game.get("gameCode"),
                    "status": game_status_text,
                    "home_team": {
                        "tricode": home_tricode,
                        "score": home_score,
                        "wins": game.get("homeTeam", {}).get("wins", 0),
                        "losses": game.get("homeTeam", {}).get("losses", 0)
                    },
                    "away_team": {
                        "tricode": away_tricode,
                        "score": away_score,
                        "wins": game.get("awayTeam", {}).get("wins", 0),
                        "losses": game.get("awayTeam", {}).get("losses", 0)
                    },
                    "period": game.get("period", 0),
                    "game_time_utc": game.get("gameTimeUTC"),
                    "arena": game.get("arenaName", ""),
                    
                    # Flat format for Command Center compatibility
                    "home": home_tricode,
                    "away": away_tricode,
                    "home_score": home_score,
                    "away_score": away_score,
                    "time": game_status_text,
                    "started": game_status >= 2,
                    "volatility": "High" if game_status == 2 else "Normal"
                })
        
        result = {
            "games": games,
            "date": target_date,
            "total": len(games),
            "cached": False,
            "source": "nba_api_vpc"
        }
        
        # Cache for 10 minutes
        nba_cache.set(cache_key, result, ttl_minutes=10)
        logger.info(f"✅ [VPC] Fetched {len(games)} games, cached for 10min")
        return result
        
    except Exception as e:
        logger.error(f"❌ [VPC] Schedule error: {e}")
        return {
            "games": [],
            "date": date or str(datetime.now().date()),
            "error": str(e),
            "note": "VPC connector required for NBA API access"
        }


@router.get("/matchup-lab/games")
async def get_matchup_lab_games():
    """
    Get today's games for Matchup Lab (VPC-enabled with caching)
    Returns games in frontend-compatible format
    Cache TTL: 5 minutes
    """
    try:
        # Import cache
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from nba_cache import nba_cache
        import asyncio
        
        cache_key = "matchup_lab_games"
        
        # Check cache (5 min for live updates)
        cached_data = nba_cache.get(cache_key)
        if cached_data:
            logger.info(f"✅ [CACHE HIT] Matchup Lab ({len(cached_data.get('games', []))} games)")
            return cached_data
        
        # Fetch from NBA API via VPC
        logger.info("⏳ [VPC] Fetching matchup lab games from NBA API")
        
        def fetch_games():
            from nba_api.live.nba.endpoints import scoreboard
            import time
            time.sleep(0.6)
            return scoreboard.ScoreBoard().get_dict()
        
        loop = asyncio.get_event_loop()
        scoreboard_data = await loop.run_in_executor(None, fetch_games)
        
        games = []
        if 'scoreboard' in scoreboard_data and 'games' in scoreboard_data['scoreboard']:
            for game in scoreboard_data['scoreboard']['games']:
                home_tricode = game.get("homeTeam", {}).get("teamTricode", "")
                away_tricode = game.get("awayTeam", {}).get("teamTricode", "")
                game_status = game.get("gameStatus", 1)
                game_time = game.get("gameStatusText", "")
                
                # Determine status
                status = "scheduled"
                if game_status == 2:
                    status = "live"
                elif game_status == 3:
                    status = "final"
                
                # Create display string (matches frontend expectation)
                home_score = game.get("homeTeam", {}).get("score", 0)
                away_score = game.get("awayTeam", {}).get("score", 0)
                
                if status == "live":
                    display = f"{away_tricode} @ {home_tricode} - {game_time}"
                elif status == "final":
                    display = f"{away_tricode} {away_score} @ {home_tricode} {home_score} (F)"
                else:
                    display = f"{away_tricode} @ {home_tricode} - {game_time}"
                
                games.append({
                    "game_id": game.get("gameId", ""),
                    "home_team": home_tricode,
                    "away_team": away_tricode,
                    "game_time": game_time,
                    "status": status,
                    "display": display,
                    # Additional data for analysis
                    "home_score": home_score,
                    "away_score": away_score,
                    "period": game.get("period", 0)
                })
        
        # Wrap in object with games key (frontend expects data.games)
        result = {
            "games": games,
            "count": len(games),
            "cached": False,
            "source": "nba_api_vpc"
        }
        
        # Cache for 5 minutes
        nba_cache.set(cache_key, result, ttl_minutes=5)
        logger.info(f"✅ [VPC] Fetched {len(games)} matchup games, cached for 5min")
        return result
        
    except Exception as e:
        logger.error(f"❌ [VPC] Matchup lab error: {e}")
        return {"games": [], "count": 0, "error": str(e)}


@router.get("/roster/{team_id}")
async def get_roster(team_id: str):
    """Get team roster from players collection"""
    try:
        players = get_players_by_team(team_id, active_only=True)
        
        if not players:
            raise HTTPException(status_code=404, detail=f"No roster found for team {team_id}")
        
        logger.info(f"✅ Returned {len(players)} players for {team_id}")
        return players
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching roster for {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/teams/{team_abbrev}")
async def get_team_by_abbrev(team_abbrev: str):
    """Get individual team information"""
    try:
        team = get_team_by_tricode(team_abbrev)
        
        if not team:
            raise HTTPException(status_code=404, detail=f"Team {team_abbrev} not found")
        
        # Get team stats if available
        team_stats_data = get_team_stats(team_abbrev)
        if team_stats_data:
            team["stats"] = team_stats_data
        
        logger.info(f"✅ Returned team {team_abbrev}")
        return team
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching team {team_abbrev}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== PLAYER ENDPOINTS ==================

@router.get("/player/{player_id}")
async def get_player_by_id_endpoint(player_id: str):
    """Get individual player profile with stats"""
    try:
        player = firestore_get_player(player_id)
        
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        
        # Get player stats if available
        stats = get_player_stats(player_id)
        if stats:
            player["stats"] = stats
        
        logger.info(f"✅ Returned player {player_id}")
        return player
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching player {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ================== PWA COMPATIBILITY ENDPOINTS ==================

@router.post("/settings/gemini-key")
async def save_gemini_key(data: dict):
    """Save Gemini API key to Cloud Secret Manager (placeholder)"""
    # This would integrate with Google Secret Manager in production
    return {
        "success": True,
        "message": "Gemini key saved (placeholder - not yet implemented)"
    }


@router.get("/matchup-lab/games")
async def get_matchup_lab_games():
    """Get today's games for Matchup Lab - reuses schedule endpoint"""
    return await get_schedule()


@router.get("/analyze/usage-vacuum")
async def analyze_usage_vacuum(player_ids: str = ""):
    """Analyze usage vacuum for players when teammates are out (placeholder)"""
    return {
        "analysis": "Usage vacuum analysis coming soon",
        "player_ids": player_ids.split(",") if player_ids else []
    }


# ================== MATCHUP ANALYSIS (FULL CONFLUENCE) ==================

# Initialize Multi-Stat Confluence Engine (Firestore Cloud Version) and AI Insights
try:
    from services.multi_stat_confluence_cloud import MultiStatConfluenceCloud
    from services.ai_insights import GeminiInsights
    multi_stat_engine = MultiStatConfluenceCloud()
    ai_insights_engine = GeminiInsights()
    HAS_MATCHUP_ENGINE = True
    logger.info("[OK] MultiStatConfluenceCloud engine initialized (Firestore)")
except Exception as e:
    logger.warning(f"[WARN] Matchup engine not available: {e}")
    HAS_MATCHUP_ENGINE = False
    multi_stat_engine = None
    ai_insights_engine = None


@router.get("/matchup/analyze")
async def analyze_matchup(
    game_id: str = Query(None, description="Game ID (optional)"),
    home_team: str = Query(None, description="Home team abbreviation"),
    away_team: str = Query(None, description="Away team abbreviation")
):
    """
    Full player projection analysis for a matchup using MultiStatConfluence.
    
    Returns per-player projections with:
    - Season averages (baseline)
    - Defense-adjusted projections
    - Head-to-head historical performance
    - Form factors (HOT/COLD/STEADY)
    - Matchup grades (A+, A, B, C, D, F)
    - AI-generated insights via Gemini
    """
    if not HAS_MATCHUP_ENGINE:
        # Graceful fallback when engine unavailable (P1 fix - avoids 503 incidents)
        return {
            'success': False,
            'error': 'Matchup analysis engine temporarily unavailable',
            'fallback': True,
            'game_id': game_id,
            'game': f"{away_team} @ {home_team}" if home_team and away_team else None,
            'matchup_context': {},
            'projections': [],
            'insights': {'summary': 'Engine offline. Try again later.', 'ai_powered': False}
        }
    
    if not (home_team and away_team):
        raise HTTPException(status_code=400, detail="Both home_team and away_team are required")
    
    try:
        # Run multi-stat confluence analysis
        confluence_data = multi_stat_engine.analyze_game(home_team.upper(), away_team.upper())
        
        # Add game_id to response if provided
        if game_id:
            confluence_data['game_id'] = game_id
        
        # Generate AI insights
        insights = {}
        if ai_insights_engine:
            try:
                insights = ai_insights_engine.generate_insights(confluence_data)
            except Exception as e:
                logger.error(f"AI insights error: {e}")
                insights = {
                    'summary': 'Analysis complete. Review player projections for details.',
                    'top_plays': [],
                    'fade_plays': [],
                    'ai_powered': False
                }
        
        return {
            'success': True,
            'game_id': game_id,
            'game': confluence_data.get('game', f"{away_team} @ {home_team}"),
            'generated_at': confluence_data.get('generated_at'),
            'matchup_context': confluence_data.get('matchup_context', {}),
            'projections': confluence_data.get('projections', []),
            'insights': insights,
            'ai_powered': insights.get('ai_powered', False),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing matchup {home_team} vs {away_team}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/crucible")
async def crucible_simulation(data: dict = None):
    """Run Crucible simulation for matchup scenarios (placeholder)"""
    return {
        "simulation": "Crucible simulation coming soon",
        "note": "This feature requires Vertex Engine (desktop only)"
    }


# ================== LIVE STATS ENDPOINTS (SSE) ==================

@router.get("/live/stream")
async def live_stats_stream(request: Request):
    """
    SSE endpoint for real-time live game stats (DESKTOP PATTERN WITH VPC).
    All clients stream from shared LivePulseCache - no per-client NBA API hits.
    
    Updates pushed every 1s (checks cache for changes).
    Data includes:
    - All live games with scores and clock
    - Top 10 players by in-game PIE
    - Stat changes for gold pulse animation
    """
    from sse_starlette.sse import EventSourceResponse
    from fastapi import Request
    import asyncio
    import json
    
    async def event_generator():
        logger.info("[SSE] Client connected to /live/stream (VPC HOT CACHE)")
        last_update_cycle = 0
        
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("[SSE] Client disconnected")
                    break
                
                if HAS_PULSE_CACHE and pulse_cache:
                    data = pulse_cache.get_latest()
                    
                    # Only send if there's new data
                    current_cycle = data.get('meta', {}).get('update_cycle', 0)
                    if current_cycle != last_update_cycle:
                        last_update_cycle = current_cycle
                        yield {
                            "event": "pulse",
                            "data": json.dumps(data)
                        }
                else:
                    # No cache available
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Live pulse cache not available"})
                    }
                
                # Check for updates every 1 second
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("[SSE] Live stream cancelled")
        except Exception as e:
            logger.error(f"[SSE] Stream error: {e}")
    
    return EventSourceResponse(event_generator())


@router.get("/live/leaders")
async def get_live_leaders_endpoint(limit: int = Query(10)):
    """
    Get top live players from LivePulseCache by PIE.
    Used for Alpha Leaderboard component.
    """
    if not HAS_PULSE_CACHE or not pulse_cache:
        return {
            "leaders": [],
            "error": "Live pulse cache not available",
            "count": 0
        }
    
    return {
        "leaders": pulse_cache.get_leaders(limit=limit),
        "count": limit,
        "timestamp": datetime.now().isoformat(),
        "source": "vpc_hot_cache"
    }


@router.get("/game-dates")
async def get_game_dates(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    """
    Get list of dates that have game log data available
    Used by frontend calendar to highlight available dates
    
    Query params:
        start_date: Filter dates >= this date (YYYY-MM-DD)
        end_date: Filter dates <= this date (YYYY-MM-DD)
    
    Returns: Array of date strings in YYYY-MM-DD format
    Cache: 1 hour (dates don't change frequently)
    """
    try:
        db = get_firestore_db()
        logs_ref = db.collection('game_logs')
        
        # Build query with optional date filters
        query = logs_ref
        if start_date:
            query = query.where('game_date', '>=', start_date)
        if end_date:
            query = query.where('game_date', '<=', end_date)
        
        # Fetch documents and extract unique dates
        docs = query.stream()
        dates = set()
        
        for doc in docs:
            data = doc.to_dict()
            if 'game_date' in data and data['game_date']:
                dates.add(data['game_date'])
        
        # Sort dates and return
        sorted_dates = sorted(list(dates))
        logger.info(f"Found {len(sorted_dates)} distinct game dates")
        
        return {
            "dates": sorted_dates,
            "count": len(sorted_dates),
            "range": {
                "start": sorted_dates[0] if sorted_dates else None,
                "end": sorted_dates[-1] if sorted_dates else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching game dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/live/games")
def get_live_games():
    """
    REST endpoint for current live game data.
    Returns the same data as /live/stream but as a single snapshot.
    """
    if not HAS_PULSE_CACHE or not pulse_cache:
        return {
            "games": [],
            "error": "Live pulse cache not available",
            "meta": {"game_count": 0, "live_count": 0}
        }
    
    return pulse_cache.get_latest()


@router.get("/live/status")
def get_live_status():
    """
    Health check for the live pulse system.
    Shows producer status, update count, and cache size.
    """
    if not HAS_PULSE_CACHE or not pulse_cache:
        return {
            "status": "unavailable",
            "error": "Live pulse cache not available"
        }
    
    return pulse_cache.get_status()
@router.get("/live/games")
async def get_live_games_endpoint():
    """Get all currently live NBA games from Firestore."""
    try:
        db = get_firestore_db()
        
        # Query live games collection
        games_ref = db.collection('live_games')
        docs = games_ref.stream()
        
        live_games = []
        for doc in docs:
            game_data = doc.to_dict()
            game_data['game_id'] = doc.id
            
            # Only include if status is 'live'
            if game_data.get('status') == 'live':
                live_games.append(game_data)
        
        return {
            "status": "ok",
            "count": len(live_games),
            "games": live_games,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[LiveGames] Error: {e}")
        return {
            "status": "error",
            "games": [],
            "error": str(e)
        }


# ================== GAME LOGS ENDPOINTS ==================

@router.get("/game-logs")
async def get_game_logs(
    player_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get game logs from Firestore
    Query params:
        player_id: Filter by player ID
        team_id: Filter by team abbreviation  
        start_date: Filter by start date (YYYY-MM-DD)
        end_date: Filter by end date (YYYY-MM-DD)
        limit: Number of logs to return (default: 50, max: 100)
    """
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        
        db = get_firestore_db()
        logs_ref = db.collection('game_logs')
        
        # Build query
        query = logs_ref
        if player_id:
            query = query.where(filter=FieldFilter('player_id', '==', str(player_id)))
        if team_id:
            query = query.where(filter=FieldFilter('team', '==', team_id.upper()))
        if start_date:
            query = query.where(filter=FieldFilter('game_date', '>=', start_date))
        if end_date:
            query = query.where(filter=FieldFilter('game_date', '<=', end_date))
        
        query = query.limit(limit)
        docs = query.stream()
        
        logs = []
        for doc in docs:
            log_data = doc.to_dict()
            log_data['id'] = doc.id
            logs.append(log_data)
        
        logger.info(f"Returned {len(logs)} game logs (filters: player={player_id}, dates={start_date} to {end_date})")
        return {
            "logs": logs,
            "count": len(logs),
            "filters_applied": {
                "player_id": player_id,
                "team_id": team_id,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching game logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/boxscore/{game_id}")
async def get_boxscore(game_id: str):
    """
    Get boxscore for a specific game
    Returns player stats for both teams in the game
    """
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        
        db = get_firestore_db()
        logs_ref = db.collection('game_logs')
        
        # Get all game logs for this game_id
        query = logs_ref.where(filter=FieldFilter('game_id', '==', game_id))
        docs = query.stream()
        
        player_stats = []
        for doc in docs:
            stat = doc.to_dict()
            stat['id'] = doc.id
            player_stats.append(stat)
        
        if not player_stats:
            raise HTTPException(status_code=404, detail=f"No boxscore found for game {game_id}")
        
        # Group by team
        home_team = None
        away_team = None
        home_players = []
        away_players = []
        
        for stat in player_stats:
            team_abbr = stat.get('team_abbreviation')
            if not home_team:
                home_team = team_abbr
                home_players.append(stat)
            elif team_abbr == home_team:
                home_players.append(stat)
            else:
                if not away_team:
                    away_team = team_abbr
                away_players.append(stat)
        
        logger.info(f"✅ Returned boxscore for game {game_id}")
        return {
            "game_id": game_id,
            "home_team": {
                "abbreviation": home_team,
                "players": home_players
            },
            "away_team": {
                "abbreviation": away_team,
                "players": away_players
            },
            "total_players": len(player_stats)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching boxscore for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

