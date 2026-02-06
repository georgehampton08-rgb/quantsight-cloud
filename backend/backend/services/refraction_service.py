"""
RefractionService - Centralized pace-adjusted statistics calculator.

Eliminates redundant pace calculations between Player Lab and Matchup Engine.
Formula: M_adj = (Pace_league / Pace_team) × M_raw
"""

import logging
from typing import Dict, Optional
import sqlite3

from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)


class RefractionService:
    """
    Unified pace normalization service.
    
    Standardizes all pace-adjusted calculations to prevent
    discrepancies between frontend components.
    """
    
    # League average pace (current season)
    LEAGUE_AVG_PACE = 98.5
    
    def __init__(self, db_path: str):
        """
        Initialize refraction service.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def get_team_pace(self, team_id: str, season: str = CURRENT_SEASON) -> float:
        """
        Get team's average pace for season.
        
        Args:
            team_id: Team identifier
            season: Season string (e.g., "2024-25")
            
        Returns:
            Team pace (possessions per 48 minutes)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query team pace from team_stats table
            cursor.execute("""
                SELECT pace FROM team_stats 
                WHERE team_id = ? AND season = ?
            """, (team_id, season))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                return float(result[0])
            else:
                logger.warning(f"[REFRACTION] No pace data for {team_id}, using league average")
                return self.LEAGUE_AVG_PACE
                
        except Exception as e:
            logger.error(f"[REFRACTION] Error fetching team pace: {e}")
            return self.LEAGUE_AVG_PACE
    
    def adjust_stat(self, raw_value: float, team_pace: float) -> float:
        """
        Apply pace adjustment to raw stat.
        
        Formula: M_adj = (Pace_league / Pace_team) × M_raw
        
        Args:
            raw_value: Unadjusted statistic
            team_pace: Team's pace
            
        Returns:
            Pace-adjusted value
        """
        if team_pace <= 0:
            return raw_value
        
        adjustment_factor = self.LEAGUE_AVG_PACE / team_pace
        return raw_value * adjustment_factor
    
    def get_pace_adjusted_stats(
        self, 
        player_id: str, 
        team_id: Optional[str] = None,
        season: str = CURRENT_SEASON
    ) -> Dict[str, float]:
        """
        Get all pace-adjusted stats for a player.
        
        Args:
            player_id: Player identifier
            team_id: Optional team override
            season: Season string
            
        Returns:
            Dict with adjusted stats
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get player's team if not provided
            if not team_id:
                cursor.execute("""
                    SELECT team_id FROM players WHERE player_id = ?
                """, (player_id,))
                result = cursor.fetchone()
                team_id = result[0] if result else None
            
            # Get raw stats
            cursor.execute("""
                SELECT points_avg, rebounds_avg, assists_avg, 
                       steals_avg, blocks_avg, turnovers_avg
                FROM player_stats 
                WHERE player_id = ? AND season = ?
            """, (player_id, season))
            
            stats_row = cursor.fetchone()
            conn.close()
            
            if not stats_row:
                logger.warning(f"[REFRACTION] No stats found for player {player_id}")
                return {}
            
            # Get team pace
            team_pace = self.get_team_pace(team_id, season) if team_id else self.LEAGUE_AVG_PACE
            
            # Apply adjustments
            raw_stats = {
                "points_avg": stats_row[0] or 0,
                "rebounds_avg": stats_row[1] or 0,
                "assists_avg": stats_row[2] or 0,
                "steals_avg": stats_row[3] or 0,
                "blocks_avg": stats_row[4] or 0,
                "turnovers_avg": stats_row[5] or 0
            }
            
            adjusted_stats = {
                "pace_adjusted": {
                    key: round(self.adjust_stat(val, team_pace), 2)
                    for key, val in raw_stats.items()
                },
                "raw": raw_stats,
                "team_pace": team_pace,
                "league_pace": self.LEAGUE_AVG_PACE,
                "adjustment_factor": round(self.LEAGUE_AVG_PACE / team_pace, 3)
            }
            
            logger.info(f"[REFRACTION] Adjusted stats for {player_id} (team pace: {team_pace})")
            return adjusted_stats
            
        except Exception as e:
            logger.error(f"[REFRACTION] Error calculating adjusted stats: {e}")
            return {}
