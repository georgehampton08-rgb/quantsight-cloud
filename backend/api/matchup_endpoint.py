"""
Matchup Analysis Endpoint - Firestore Version
"""
from fastapi import APIRouter, HTTPException
import logging

from firestore_db import (
    get_team_by_tricode,
    get_players_by_team
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/matchup/analyze")
async def analyze_matchup(home_team: str, away_team: str):
    """
    Basic team matchup analysis (cloud-optimized version without Vertex Engine)
    Analyzes team stats and provides win probability
    """
    try:
        # Get both teams from Firestore
        home = get_team_by_tricode(home_team)
        away = get_team_by_tricode(away_team)
        
        if not home:
            raise HTTPException(status_code=404, detail=f"Home team {home_team} not found")
        if not away:
            raise HTTPException(status_code=404, detail=f"Away team {away_team} not found")
        
        # Get rosters
        home_roster = get_players_by_team(home_team, active_only=True)
        away_roster = get_players_by_team(away_team, active_only=True)
        
        # Simple win probability (50-50 baseline for cloud version)
        # In desktop version with Vertex Engine, this uses advanced ML models
        return {
            "matchup": {
                "home_team": {
                    "name": home.get("full_name"),
                    "abbreviation": home.get("abbreviation", home_team),
                    "roster_size": len(home_roster)
                },
                "away_team": {
                    "name": away.get("full_name"),
                    "abbreviation": away.get("abbreviation", away_team),
                    "roster_size": len(away_roster)
                }
            },
            "prediction": {
                "home_win_probability": 0.50,
                "away_win_probability": 0.50,
                "confidence": "low",
                "note": "Basic analysis - Desktop version has advanced ML predictions via Vertex Engine"
            },
            "key_factors": [
                "Home court advantage typically +3-4% win rate",
                f"Home roster: {len(home_roster)} active players",
                f"Away roster: {len(away_roster)} active players",
                "For advanced predictions, use desktop version with Vertex Engine"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing matchup {home_team} vs {away_team}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
