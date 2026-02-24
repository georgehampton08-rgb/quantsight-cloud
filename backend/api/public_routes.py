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

# ==================== LIVE PULSE (CLOUD PRODUCER) ====================
# Cloud Run uses CloudAsyncPulseProducer (started in main.py) for Firebase writes.
# The old LivePulseCache SSE producer is REMOVED to avoid duplicate NBA API calls.
try:
    from services.async_pulse_producer_cloud import get_cloud_producer
    HAS_PULSE_CACHE = True
    pulse_cache = None  # No more SSE cache; live endpoints use cloud producer / Firestore
    logger.info("[OK] Live pulse routing via CloudAsyncPulseProducer (Firebase)")
except ImportError as e:
    logger.warning(f"[WARN] CloudAsyncPulseProducer not available: {e}")
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
async def search_players_endpoint(q: Optional[str] = Query(None, min_length=0, max_length=50)):
    """
    Search for players by name (for OmniSearch)
    Query params:
        q: Search query string (optional)
    Returns standardized format for frontend Fuse.js:
        - id: player ID
        - name: player name
        - team: team abbreviation
        - position: position
    """
    try:
        # Get ACTIVE players only (current rosters)
        all_players = get_all_players(active_only=True)
        
        if not all_players:
            logger.warning("No players found in database")
            return []
        
        def normalize_player(p):
            """Normalize player data to standard frontend format"""
            return {
                'id': p.get('player_id') or p.get('id') or '',
                'name': p.get('name') or p.get('player_name') or p.get('fullName') or 'Unknown',
                'team': p.get('team') or p.get('team_id') or '',
                'position': p.get('position') or '',
                'avatar': p.get('headshot_url') or ''
            }
        
        # If no query or empty string, return first 100 active players
        if not q or q.strip() == '':
            normalized = [normalize_player(p) for p in all_players[:100]]
            logger.info(f"✅ Returned {len(normalized)} active players (no query)")
            return normalized
        
        # Case-insensitive search
        query_lower = q.lower().strip()
        filtered = []
        for p in all_players:
            # Check multiple common name fields
            name = (p.get('name') or p.get('player_name') or p.get('fullName') or '').lower()
            if query_lower in name:
                filtered.append(normalize_player(p))
        
        # Return top 50 matches
        logger.info(f"✅ Search '{q}' returned {len(filtered[:50])} active players")
        return filtered[:50]
        
    except Exception as e:
        logger.error(f"Player search failed for query '{q}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search temporarily unavailable")


