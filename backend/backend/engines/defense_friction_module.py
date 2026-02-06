"""
Defense Friction Module for Crucible v4.0
==========================================
Applies INDIVIDUAL DEFENDER DFG% to shot success probability.
Uses real tracking data instead of flat modifiers.

Integration with Crucible:
- Replace flat shooting modifiers with player-specific DFG%  
- Apply PCT_PLUSMINUS to exact shot probability
- Temporal pacing based on shot clock distribution
"""
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DefenderProfile:
    """Individual defender's impact profile"""
    player_id: str
    player_name: str
    d_fg_pct: float           # Opponent's FG% when defended by this player
    pct_plusminus: float      # Impact vs league average (e.g., -0.057 = -5.7%)
    contested_shots: float    # Contested shots per game
    deflections: float
    
    @property
    def friction_multiplier(self) -> float:
        """Convert DFG% impact to friction multiplier"""
        # If defender is -5.7% vs average, shooter success = 1 + (-0.057) = 0.943
        return 1.0 + self.pct_plusminus


@dataclass
class TeamPaceProfile:
    """Team's tempo characteristics from shot clock data"""
    team_abbr: str
    pace: float
    early_clock_freq: float   # 22-18s (transition)
    mid_clock_freq: float     # 18-7s (normal)
    late_clock_freq: float    # 7-0s (ISO/late)
    very_late_freq: float     # 0-4s (desperation)
    
    @property
    def avg_possession_length(self) -> float:
        """Calculate average possession length based on shot clock distribution"""
        # Weighted by frequency
        early_time = 5.0    # avg 5s into possession
        mid_time = 12.5     # avg 12.5s
        late_time = 17.0    # avg 17s
        very_late_time = 20.0  # avg 20s
        
        weighted = (
            self.early_clock_freq * early_time +
            self.mid_clock_freq * mid_time +
            self.late_clock_freq * late_time +
            self.very_late_freq * very_late_time
        )
        
        return weighted if weighted > 0 else 14.0  # Default 14s
    
    @property 
    def is_late_clock_heavy(self) -> bool:
        """Team has >15% very late clock shots (ISO-heavy)"""
        return self.very_late_freq > 0.15


