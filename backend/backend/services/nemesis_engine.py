"""
NemesisEngine v3 - PURE DYNAMIC DATA
NO hardcoded fallbacks - returns unavailable status if no real data.
All data comes from player_vs_team table.
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


class NemesisEngine:
    """
    Analyzes historical player performance against specific opponents.
    PURE DYNAMIC - Only uses real data from player_vs_team table.
    Returns unavailable status if data doesn't exist.
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
    def _get_real_matchup(player_id: str, opponent_team: str) -> Optional[Dict]:
        """Get REAL matchup data from database - NO FALLBACKS"""
        try:
            conn = NemesisEngine._get_db_connection()
            if not conn:
                return None
            
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM player_vs_team 
                WHERE player_id = ? AND opponent = ?
            """, (str(player_id), opponent_team.upper()))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                avg_pts = row['avg_pts'] if 'avg_pts' in row.keys() else None
                if avg_pts and avg_pts > 0:
                    # Safe access for optional columns
                    avg_reb = row['avg_reb'] if 'avg_reb' in row.keys() else 0
                    avg_ast = row['avg_ast'] if 'avg_ast' in row.keys() else 0
                    games = row['games'] if 'games' in row.keys() else 0
                    
                    return {
                        'avg_pts': avg_pts,
                        'avg_reb': avg_reb or 0,
                        'avg_ast': avg_ast or 0,
                        'games_played': games or 0,
                        'wins': 0,
                        'source': 'real_data',
                        'available': True
                    }
            return None
        except Exception as e:
            print(f"NemesisEngine DB error: {e}")
            return None
    
    @staticmethod
    def analyze_head_to_head(player_id: str, opponent_team: str, season_avg_ppg: float) -> Dict:
        """
        Analyze player's historical performance against an opponent.
        Returns unavailable status if no real data - NEVER fake data.
        """
        # Try real data first
        real_data = NemesisEngine._get_real_matchup(player_id, opponent_team)
        
        if real_data and real_data.get('available'):
            # Use real historical data
            avg_vs_opp = real_data['avg_pts']
            games = real_data.get('games_played', 1)
            
            # Calculate delta
            if season_avg_ppg > 0:
                delta_percent = (avg_vs_opp - season_avg_ppg) / season_avg_ppg
            else:
                delta_percent = 0
            
            # Determine grade based on real data
            if delta_percent > 0.15:
                grade, status = "A+", "Nemesis Mode"
            elif delta_percent > 0.05:
                grade, status = "B", "Favorable"
            elif delta_percent < -0.15:
                grade, status = "F", "Locked Down"
            elif delta_percent < -0.05:
                grade, status = "D", "Disadvantage"
            else:
                grade, status = "C", "Neutral"
            
            return {
                "grade": grade,
                "status": status,
                "avg_vs_opponent": round(avg_vs_opp, 1),
                "delta_percent": round(delta_percent * 100, 1),
                "games_sampled": games,
                "source": "real_data",
                "available": True
            }
        
        # NO FALLBACKS - Return unavailable status
        return {
            "grade": "?",
            "status": "No History",
            "avg_vs_opponent": None,
            "delta_percent": 0.0,  # Neutral - no adjustment
            "games_sampled": 0,
            "source": "unavailable",
            "available": False,
            "message": f"No matchup history for player {player_id} vs {opponent_team}"
        }
    
    @staticmethod
    def get_all_matchups(player_id: str) -> list:
        """Get all matchup data for a player against all opponents"""
        try:
            conn = NemesisEngine._get_db_connection()
            if not conn:
                return []
            
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM player_vs_team 
                WHERE player_id = ? AND avg_pts > 0
                ORDER BY avg_pts DESC
            """, (str(player_id),))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception:
            return []
    
    @staticmethod
    def has_matchup_history(player_id: str, opponent_team: str) -> bool:
        """Check if real matchup history exists"""
        data = NemesisEngine._get_real_matchup(player_id, opponent_team)
        return data is not None and data.get('available', False)
    
    @staticmethod
    def clear_cache():
        """Clear the cache"""
        NemesisEngine._cache = {}
