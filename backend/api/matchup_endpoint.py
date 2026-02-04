@router.get("/matchup/analyze")
async def analyze_matchup(home_team: str, away_team: str):
    """
    Basic team matchup analysis (cloud-optimized version without Vertex Engine)
    Analyzes team stats and provides win probability
    """
    db_url = get_database_url()
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # Fetch team stats for both teams
            home_stats = conn.execute(text("""
                SELECT t.full_name, t.tricode, COUNT(DISTINCT p.player_id) as roster_size
                FROM teams t
                LEFT JOIN players p ON t.tricode = p.team_abbreviation
                WHERE UPPER(t.tricode) = UPPER(:team)
                GROUP BY t.full_name, t.tricode
            """), {"team": home_team}).fetchone()
            
            away_stats = conn.execute(text("""
                SELECT t.full_name, t.tricode, COUNT(DISTINCT p.player_id) as roster_size  
                FROM teams t
                LEFT JOIN players p ON t.tricode = p.team_abbreviation
                WHERE UPPER(t.tricode) = UPPER(:team)
                GROUP BY t.full_name, t.tricode
            """), {"team": away_team}).fetchone()
            
            if not home_stats or not away_stats:
                raise HTTPException(status_code=404, detail="One or both teams not found")
        
        engine.dispose()
        
        # Simple win probability (50-50 baseline for cloud version)
        # In desktop version with Vertex Engine, this uses advanced ML models
        return {
            "matchup": {
                "home_team": {
                    "name": home_stats[0],
                    "abbreviation": home_stats[1],
                    "roster_size": int(home_stats[2])
                },
                "away_team": {
                    "name": away_stats[0],
                    "abbreviation": away_stats[1],
                    "roster_size": int(away_stats[2])
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
                "Team rosters loaded successfully",
                "For advanced predictions, use desktop version with Vertex Engine"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing matchup {home_team} vs {away_team}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
