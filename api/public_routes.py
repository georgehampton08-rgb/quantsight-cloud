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


# NOTE: /roster/{team_id} is defined below (L373) with active_only filtering + 404 handling.
# The duplicate here was removed to prevent route shadowing.


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
            
            games.append({
                "gameId": game.get("game_id"),
                "game_code": f"{target_date.replace('-', '')}/{away_tricode}{home_tricode}",
                "status": status_text,
                "home_team": {
                    "tricode": home_tricode,
                    "score": home_score,
                    "wins": 0,
                    "losses": 0
                },
                "away_team": {
                    "tricode": away_tricode,
                    "score": away_score,
                    "wins": 0,
                    "losses": 0
                },
                "period": game.get("period", 0),
                "game_time_utc": game.get("game_time"),
                "arena": "",
                
                # Flat format for Command Center compatibility
                "home": home_tricode,
                "away": away_tricode,
                "home_score": home_score,
                "away_score": away_score,
                "time": status_text,
                "started": status in ["live", "final"],
                "volatility": "High" if status == "live" else "Normal"
            })
        
        logger.info(f"✅ [CDN] Fetched {len(games)} games for {target_date}")
        return {
            "games": games,
            "date": target_date,
            "total": len(games),
            "source": "nba_cdn"
        }
        
    except Exception as e:
        logger.error(f"❌ Schedule error: {e}")
        return {
            "games": [],
            "date": date or str(datetime.now().date()),
            "error": str(e)
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


@router.get("/roster/{team_id}")
async def get_roster(team_id: str):
    """Get team roster from players collection.
    Returns wrapped format: {team_id, team_name, roster, source, count}
    matching the desktop API contract expected by the frontend.
    """
    try:
        players = get_players_by_team(team_id, active_only=True)

        if not players:
            raise HTTPException(status_code=404, detail=f"No roster found for team {team_id}")

        # Get team name from team data
        team = get_team_by_tricode(team_id)
        team_name = team.get('full_name', team.get('name', team_id)) if team else team_id

        logger.info(f"✅ Returned {len(players)} players for {team_id}")
        return {
            "team_id": team_id.upper(),
            "team_name": team_name,
            "roster": players,
            "source": "firestore",
            "count": len(players)
        }

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
@router.get("/players/{player_id}")
async def get_player_by_id_endpoint(player_id: str):
    """Get individual player profile with stats.
    Accepts both /player/{id} and /players/{id} for frontend compatibility.
    """
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


# NOTE: /matchup-lab/games is defined above (L332) with full NBAScheduleService implementation.
# The duplicate stub here was removed to prevent route shadowing.


@router.get("/analyze/usage-vacuum")
async def analyze_usage_vacuum(player_ids: str = ""):
    """Legacy GET endpoint for usage vacuum (kept for backwards compat)."""
    return {
        "analysis": "Use POST /usage-vacuum/analyze for full calculation",
        "player_ids": player_ids.split(",") if player_ids else []
    }


@router.post("/usage-vacuum/analyze")
async def usage_vacuum_analyze(data: dict):
    """Usage vacuum analysis: redistribute usage from injured players.

    When high-usage players are out, their share gets redistributed
    proportionally to remaining roster members based on existing usage.

    Input: {team_id, injured_player_ids: [], remaining_roster: [{player_id, name, usage}]}
    Output: {redistribution: [{player_id, player_name, usage_change, pts_ev_change, ...}]}
    """
    try:
        injured_ids = data.get('injured_player_ids', [])
        remaining = data.get('remaining_roster', [])

        if not injured_ids or not remaining:
            return {"redistribution": []}

        # Calculate total usage freed by injured players
        total_freed = 0.0
        for pid in injured_ids:
            pstats = get_player_stats(str(pid))
            if pstats:
                ppg = pstats.get('points_avg', 0)
                # Estimate usage rate from scoring: usage ~= ppg / 1.1
                usage = min(35, ppg / 1.1) if ppg > 0 else 10
                total_freed += usage

        if total_freed <= 0:
            return {"redistribution": []}

        # Calculate total remaining usage for proportional distribution
        total_remaining_usage = sum(p.get('usage', 10) for p in remaining)
        if total_remaining_usage <= 0:
            total_remaining_usage = len(remaining) * 10

        redistribution = []
        for p in remaining:
            pid = p.get('player_id', '')
            name = p.get('name', '')
            existing_usage = p.get('usage', 10)

            # Proportional share of freed usage
            share = existing_usage / total_remaining_usage
            usage_boost = total_freed * share

            # Get base stats for EV change calculation
            pstats = get_player_stats(str(pid))
            ppg = pstats.get('points_avg', 0) if pstats else 0
            apg = pstats.get('assists_avg', 0) if pstats else 0
            rpg = pstats.get('rebounds_avg', 0) if pstats else 0

            # EV changes proportional to usage boost
            boost_pct = usage_boost / max(existing_usage, 1)
            pts_change = ppg * boost_pct * 0.8  # 80% efficiency on extra usage
            ast_change = apg * boost_pct * 0.5
            reb_change = rpg * boost_pct * 0.3

            redistribution.append({
                "player_id": pid,
                "player_name": name,
                "usage_change": round(usage_boost, 2),
                "pts_ev_change": round(pts_change, 1),
                "ast_ev_change": round(ast_change, 1),
                "reb_ev_change": round(reb_change, 1),
            })

        # Sort by pts_ev_change descending
        redistribution.sort(key=lambda x: x['pts_ev_change'], reverse=True)

        return {"redistribution": redistribution}

    except Exception as e:
        logger.error(f"Usage vacuum error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


# ================== PLAYER MATCHUP ENDPOINT ==================

@router.get("/matchup/{player_id}/{opponent}")
async def get_player_matchup(player_id: str, opponent: str):
    """Player-level matchup analysis.
    Returns defense_matrix, nemesis_vector, pace_friction, insight
    matching the MatchupResult interface expected by the frontend.
    """
    try:
        player = firestore_get_player(player_id)
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

        stats = get_player_stats(player_id)
        ppg = 0.0
        rpg = 0.0
        apg = 0.0
        fg = 0.0
        if stats:
            ppg = stats.get('points_avg', 0)
            rpg = stats.get('rebounds_avg', 0)
            apg = stats.get('assists_avg', 0)
            fg = stats.get('fg_pct', 0.45)

        # H2H lookup (non-blocking, returns None if missing)
        h2h_avg = ppg
        h2h_games = 0
        if HAS_MATCHUP_ENGINE and multi_stat_engine:
            h2h = multi_stat_engine.get_h2h_history(player_id, opponent)
            if h2h and h2h.get('games', 0) > 0:
                h2h_avg = h2h.get('pts', ppg)
                h2h_games = h2h.get('games', 0)

        delta_pct = ((h2h_avg - ppg) / ppg * 100) if ppg > 0 else 0

        # Nemesis grade
        if delta_pct >= 10:
            grade, status = 'A', 'DOMINANT'
        elif delta_pct >= 3:
            grade, status = 'B', 'FAVORABLE'
        elif delta_pct >= -3:
            grade, status = 'C', 'NEUTRAL'
        elif delta_pct >= -10:
            grade, status = 'D', 'TOUGH'
        else:
            grade, status = 'F', 'NEMESIS'

        # Insight text
        if delta_pct > 3:
            insight_text = f"{player.get('name', 'Player')} has historically dominated vs {opponent} (+{delta_pct:.1f}% above baseline)"
            insight_type = 'success'
        elif delta_pct < -3:
            insight_text = f"{player.get('name', 'Player')} struggles vs {opponent} ({delta_pct:.1f}% below baseline)"
            insight_type = 'warning'
        else:
            insight_text = f"{player.get('name', 'Player')} performs near baseline vs {opponent}"
            insight_type = 'neutral'

        return {
            "defense_matrix": {
                "paoa": round(fg * 100, 1),
                "rebound_resistance": "high" if rpg >= 8 else "medium" if rpg >= 4 else "low",
                "profile": {
                    "scoring": round(ppg, 1),
                    "rebounding": round(rpg, 1),
                    "playmaking": round(apg, 1),
                }
            },
            "nemesis_vector": {
                "grade": grade,
                "status": status,
                "avg_vs_opponent": round(h2h_avg, 1),
                "delta_percent": round(delta_pct, 1),
                "h2h_games": h2h_games,
            },
            "pace_friction": {
                "multiplier": 1.0,
                "projected_pace": "average",
            },
            "insight": {
                "text": insight_text,
                "type": insight_type,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in player matchup {player_id} vs {opponent}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== RADAR DIMENSIONS ENDPOINT ==================

@router.get("/radar/{player_id}")
async def get_radar_dimensions(player_id: str, opponent_id: str = Query("NBA")):
    """Radar chart dimensions for player profile matchup tab.
    Returns player_stats and opponent_defense radar shapes.
    """
    try:
        stats = get_player_stats(player_id)
        if not stats:
            # Use league-average defaults rather than 404 — radar still renders
            logger.info(f"No stats for {player_id}, using league-average defaults for radar")
            stats = {
                "points_avg": 0.0, "rebounds_avg": 0.0, "assists_avg": 0.0,
                "fg_pct": 0.45, "three_p_pct": 0.33
            }

        ppg = stats.get('points_avg', 0)
        rpg = stats.get('rebounds_avg', 0)
        apg = stats.get('assists_avg', 0)
        fg = stats.get('fg_pct', 0.45)
        tp = stats.get('three_p_pct', 0.33)

        # Normalize to 0-100 scale for radar
        scoring = min(100, (ppg / 35) * 100)
        playmaking = min(100, (apg / 12) * 100)
        rebounding = min(100, (rpg / 15) * 100)
        defense = min(100, (fg * 100 + tp * 50) / 1.5)  # Composite
        pace = 50.0  # Neutral default

        # Opponent defense profile (league-average baseline)
        opp_scoring = 50.0
        opp_playmaking = 50.0
        opp_rebounding = 50.0
        opp_defense = 55.0
        opp_pace = 50.0

        return {
            "player_stats": {
                "scoring": round(scoring, 1),
                "playmaking": round(playmaking, 1),
                "rebounding": round(rebounding, 1),
                "defense": round(defense, 1),
                "pace": round(pace, 1),
            },
            "opponent_defense": {
                "scoring": round(opp_scoring, 1),
                "playmaking": round(opp_playmaking, 1),
                "rebounding": round(opp_rebounding, 1),
                "defense": round(opp_defense, 1),
                "pace": round(opp_pace, 1),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting radar for {player_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== AEGIS TEAM MATCHUP ENDPOINT ==================

@router.get("/aegis/matchup")
async def aegis_team_matchup(
    home_team_id: str = Query(..., description="Home team abbreviation or ID"),
    away_team_id: str = Query(..., description="Away team abbreviation or ID"),
    game_date: str = Query(None, description="Game date YYYY-MM-DD")
):
    """Team-level matchup analysis for MatchupWarRoom.
    Returns both team rosters with player projections and matchup edge.
    """
    from datetime import datetime as dt

    try:
        home_players = get_players_by_team(home_team_id.upper(), active_only=True)
        away_players = get_players_by_team(away_team_id.upper(), active_only=True)

        if not home_players and not away_players:
            raise HTTPException(status_code=404, detail="Neither team found")

        def build_team_data(players, team_id):
            team_data = []
            for p in players[:15]:
                pid = p.get('player_id', p.get('id', ''))
                pstats = get_player_stats(str(pid))
                ppg = pstats.get('points_avg', 0) if pstats else 0
                rpg = pstats.get('rebounds_avg', 0) if pstats else 0
                apg = pstats.get('assists_avg', 0) if pstats else 0

                team_data.append({
                    "player_id": str(pid),
                    "player_name": p.get('name', ''),
                    "position": p.get('position', ''),
                    "is_active": True,
                    "health_status": "green",
                    "ev_points": round(ppg, 1),
                    "ev_rebounds": round(rpg, 1),
                    "ev_assists": round(apg, 1),
                    "archetype": _infer_archetype(ppg, rpg, apg),
                    "matchup_advantage": "neutral",
                    "efficiency_grade": _grade_from_ppg(ppg),
                    "usage_boost": 0.0,
                    "vacuum_beneficiary": False,
                })
            return team_data

        home_data = build_team_data(home_players, home_team_id)
        away_data = build_team_data(away_players, away_team_id)

        home_team_info = get_team_by_tricode(home_team_id.upper())
        away_team_info = get_team_by_tricode(away_team_id.upper())

        return {
            "home_team": {
                "team_id": home_team_id.upper(),
                "team_name": home_team_info.get('full_name', home_team_info.get('name', home_team_id)) if home_team_info else home_team_id,
                "offensive_archetype": "Balanced",
                "defensive_profile": "Standard",
                "active_count": len(home_players),
                "out_count": 0,
                "players": home_data,
            },
            "away_team": {
                "team_id": away_team_id.upper(),
                "team_name": away_team_info.get('full_name', away_team_info.get('name', away_team_id)) if away_team_info else away_team_id,
                "offensive_archetype": "Balanced",
                "defensive_profile": "Standard",
                "active_count": len(away_players),
                "out_count": 0,
                "players": away_data,
            },
            "matchup_edge": "neutral",
            "edge_reason": "Even matchup based on available data",
            "usage_vacuum_applied": [],
            "execution_time_ms": 0,
            "game_date": game_date or dt.now().strftime("%Y-%m-%d"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in aegis matchup {home_team_id} vs {away_team_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _infer_archetype(ppg, rpg, apg):
    """Infer player archetype from basic stats."""
    if apg >= 7:
        return "Playmaker"
    if ppg >= 20 and rpg < 6:
        return "Scorer"
    if rpg >= 10:
        return "Rim Protector"
    if ppg >= 15:
        return "Three-and-D"
    return "Role Player"


def _grade_from_ppg(ppg):
    """Simple efficiency grade from scoring average."""
    if ppg >= 25:
        return "A"
    if ppg >= 18:
        return "B"
    if ppg >= 12:
        return "C"
    if ppg >= 6:
        return "D"
    return "F"


@router.post("/analyze/crucible")
async def crucible_simulation_legacy(data: dict = None):
    """Legacy crucible endpoint. Use POST /matchup-lab/crucible-sim instead."""
    return {"simulation": "Use POST /matchup-lab/crucible-sim", "legacy": True}


@router.post("/matchup-lab/crucible-sim")
async def crucible_sim(data: dict = None):
    """Run Crucible simulation for a matchup.

    Input: {home_team: str, away_team: str, num_simulations: int}
    Output: {home_team_stats, away_team_stats, final_score, was_clutch, was_blowout, key_events, execution_time_ms}
    """
    import time as _time
    import numpy as _np

    if not data:
        raise HTTPException(status_code=400, detail="Request body required")

    raw_home = data.get('home_team', '')
    raw_away = data.get('away_team', '')
    n_sims = min(data.get('num_simulations', 200), 500)  # Cap at 500 for cloud

    # Accept both string ("LAL") and dict ({team_id: "LAL", players: [...]}) formats
    home_abbr = raw_home.get('team_id', '') if isinstance(raw_home, dict) else str(raw_home)
    away_abbr = raw_away.get('team_id', '') if isinstance(raw_away, dict) else str(raw_away)
    home_abbr = home_abbr.upper() if home_abbr else ''
    away_abbr = away_abbr.upper() if away_abbr else ''

    # If frontend sent embedded players, use them directly
    embedded_home = raw_home.get('players', []) if isinstance(raw_home, dict) else []
    embedded_away = raw_away.get('players', []) if isinstance(raw_away, dict) else []

    if not home_abbr or not away_abbr:
        raise HTTPException(status_code=400, detail="home_team and away_team required")

    try:
        start = _time.perf_counter()

        # Use embedded players if provided, otherwise fetch from Firestore
        if embedded_home:
            home_players = embedded_home
        else:
            home_players = get_players_by_team(home_abbr, active_only=True)
        if embedded_away:
            away_players = embedded_away
        else:
            away_players = get_players_by_team(away_abbr, active_only=True)

        if not home_players or not away_players:
            raise HTTPException(status_code=404, detail="Team(s) not found")

        def build_stats(players):
            """Build player stat arrays for simulation."""
            result = []
            for p in players[:10]:  # Top 10 per team
                pid = str(p.get('player_id', p.get('id', '')))
                ps = get_player_stats(pid)
                ppg = ps.get('points_avg', 0) if ps else 0
                rpg = ps.get('rebounds_avg', 0) if ps else 0
                apg = ps.get('assists_avg', 0) if ps else 0
                fg = ps.get('fg_pct', 0.45) if ps else 0.45
                tp = ps.get('three_p_pct', 0.33) if ps else 0.33
                ft = ps.get('ft_pct', 0.75) if ps else 0.75
                result.append({
                    'player_id': pid,
                    'name': p.get('name', ''),
                    'ppg': ppg, 'rpg': rpg, 'apg': apg,
                    'fg_pct': fg, 'three_p_pct': tp, 'ft_pct': ft,
                })
            return result

        home_stats = build_stats(home_players)
        away_stats = build_stats(away_players)

        # Monte Carlo simulation using Vertex engine
        rng = _np.random.default_rng()

        home_scores = []
        away_scores = []
        home_player_totals = {p['player_id']: {'points': [], 'rebounds': [], 'assists': []} for p in home_stats}
        away_player_totals = {p['player_id']: {'points': [], 'rebounds': [], 'assists': []} for p in away_stats}
        clutch_count = 0
        blowout_count = 0

        for _ in range(n_sims):
            h_score = 0
            a_score = 0

            for p in home_stats:
                pts = max(0, rng.normal(p['ppg'], max(p['ppg'] * 0.3, 2)))
                reb = max(0, rng.normal(p['rpg'], max(p['rpg'] * 0.35, 1)))
                ast = max(0, rng.normal(p['apg'], max(p['apg'] * 0.35, 1)))
                h_score += pts
                home_player_totals[p['player_id']]['points'].append(pts)
                home_player_totals[p['player_id']]['rebounds'].append(reb)
                home_player_totals[p['player_id']]['assists'].append(ast)

            for p in away_stats:
                pts = max(0, rng.normal(p['ppg'], max(p['ppg'] * 0.3, 2)))
                reb = max(0, rng.normal(p['rpg'], max(p['rpg'] * 0.35, 1)))
                ast = max(0, rng.normal(p['apg'], max(p['apg'] * 0.35, 1)))
                a_score += pts
                away_player_totals[p['player_id']]['points'].append(pts)
                away_player_totals[p['player_id']]['rebounds'].append(reb)
                away_player_totals[p['player_id']]['assists'].append(ast)

            home_scores.append(h_score)
            away_scores.append(a_score)

            diff = abs(h_score - a_score)
            if diff <= 5:
                clutch_count += 1
            if diff >= 18:
                blowout_count += 1

        # Aggregate results
        def aggregate_player(totals):
            return {
                pid: {
                    'points': round(float(_np.mean(vals['points'])), 1),
                    'rebounds': round(float(_np.mean(vals['rebounds'])), 1),
                    'assists': round(float(_np.mean(vals['assists'])), 1),
                    'points_floor': round(float(_np.percentile(vals['points'], 20)), 1),
                    'points_ceiling': round(float(_np.percentile(vals['points'], 80)), 1),
                }
                for pid, vals in totals.items()
            }

        avg_home = round(float(_np.mean(home_scores)), 1)
        avg_away = round(float(_np.mean(away_scores)), 1)
        home_win_pct = round(sum(1 for h, a in zip(home_scores, away_scores) if h > a) / n_sims * 100, 1)

        execution_ms = round((_time.perf_counter() - start) * 1000, 1)

        return {
            "home_team_stats": aggregate_player(home_player_totals),
            "away_team_stats": aggregate_player(away_player_totals),
            "final_score": [avg_home, avg_away],
            "home_win_pct": home_win_pct,
            "was_clutch": clutch_count / n_sims > 0.3,
            "was_blowout": blowout_count / n_sims > 0.2,
            "key_events": [
                f"Simulated {n_sims} games",
                f"Average score: {avg_home:.0f}-{avg_away:.0f}",
                f"Home win rate: {home_win_pct}%",
                f"Clutch games (within 5pts): {clutch_count}/{n_sims}",
                f"Blowouts (18+ pts): {blowout_count}/{n_sims}",
            ],
            "execution_time_ms": execution_ms,
            "n_simulations": n_sims,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Crucible simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== LIVE STATS ENDPOINTS (SSE) ==================

@router.get("/live/stream")
async def live_stats_stream(request: Request):
    """
    SSE endpoint for real-time live game stats.
    Primary: reads from LivePulseCache (VPC hot path).
    Fallback: polls Firestore every 10s when VPC cache unavailable.

    Data schema: {games, leaders, changes, meta}
    """
    from sse_starlette.sse import EventSourceResponse
    from fastapi import Request
    import asyncio
    import json

    def _read_firestore_snapshot() -> dict:
        """Read live snapshot from Firestore (fallback path)."""
        try:
            from services.firebase_admin_service import get_firebase_service
            fb = get_firebase_service()
            if not fb or not fb.db:
                return {"games": [], "leaders": [], "changes": {},
                        "meta": {"game_count": 0, "live_count": 0, "source": "firestore_unavailable"}}

            # Read live_games collection
            game_docs = fb.db.collection('live_games').stream()
            games = [d.to_dict() for d in game_docs]
            # Strip SERVER_TIMESTAMP sentinel objects (not JSON-serialisable)
            for g in games:
                g.pop('updated_at', None)

            # Read live_leaders collection (sorted by rank)
            leader_docs = fb.db.collection('live_leaders').order_by('rank').limit(15).stream()
            leaders = [d.to_dict() for d in leader_docs]
            for l in leaders:
                l.pop('updated_at', None)

            live_count = sum(1 for g in games if g.get('status') == 'LIVE')
            return {
                "games": games,
                "leaders": leaders,
                "changes": {},
                "meta": {
                    "game_count": len(games),
                    "live_count": live_count,
                    "source": "firestore",
                    "timestamp": datetime.now().isoformat()
                }
            }
        except Exception as e:
            logger.warning(f"[SSE] Firestore fallback read failed: {e}")
            return {"games": [], "leaders": [], "changes": {},
                    "meta": {"game_count": 0, "live_count": 0, "source": "error"}}

    async def event_generator():
        logger.info("[SSE] Client connected to /live/stream")
        last_update_cycle = -1
        last_firestore_hash = ""

        try:
            while True:
                if await request.is_disconnected():
                    logger.info("[SSE] Client disconnected")
                    break

                # ── Primary: VPC hot cache ─────────────────────────────────
                if HAS_PULSE_CACHE and pulse_cache:
                    data = pulse_cache.get_latest()
                    current_cycle = data.get('meta', {}).get('update_cycle', 0)
                    if current_cycle != last_update_cycle:
                        last_update_cycle = current_cycle
                        yield {"event": "pulse", "data": json.dumps(data)}

                # ── Fallback: Firestore read every ~10s ────────────────────
                else:
                    snapshot = await asyncio.get_event_loop().run_in_executor(
                        None, _read_firestore_snapshot
                    )
                    # Only push when data actually changed
                    key = f"{snapshot['meta'].get('game_count')}{snapshot['meta'].get('live_count')}{len(snapshot.get('leaders',[]))}"
                    if key != last_firestore_hash:
                        last_firestore_hash = key
                        # Normalise to pulse envelope so frontend hook doesn't need changes
                        yield {"event": "pulse", "data": json.dumps(snapshot)}

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("[SSE] Live stream cancelled")
        except Exception as e:
            logger.error(f"[SSE] Stream error: {e}")

    return EventSourceResponse(event_generator())


@router.get("/live/leaders")
async def get_live_leaders_endpoint(limit: int = Query(10)):
    """
    Get top live players by PIE.
    Primary: LivePulseCache. Fallback: Firestore live_leaders collection.
    """
    # Primary: VPC hot cache
    if HAS_PULSE_CACHE and pulse_cache:
        return {
            "leaders": pulse_cache.get_leaders(limit=limit),
            "count": limit,
            "timestamp": datetime.now().isoformat(),
            "source": "vpc_hot_cache"
        }

    # Fallback: read from Firestore (written by AsyncPulseProducer)
    try:
        from services.firebase_admin_service import get_firebase_service
        fb = get_firebase_service()
        if fb and fb.db:
            docs = fb.db.collection('live_leaders').order_by('rank').limit(limit).stream()
            leaders = [d.to_dict() for d in docs]
            for l in leaders:
                l.pop('updated_at', None)
            return {
                "leaders": leaders,
                "count": len(leaders),
                "timestamp": datetime.now().isoformat(),
                "source": "firestore"
            }
    except Exception as e:
        logger.warning(f"Firestore leaders fallback failed: {e}")

    return {"leaders": [], "count": 0, "source": "unavailable",
            "timestamp": datetime.now().isoformat()}


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
    REST snapshot of live game data.
    Primary: LivePulseCache (VPC). Fallback: Firestore live_games collection.
    """
    # Primary: VPC hot cache
    if HAS_PULSE_CACHE and pulse_cache:
        return pulse_cache.get_latest()

    # Fallback: read from Firestore
    try:
        from services.firebase_admin_service import get_firebase_service
        fb = get_firebase_service()
        if fb and fb.db:
            docs = fb.db.collection('live_games').stream()
            games = [d.to_dict() for d in docs]
            for g in games:
                g.pop('updated_at', None)
            live_count = sum(1 for g in games if g.get('status') == 'LIVE')
            return {
                "games": games,
                "meta": {
                    "game_count": len(games),
                    "live_count": live_count,
                    "source": "firestore",
                    "update_cycle": 0
                }
            }
    except Exception as e:
        logger.warning(f"Firestore games fallback failed: {e}")

    return {"games": [], "meta": {"game_count": 0, "live_count": 0, "source": "unavailable"}}


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
# NOTE: /live/games is defined above (L702) using pulse cache (hot data).
# The duplicate Firestore-direct query was removed to prevent route shadowing.
# If Firestore-direct live games query is needed, use a different path (e.g., /live/games/firestore).


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

