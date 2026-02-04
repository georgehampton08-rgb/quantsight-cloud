"""
Database API Bridge for Aegis Router
Connects Aegis data router to SQLite database queries
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import os
from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)


class DatabaseAPIBridge:
    """
    API Bridge that fetches data from SQLite database.
    Used by AegisBrain as the data source for cache misses.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        logger.info(f"DatabaseAPIBridge initialized with {db_path}")
    
    def _get_connection(self):
        """Get database connection with dict factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = self._dict_factory
        return conn
    
    @staticmethod
    def _dict_factory(cursor, row):
        """Convert sqlite3 rows to dictionaries"""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
    
    async def fetch(self, entity_type: str, entity_id: int, query: dict = None) -> dict:
        """
        Fetch data from database based on entity type.
        
        Args:
            entity_type: Type of entity ('player_stats', 'player_profile', 'team_stats', etc.)
            entity_id: Entity identifier
            query: Additional query parameters
            
        Returns:
            Data dictionary with 'last_sync' timestamp
        """
        query = query or {}
        
        handlers = {
            'player_profile': self._fetch_player_profile,
            'player_stats': self._fetch_player_stats,
            'player_career': self._fetch_player_career,
            'team_stats': self._fetch_team_stats,
            'team_roster': self._fetch_team_roster,
            'schedule': self._fetch_schedule,
        }
        
        handler = handlers.get(entity_type)
        if not handler:
            logger.warning(f"Unknown entity type: {entity_type}")
            return {'data': None, 'last_sync': None}
        
        try:
            data = handler(entity_id, query)
            from datetime import datetime
            return {
                'data': data,
                'last_sync': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Database fetch error: {e}")
            raise
    
    def _fetch_player_profile(self, player_id: int, query: dict) -> Optional[dict]:
        """Fetch complete player profile"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get player basic info
        cursor.execute("""
            SELECT player_id, name, position, team_id, jersey_number, 
                   status, height, weight, college, draft_year, draft_round, draft_number
            FROM players
            WHERE player_id = ?
        """, (str(player_id),))
        player = cursor.fetchone()
        
        if not player:
            conn.close()
            return None
        
        # Add avatar URL
        import urllib.parse
        name_encoded = urllib.parse.quote(player['name'])
        player['avatar'] = f"https://ui-avatars.com/api/?name={name_encoded}&background=1e293b&color=10b981&size=256&bold=true"
        
        # Get current season stats
        season = query.get('season', CURRENT_SEASON)
        cursor.execute("""
            SELECT * FROM player_stats
            WHERE player_id = ? AND season = ?
        """, (str(player_id), season))
        current_stats = cursor.fetchone()
        
        # Get analytics if available
        cursor.execute("""
            SELECT * FROM player_analytics
            WHERE player_id = ? AND season = ?
        """, (str(player_id), season))
        analytics = cursor.fetchone()
        
        # Get team info if team_id exists
        team = None
        if player.get('team_id'):
            cursor.execute("""
                SELECT team_id, full_name, abbreviation, city, conference, division
                FROM teams WHERE team_id = ?
            """, (player['team_id'],))
            team = cursor.fetchone()
        
        conn.close()
        
        return {
            'player': player,
            'current_stats': current_stats,
            'analytics': analytics,
            'team': team
        }
    
    def _fetch_player_stats(self, player_id: int, query: dict) -> Optional[dict]:
        """Fetch player stats for specific season"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        season = query.get('season', CURRENT_SEASON)
        cursor.execute("""
            SELECT * FROM player_stats
            WHERE player_id = ? AND season = ?
        """, (str(player_id), season))
        stats = cursor.fetchone()
        conn.close()
        
        return stats
    
    def _fetch_player_career(self, player_id: int, query: dict) -> Optional[dict]:
        """Fetch player career data with all seasons"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT season, games, points_avg, rebounds_avg, assists_avg,
                   fg_pct, three_p_pct, ft_pct
            FROM player_stats
            WHERE player_id = ?
            ORDER BY season DESC
        """, (str(player_id),))
        seasons = cursor.fetchall()
        conn.close()
        
        if not seasons:
            return None
        
        return {
            'player_id': str(player_id),
            'seasons': seasons
        }
    
    def _fetch_team_stats(self, team_id: int, query: dict) -> Optional[dict]:
        """Fetch team statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM teams WHERE team_id = ?
        """, (str(team_id),))
        team = cursor.fetchone()
        conn.close()
        
        return team
    
    def _fetch_team_roster(self, team_id: int, query: dict) -> Optional[dict]:
        """Fetch team roster"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT player_id, name, position, jersey_number, status
            FROM players
            WHERE team_id = ?
            ORDER BY jersey_number
        """, (str(team_id),))
        players = cursor.fetchall()
        conn.close()
        
        return {
            'team_id': str(team_id),
            'players': players
        }
    
    def _fetch_schedule(self, team_id: int, query: dict) -> Optional[dict]:
        """Fetch team schedule"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT game_id, game_date, game_time, home_team, away_team,
                   home_score, away_score, status, arena
            FROM schedule
            WHERE home_team_id = ? OR away_team_id = ?
            ORDER BY game_date DESC
            LIMIT 20
        """, (str(team_id), str(team_id)))
        games = cursor.fetchall()
        conn.close()
        
        return {
            'team_id': str(team_id),
            'games': games
        }