class DefenseFrictionModule:
    """
    Provides individual defender DFG% friction for Crucible simulations.
    
    Key Features:
    1. Real DFG% from tracking data (not flat modifiers)
    2. PCT_PLUSMINUS applied to shot success probability
    3. Temporal pacing from shot clock distribution
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._defender_cache: Dict[str, DefenderProfile] = {}
        self._pace_cache: Dict[str, TeamPaceProfile] = {}
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_defender_profile(self, defender_id: str) -> Optional[DefenderProfile]:
        """Get defender's DFG% impact profile from tracking data"""
        if defender_id in self._defender_cache:
            return self._defender_cache[defender_id]
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT player_id, player_name, d_fg_pct, pct_plusminus
                FROM player_defense_tracking
                WHERE player_id = ?
            """, (str(defender_id),))
            
            row = cursor.fetchone()
            
            # Also get hustle data
            hustle = None
            cursor.execute("""
                SELECT contested_shots, deflections
                FROM player_hustle
                WHERE player_id = ?
            """, (str(defender_id),))
            hustle_row = cursor.fetchone()
            
            conn.close()
            
            if row:
                profile = DefenderProfile(
                    player_id=str(defender_id),
                    player_name=row['player_name'] or 'Unknown',
                    d_fg_pct=float(row['d_fg_pct'] or 0.45),
                    pct_plusminus=float(row['pct_plusminus'] or 0),
                    contested_shots=float(hustle_row['contested_shots'] or 0) if hustle_row else 0,
                    deflections=float(hustle_row['deflections'] or 0) if hustle_row else 0,
                )
                self._defender_cache[defender_id] = profile
                return profile
        except Exception as e:
            logger.warning(f"Error fetching defender profile: {e}")
        
        return None
    
    def get_team_pace_profile(self, team_abbr: str) -> Optional[TeamPaceProfile]:
        """Get team's shot clock distribution for temporal pacing"""
        team_abbr = team_abbr.upper()
        
        if team_abbr in self._pace_cache:
            return self._pace_cache[team_abbr]
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get base pace
            cursor.execute("""
                SELECT pace FROM team_defense WHERE team_abbr = ?
            """, (team_abbr,))
            pace_row = cursor.fetchone()
            pace = float(pace_row['pace']) if pace_row else 100.0
            
            # Get shot clock distribution (from player averages for that team)
            # This is aggregated from player_shot_clock data
            cursor.execute("""
                SELECT clock_range, AVG(fga_freq) as avg_freq
                FROM player_shot_clock
                WHERE team = ?
                GROUP BY clock_range
            """, (team_abbr,))
            
            clock_data = {row['clock_range']: float(row['avg_freq'] or 0) for row in cursor.fetchall()}
            conn.close()
            
            profile = TeamPaceProfile(
                team_abbr=team_abbr,
                pace=pace,
                early_clock_freq=clock_data.get('22-18 Seconds', 0) + clock_data.get('18-15 Seconds', 0),
                mid_clock_freq=clock_data.get('15-7 Seconds', 0),
                late_clock_freq=clock_data.get('7-4 Seconds', 0),
                very_late_freq=clock_data.get('4-0 Very Late', 0) + clock_data.get('0-4 Seconds', 0),
            )
            
            self._pace_cache[team_abbr] = profile
            return profile
            
        except Exception as e:
            logger.warning(f"Error fetching pace profile: {e}")
        
        return None
    
    def apply_defender_friction(
        self,
        base_fg_pct: float,
        defender_id: str,
        shot_type: str = '2PT'
    ) -> Tuple[float, str]:
        """
        Apply INDIVIDUAL DFG% friction to a shot.
        
        Args:
            base_fg_pct: Shooter's base FG%
            defender_id: Primary defender's player ID
            shot_type: '2PT' or '3PT'
            
        Returns:
            (adjusted_fg_pct, reason_string)
        """
        profile = self.get_defender_profile(defender_id)
        
        if not profile:
            return base_fg_pct, "No defender data"
        
        # Apply PCT_PLUSMINUS directly to shooting percentage
        # If defender is -5.7% vs average, subtract that from shooter's FG%
        adjusted = base_fg_pct * profile.friction_multiplier
        
        # Clamp to reasonable range
        adjusted = max(0.15, min(0.75, adjusted))
        
        reason = f"{profile.player_name}: DFG% +{profile.pct_plusminus*100:+.1f}% vs avg"
        
        return adjusted, reason
    
    def get_possession_length(self, off_team: str, def_team: str) -> float:
        """
        Calculate possession length based on both teams' tempo profiles.
        
        Late Clock heavy teams (>15% 0-4s shots) → 18.5s possessions
        Fast pace teams → 12s possessions
        """
        off_profile = self.get_team_pace_profile(off_team)
        def_profile = self.get_team_pace_profile(def_team)
        
        # Default possession length
        base_length = 14.0
        
        if off_profile:
            base_length = off_profile.avg_possession_length
            
            # If ISO-heavy, use longer possessions
            if off_profile.is_late_clock_heavy:
                base_length = max(base_length, 18.5)
        
        if def_profile:
            # Slower defensive teams extend possessions
            if def_profile.pace < 97:
                base_length += 1.5
            elif def_profile.pace > 102:
                base_length -= 1.0
        
        return max(10.0, min(22.0, base_length))
    
    def get_primary_defender(
        self,
        offensive_players: List[Dict],
        defensive_players: List[Dict],
        ball_handler_id: str
    ) -> Optional[DefenderProfile]:
        """
        Determine primary defender for the ball handler.
        
        Uses position matching and defensive ratings to select best matchup.
        """
        # For now, simple position-based matching
        # Could be enhanced with actual matchup data
        
        for def_player in defensive_players[:5]:  # Starters only
            profile = self.get_defender_profile(def_player.get('player_id'))
            if profile:
                return profile
        
        return None
    
    def get_all_defenders_friction(self, team_id: str) -> List[DefenderProfile]:
        """Get all defenders' friction profiles for a team"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT pdt.player_id, pdt.player_name, pdt.d_fg_pct, pdt.pct_plusminus,
                       ph.contested_shots, ph.deflections
                FROM player_defense_tracking pdt
                LEFT JOIN player_hustle ph ON pdt.player_id = ph.player_id
                WHERE pdt.team = ?
                ORDER BY pdt.pct_plusminus ASC
            """, (team_id,))
            
            profiles = []
            for row in cursor.fetchall():
                profile = DefenderProfile(
                    player_id=str(row['player_id']),
                    player_name=row['player_name'] or 'Unknown',
                    d_fg_pct=float(row['d_fg_pct'] or 0.45),
                    pct_plusminus=float(row['pct_plusminus'] or 0),
                    contested_shots=float(row['contested_shots'] or 0),
                    deflections=float(row['deflections'] or 0),
                )
                profiles.append(profile)
            
            conn.close()
            return profiles
            
        except Exception as e:
            logger.warning(f"Error fetching team defenders: {e}")
            return []


# Singleton
_module = None

def get_defense_friction_module() -> DefenseFrictionModule:
    global _module
    if _module is None:
        _module = DefenseFrictionModule()
    return _module


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    module = get_defense_friction_module()
    
    print("="*60)
    print("DEFENSE FRICTION MODULE TEST")
    print("="*60)
    
    # Test defender profile
    print("\n1. Testing Kevin Durant's DFG% profile:")
    profile = module.get_defender_profile("201142")
    if profile:
        print(f"   {profile.player_name}")
        print(f"   DFG%: {profile.d_fg_pct*100:.1f}%")
        print(f"   PCT_PLUSMINUS: {profile.pct_plusminus*100:+.1f}%")
        print(f"   Friction Multiplier: {profile.friction_multiplier:.3f}")
    
    # Test friction application
    print("\n2. Testing friction on a 45% shooter vs KD:")
    adj_pct, reason = module.apply_defender_friction(0.45, "201142")
    print(f"   Base: 45.0% → Adjusted: {adj_pct*100:.1f}%")
    print(f"   Reason: {reason}")
    
    # Test pace profile
    print("\n3. Testing GSW pace profile:")
    pace = module.get_team_pace_profile("GSW")
    if pace:
        print(f"   Pace: {pace.pace}")
        print(f"   Avg possession: {pace.avg_possession_length:.1f}s")
        print(f"   ISO-heavy: {pace.is_late_clock_heavy}")
