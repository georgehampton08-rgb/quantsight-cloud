"""
PaceEngine v3 - PURE DYNAMIC DATA
NO hardcoded fallbacks - returns unavailable status if no real data.
All data comes from team_defense table pace column.
"""
import sqlite3
from typing import Dict, Optional
import sys
from pathlib import Path

# Add parent to path for centralized imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from data_paths import get_db_connection
    _USE_CENTRALIZED = True
except ImportError:
    _USE_CENTRALIZED = False
    _SCRIPT_DIR = Path(__file__).parent.parent
    _DB_PATH = _SCRIPT_DIR / 'data' / 'nba_data.db'


# League average pace (only for multiplier calculation, not as fallback)
LEAGUE_AVG_PACE = 99.5


class PaceEngine:
    """
    Calculates pace adjustment factors for matchup projections.
    PURE DYNAMIC - Only uses real pace data from team_defense table.
    Returns neutral multiplier (1.0) if no data available.
    """
    
    _cache: Dict[str, Dict] = {}
    
    @staticmethod
    def _get_db_connection():
        """Get database connection if available - uses centralized paths"""
        try:
            if _USE_CENTRALIZED:
                return get_db_connection()
            else:
                if _DB_PATH.exists():
                    return sqlite3.connect(str(_DB_PATH))
        except Exception:
            pass
        return None
    
    @staticmethod
    def _get_real_pace(team_code: str) -> Optional[Dict]:
        """Get REAL pace from database - NO FALLBACKS"""
        team_code = team_code.upper()
        
        # Check cache first
        if team_code in PaceEngine._cache:
            return PaceEngine._cache[team_code]
        
        try:
            conn = PaceEngine._get_db_connection()
            if not conn:
                return None
            
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT pace FROM team_defense WHERE team_abbr = ?
            """, (team_code,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row['pace'] and row['pace'] > 0:
                result = {
                    'pace': float(row['pace']),
                    'available': True,
                    'source': 'real_data'
                }
                PaceEngine._cache[team_code] = result
                return result
            return None
        except Exception:
            return None
    
    @staticmethod
    def get_team_pace(team_code: str) -> Optional[float]:
        """
        Get pace for a team.
        Returns None if no real data available.
        """
        data = PaceEngine._get_real_pace(team_code)
        if data and data.get('available'):
            return data['pace']
        return None
    
    @staticmethod
    def calculate_multiplier(team1: str, team2: str) -> float:
        """
        Calculate pace adjustment multiplier for a matchup.
        Returns 1.0 (neutral) if either team's pace is unavailable.
        """
        pace1 = PaceEngine.get_team_pace(team1)
        pace2 = PaceEngine.get_team_pace(team2)
        
        # If either team has no data, return neutral multiplier
        if pace1 is None or pace2 is None:
            return 1.0
        
        projected_pace = (pace1 + pace2) / 2
        multiplier = projected_pace / LEAGUE_AVG_PACE
        
        # Safety Valve: Cap at +/- 12%
        if multiplier > 1.12: 
            multiplier = 1.12
        if multiplier < 0.88: 
            multiplier = 0.88
        
        return round(multiplier, 3)
    
    @staticmethod
    def get_matchup_pace_info(team1: str, team2: str) -> Dict:
        """
        Get detailed pace information for a matchup.
        Returns availability status for each team.
        """
        pace1 = PaceEngine.get_team_pace(team1)
        pace2 = PaceEngine.get_team_pace(team2)
        
        # Build response with availability info
        result = {
            "team1": team1.upper(),
            "team1_pace": pace1,
            "team1_available": pace1 is not None,
            "team2": team2.upper(),
            "team2_pace": pace2,
            "team2_available": pace2 is not None,
        }
        
        if pace1 is not None and pace2 is not None:
            projected = (pace1 + pace2) / 2
            multiplier = PaceEngine.calculate_multiplier(team1, team2)
            
            # Determine pace category
            if projected > 101:
                category = "Fast"
            elif projected < 98:
                category = "Slow"
            else:
                category = "Average"
            
            result.update({
                "projected_pace": round(projected, 1),
                "multiplier": multiplier,
                "category": category,
                "impact_percent": round((multiplier - 1) * 100, 1),
                "source": "real_data",
                "available": True
            })
        else:
            result.update({
                "projected_pace": None,
                "multiplier": 1.0,  # Neutral
                "category": "Unknown",
                "impact_percent": 0.0,
                "source": "unavailable",
                "available": False,
                "message": "Pace data not available for one or both teams"
            })
        
        return result
    
    @staticmethod
    def is_data_available(team_code: str) -> bool:
        """Check if real pace data exists for this team"""
        return PaceEngine.get_team_pace(team_code) is not None
    
    @staticmethod
    def get_all_teams_with_pace() -> list:
        """Get list of all teams with real pace data"""
        try:
            conn = PaceEngine._get_db_connection()
            if not conn:
                return []
            
            cursor = conn.cursor()
            cursor.execute("SELECT team_abbr, pace FROM team_defense WHERE pace > 0")
            teams = [(row[0], row[1]) for row in cursor.fetchall()]
            conn.close()
            return teams
        except Exception:
            return []
    
    @staticmethod
    def clear_cache():
        """Clear the cache"""
        PaceEngine._cache = {}