@router.get("/players/{player_id}")
async def get_player_by_id(player_id: str):
    """
    Get player profile by ID
    This endpoint is called by PlayerProfilePage (playerApi.ts line 98)
    """
    try:
        player = firestore_get_player(player_id)
        
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
        
        # Return in format expected by frontend
        return {
            "id": player.get("player_id") or player_id,
            "name": player.get("name") or player.get("player_name") or "Unknown",
            "team": player.get("team") or player.get("team_id") or "",
            "position": player.get("position") or "",
            "avatar": player.get("headshot_url") or "",
            "stats": {
                "ppg": player.get("ppg", 0),
                "rpg": player.get("rpg", 0),
                "apg": player.get("apg", 0),
                "confidence": 85  # Default confidence
            },
            "narrative": f"Statistical analysis for {player.get('name', 'player')}",
            "hitProbability": 0.65,
            "impliedOdds": "-150"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get player {player_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load player profile")


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
async def get_schedule(date: Optional[str] = Query(None), force_refresh: bool = Query(False)):
    """
    Get NBA game schedule from NBA API (VPC-enabled)
    Query params:
        date: Date in YYYY-MM-DD format (default: today)
        force_refresh: Force fresh data, bypass cache
    """
    try:
        target_date = date or str(datetime.now().date())
        
        # Use NBAScheduleService directly (has built-in caching)
        from services.nba_schedule import get_schedule_service
        service = get_schedule_service()
        games_raw = service.get_todays_games(force_refresh=force_refresh)
        
        games = []
        for game in games_raw:
            home_tricode = game.get("home_team", "")
            away_tricode = game.get("away_team", "")
            home_score = game.get("home_score", 0)
            away_score = game.get("away_score", 0)
            status_text = game.get("status_text", "Scheduled")
            status = game.get("status", "scheduled")
            period = game.get("period", 0)
            
            # Determine game state for frontend
            is_live = status.lower() == "live" or (period > 0 and status.lower() != "final")
            is_final = status.lower() == "final"
            
            # Frontend expects flat fields: home, away, home_score, away_score, time, status
            games.append({
                "gameId": game.get("game_id"),
                "game_code": f"{target_date.replace('-', '')}/{away_tricode}{home_tricode}",
                "home": home_tricode,
                "away": away_tricode,
                "home_score": home_score,
                "away_score": away_score,
                "status": "LIVE" if is_live else ("FINAL" if is_final else "SCHEDULED"),
                "time": status_text,
                "period": period,
                "started": is_live or is_final or period > 0,
                "game_time_utc": game.get("game_time"),
                # Keep nested objects for backwards compatibility
                "home_team": {"tricode": home_tricode, "score": home_score, "wins": 0, "losses": 0},
                "away_team": {"tricode": away_tricode, "score": away_score, "wins": 0, "losses": 0},
            })
        
        logger.info(f"✅ [CDN] Fetched {len(games)} games for {target_date}")
        # Frontend ACTUALLY expects object wrapper with "games" key
        return {
            "games": games,
            "date": target_date,
            "total": len(games)
        }
        
    except Exception as e:
        logger.error(f"❌ Schedule error: {e}")
        return {
            "games": [],
            "date": date or str(datetime.now().date()),
            "total": 0
        }


@router.get("/matchup-lab/games")
async def get_matchup_lab_games(force_refresh: bool = Query(False)):
    """
    Get today's games for Matchup Lab (VPC-enabled)
    Returns games in frontend-compatible format
    """
    try:
        # Use NBAScheduleService directly (has built-in caching)
        from services.nba_schedule import get_schedule_service
        service = get_schedule_service()
        games_raw = service.get_todays_games(force_refresh=force_refresh)
        
        games = []
        for game in games_raw:
            status = game.get("status", "scheduled")
            display = game.get("display", "")
            
            games.append({
                "game_id": game.get("game_id", ""),
                "home_team": game.get("home_team", ""),
                "away_team": game.get("away_team", ""),
                "game_time": game.get("status_text", ""),
                "status": status,
                "display": display,
                "home_score": game.get("home_score", 0),
                "away_score": game.get("away_score", 0),
                "period": game.get("period", 0)
            })
        
        logger.info(f"✅ [CDN] Fetched {len(games)} matchup games")
        return {
            "games": games,
            "count": len(games),
            "source": "nba_cdn"
        }
        
    except Exception as e:
        logger.error(f"❌ Matchup lab error: {e}")
        return {"games": [], "count": 0, "error": str(e)}


@router.get("/matchup/roster/{team_id}")
async def get_matchup_roster(team_id: str, game_id: Optional[str] = Query(None)):
    """
    Get team roster with live stats for Matchup Lab.
    Combines player roster with Firebase live stats/averages.
    
    Args:
        team_id: Team abbreviation (e.g., LAL, GSW)
        game_id: Optional game_id to filter live stats
        
    Returns:
        Roster with enriched stats for matchup analysis
    """
    try:
        # Get base roster from Firestore players collection
        players = get_players_by_team(team_id.upper(), active_only=True)
        
        if not players:
            raise HTTPException(status_code=404, detail=f"No roster found for team {team_id}")
        
        # Try to enrich with live Firebase stats
        enriched_players = []
        
        try:
            db = get_firestore_db()
            
            # Get live leaders if available
            live_leaders = {}
            # Read from Firestore live_leaders collection (written by CloudAsyncPulseProducer)
            try:
                leaders_ref = db.collection('live_leaders').document('current')
                leaders_doc = leaders_ref.get()
                if leaders_doc.exists:
                    leaders_list = leaders_doc.to_dict().get('leaders', [])
                    for leader in leaders_list:
                        pid = str(leader.get('player_id', ''))
                        if pid and pid not in live_leaders:
                            live_leaders[pid] = leader
            except Exception:
                pass
            
            # Enrich each player
            for player in players:
                # Normalize player data with strict validation
                player_id = player.get('player_id') or player.get('id')
                
                if not player_id:
                    logger.warning(f"Skipping player without ID in roster for {team_id}")
                    continue
                
                # Extract name (fail if missing)
                name = player.get('name') or player.get('player_name') or player.get('playerName')
                if not name:
                    logger.error(f"Player {player_id} missing name field - data corruption")
                    name = "Unknown"  # Fallback only after logging error
                
                # Build normalized player object
                enriched = {
                    'player_id': str(player_id),
                    'name': name,
                    'team': player.get('team_abbreviation') or player.get('team') or team_id.upper(),
                    'position': player.get('position') or '',
                    'jersey_number': str(player.get('jersey_number') or ''),  # Always string
                    'avatar': player.get('headshot_url') or player.get('avatar') or '',
                    'is_active': player.get('is_active', True),
                    'status': player.get('status') or 'active',
                    'is_in_game': False # Default to false, set to true if live stats found
                }
                
                # Add live stats if available
                if str(player_id) in live_leaders:
                    live = live_leaders[str(player_id)]
                    enriched["live_stats"] = {
                        "pts": live.get('stats', {}).get('pts', 0),
                        "reb": live.get('stats', {}).get('reb', 0),
                        "ast": live.get('stats', {}).get('ast', 0),
                        "fg3m": live.get('stats', {}).get('fg3m', 0),
                        "fga": live.get('stats', {}).get('fga', 0),
                        "min": live.get('stats', {}).get('min', 0),
                        "pie": live.get('pie', 0),
                        "ts_pct": live.get('ts_pct', 0),
                        "efg_pct": live.get('efg_pct', 0),
                    }
                    enriched["is_in_game"] = True
                else:
                    # Get season averages from player_rolling_averages
                    try:
                        avg_ref = db.collection('player_rolling_averages').document(player_id)
                        avg_doc = avg_ref.get()
                        if avg_doc.exists:
                            avgs = avg_doc.to_dict()
                            enriched["season_averages"] = {
                                "pts": avgs.get('avg_pts', 0),
                                "reb": avgs.get('avg_reb', 0),
                                "ast": avgs.get('avg_ast', 0),
                                "fg3m": avgs.get('avg_fg3m', 0),
                                "fga": avgs.get('avg_fga', 0),
                                "min": avgs.get('avg_min', 0),
                                "ts_pct": avgs.get('season_ts_pct', 0),
                            }
                    except Exception:
                        pass
                    
                    enriched["is_in_game"] = False
                
                enriched_players.append(enriched)
                
        except Exception as e:
            logger.warning(f"Could not enrich roster with Firebase stats: {e}")
            # Return basic roster if enrichment fails
            for player in players:
                enriched_players.append({
                    "player_id": str(player.get('player_id') or player.get('id') or ''),
                    "name": player.get('name') or player.get('player_name') or 'Unknown',
                    "team": player.get('team_abbreviation') or team_id.upper(),
                    "position": player.get('position') or '',
                    "is_active": True,
                    "is_in_game": False
                })
        
        logger.info(f"✅ Matchup roster: {len(enriched_players)} players for {team_id}")
        return {
            "team": team_id.upper(),
            "game_id": game_id,
            "roster": enriched_players,
            "count": len(enriched_players),
            "has_live_stats": any(p.get('is_in_game') for p in enriched_players)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching matchup roster for {team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        # Run multi-stat confluence analysis (sync method - do NOT await)
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
        logger.info("[SSE] Client connected to /live/stream (Firestore-backed)")
        last_update_hash = None
        
        try:
            while True:
                if await request.is_disconnected():
                    logger.info("[SSE] Client disconnected")
                    break
                
                # Read live data from Firestore (written by CloudAsyncPulseProducer)
                try:
                    db = get_firestore_db()
                    games_doc = db.collection('live_games').document('current').get()
                    
                    if games_doc.exists:
                        data = games_doc.to_dict()
                        # Simple change detection via update_cycle or hash
                        current_hash = data.get('meta', {}).get('update_cycle', 0)
                        if current_hash != last_update_hash:
                            last_update_hash = current_hash
                            yield {
                                "event": "pulse",
                                "data": json.dumps(data)
                            }
                except Exception as e:
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": f"Firestore read failed: {str(e)}"})
                    }
                
                # Poll Firestore every 3 seconds (CloudAsyncPulseProducer writes every 10s)
                await asyncio.sleep(3)
                
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
    # Read leaders from Firestore (written by CloudAsyncPulseProducer)
    try:
        db = get_firestore_db()
        leaders_ref = db.collection('live_leaders').document('current')
        leaders_doc = leaders_ref.get()
        if leaders_doc.exists:
            leaders_list = leaders_doc.to_dict().get('leaders', [])[:limit]
            return {
                "leaders": leaders_list,
                "count": len(leaders_list),
                "timestamp": datetime.now().isoformat(),
                "source": "firebase"
            }
    except Exception as e:
        logger.warning(f"Failed to read live leaders from Firestore: {e}")
    
    return {
        "leaders": [],
        "count": 0,
        "timestamp": datetime.now().isoformat(),
        "source": "unavailable"
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
    # Read live games from Firestore (written by CloudAsyncPulseProducer)
    try:
        db = get_firestore_db()
        games_ref = db.collection('live_games').document('current')
        games_doc = games_ref.get()
        if games_doc.exists:
            return games_doc.to_dict()
    except Exception as e:
        logger.warning(f"Failed to read live games from Firestore: {e}")
    
    return {
        "games": [],
        "meta": {"game_count": 0, "live_count": 0, "source": "unavailable"}
    }


@router.get("/live/status")
def get_live_status():
    """
    Health check for the live pulse system.
    Shows producer status, update count, and cache size.
    """
    # Return cloud producer status
    try:
        producer = get_cloud_producer()
        if producer:
            return producer.get_status()
    except Exception as e:
        logger.warning(f"Could not get cloud producer status: {e}")
    
    return {
        "status": "unavailable",
        "error": "Cloud producer not running"
    }


# ================== GAME LOGS ENDPOINTS ==================


@router.get("/game-logs")
async def get_game_logs(
    player_id: Optional[str] = Query(None, pattern=r'^\d+$', max_length=20, description="Player ID (numeric)"),
    team_id: Optional[str] = Query(None, pattern=r'^[A-Z]{3}$', description="Team abbreviation (3 letters)"),
    start_date: Optional[str] = Query(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=100, description="Max results (1-100)")
):
    """
    Get game logs from Firestore
    Query params:
        player_id: Filter by player ID (numeric string)
        team_id: Filter by team abbreviation (3-letter code)
        start_date: Filter by start date (YYYY-MM-DD)
        end_date: Filter by end date (YYYY-MM-DD)
        limit: Number of logs to return (default: 50, max: 100)
    """
    try:
        # Validate date range
        if start_date and end_date and end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be greater than or equal to start_date"
            )
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching game logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve game logs")


@router.get("/boxscore/{game_id}")
async def get_boxscore(game_id: str):
    """
    Get aggregated boxscore for a specific game.
    Returns player stats totals for both teams (not quarter-by-quarter logs).
    """
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        from collections import defaultdict
        
        db = get_firestore_db()
        logs_ref = db.collection('game_logs')
        
        # Get all game logs for this game_id
        query = logs_ref.where(filter=FieldFilter('game_id', '==', game_id))
        docs = query.stream()
        
        # Aggregate by player
        player_totals = defaultdict(lambda: {
            'pts': 0, 'reb': 0, 'ast': 0, 'min': 0,
            'fgm': 0, 'fga': 0, 'fg3m': 0, 'fg3a': 0,
            'ftm': 0, 'fta': 0, 'stl': 0, 'blk': 0,
            'tov': 0, 'pf': 0, 'plus_minus': 0,
            'team': '', 'name': '', 'position': '', 'jersey_number': ''
        })
        
        for doc in docs:
            log = doc.to_dict()
            pid = log.get('player_id')
            if not pid:
                continue
            
            # Sum stats
            player_totals[pid]['pts'] += log.get('pts', 0)
            player_totals[pid]['reb'] += log.get('reb', 0)
            player_totals[pid]['ast'] += log.get('ast', 0)
            player_totals[pid]['min'] += log.get('min', 0)
            player_totals[pid]['fgm'] += log.get('fgm', 0)
            player_totals[pid]['fga'] += log.get('fga', 0)
            player_totals[pid]['fg3m'] += log.get('fg3m', 0)
            player_totals[pid]['fg3a'] += log.get('fg3a', 0)
            player_totals[pid]['ftm'] += log.get('ftm', 0)
            player_totals[pid]['fta'] += log.get('fta', 0)
            player_totals[pid]['stl'] += log.get('stl', 0)
            player_totals[pid]['blk'] += log.get('blk', 0)
            player_totals[pid]['tov'] += log.get('tov', 0)
            player_totals[pid]['pf'] += log.get('pf', 0)
            player_totals[pid]['plus_minus'] += log.get('plus_minus', 0)
            
            # Set metadata (from first log entry for this player)
            if not player_totals[pid]['team']:
                player_totals[pid]['team'] = log.get('team', '')
                player_totals[pid]['name'] = log.get('player_name', '')
                player_totals[pid]['position'] = log.get('position', '')
                player_totals[pid]['jersey_number'] = str(log.get('jersey_number', ''))
        
        if not player_totals:
            raise HTTPException(status_code=404, detail=f"No boxscore found for game {game_id}")
        
        # Group by team
        home_team = None
        away_team = None
        home_players = []
        away_players = []
        
        for pid, totals in player_totals.items():
            team = totals['team']
            
            # Calculate percentages
            fg_pct = (totals['fgm'] / totals['fga']) if totals['fga'] > 0 else 0.0
            fg3_pct = (totals['fg3m'] / totals['fg3a']) if totals['fg3a'] > 0 else 0.0
            ft_pct = (totals['ftm'] / totals['fta']) if totals['fta'] > 0 else 0.0
            
            player_summary = {
                'player_id': pid,
                'name': totals['name'],
                'team': team,
                'position': totals['position'],
                'jersey_number': totals['jersey_number'],
                'pts': totals['pts'],
                'reb': totals['reb'],
                'ast': totals['ast'],
                'min': totals['min'],
                'fgm': totals['fgm'],
                'fga': totals['fga'],
                'fg_pct': round(fg_pct, 3),
                'fg3m': totals['fg3m'],
                'fg3a': totals['fg3a'],
                'fg3_pct': round(fg3_pct, 3),
                'ftm': totals['ftm'],
                'fta': totals['fta'],
                'ft_pct': round(ft_pct, 3),
                'stl': totals['stl'],
                'blk': totals['blk'],
                'tov': totals['tov'],
                'pf': totals['pf'],
                'plus_minus': totals['plus_minus']
            }
            
            if not home_team:
                home_team = team
                home_players.append(player_summary)
            elif team == home_team:
                home_players.append(player_summary)
            else:
                if not away_team:
                    away_team = team
                away_players.append(player_summary)
        
        logger.info(f"✅ Returned aggregated boxscore for game {game_id} ({len(home_players) + len(away_players)} players)")
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
            "total_players": len(player_totals)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching boxscore for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve boxscore")

