"""
Advanced Team Metrics Service
=============================
Provides advanced metrics for matchup analysis:
- Shot Profile Frequency (corner 3s, mid-range, paint)
- Transition Efficiency (PPP in transition)
- Secondary Assist Rate (hockey assists)

These metrics inform the Crucible engine about friction points and pace dynamics.
"""
import sqlite3
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AdvancedTeamMetrics:
    """
    Advanced team metrics calculator.
    Fetches from team_advanced_stats table or calculates from play-by-play data.
    """
    
    # League averages for normalization
    LEAGUE_AVG = {
        'corner_3_freq': 0.085,      # ~8.5% of shots from corners
        'mid_range_freq': 0.145,      # ~14.5% mid-range
        'paint_freq': 0.42,           # ~42% in the paint
        'transition_ppp': 1.12,       # Points per possession in transition
        'halfcourt_ppp': 0.96,        # Points per possession in halfcourt
        'secondary_ast_rate': 0.52,   # % of made shots that have a hockey assist
        'turnover_rate': 0.128,       # Turnovers per 100 possessions
        'pace': 99.5,
    }
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = db_path
    
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_shot_profile(self, team_abbr: str) -> Dict:
        """
        Get team shot profile frequencies.
        Returns breakdown of where team takes shots from.
        
        Shot zones:
        - corner_3: Left/Right corner 3s
        - above_break_3: Above the break 3s
        - mid_range: Mid-range jumpers
        - paint: Shots in the paint (non-restricted area)
        - restricted_area: Shots at the rim
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Try to get from team_shot_zones table
            cursor.execute("""
                SELECT 
                    corner_3_freq, corner_3_pct,
                    above_break_3_freq, above_break_3_pct,
                    mid_range_freq, mid_range_pct,
                    paint_freq, paint_pct,
                    restricted_area_freq, restricted_area_pct
                FROM team_shot_zones
                WHERE team_abbr = ?
            """, (team_abbr.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'corner_3': {'freq': row['corner_3_freq'], 'pct': row['corner_3_pct']},
                    'above_break_3': {'freq': row['above_break_3_freq'], 'pct': row['above_break_3_pct']},
                    'mid_range': {'freq': row['mid_range_freq'], 'pct': row['mid_range_pct']},
                    'paint': {'freq': row['paint_freq'], 'pct': row['paint_pct']},
                    'restricted_area': {'freq': row['restricted_area_freq'], 'pct': row['restricted_area_pct']},
                    'source': 'database',
                }
        except Exception as e:
            logger.warning(f"Could not fetch shot profile for {team_abbr}: {e}")
        
        # Return league averages if no data
        return {
            'corner_3': {'freq': self.LEAGUE_AVG['corner_3_freq'], 'pct': 0.38},
            'above_break_3': {'freq': 0.28, 'pct': 0.36},
            'mid_range': {'freq': self.LEAGUE_AVG['mid_range_freq'], 'pct': 0.42},
            'paint': {'freq': self.LEAGUE_AVG['paint_freq'], 'pct': 0.55},
            'restricted_area': {'freq': 0.30, 'pct': 0.65},
            'source': 'league_average',
        }
    
    def get_transition_metrics(self, team_abbr: str) -> Dict:
        """
        Get team transition offense/defense metrics.
        Returns PPP in transition and frequency of transition possessions.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    transition_freq, transition_ppp,
                    halfcourt_ppp, fastbreak_pts_per_game
                FROM team_transition_stats
                WHERE team_abbr = ?
            """, (team_abbr.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'transition_freq': row['transition_freq'],
                    'transition_ppp': row['transition_ppp'],
                    'halfcourt_ppp': row['halfcourt_ppp'],
                    'fastbreak_pts_game': row['fastbreak_pts_per_game'],
                    'transition_advantage': (row['transition_ppp'] - self.LEAGUE_AVG['transition_ppp']) / self.LEAGUE_AVG['transition_ppp'] * 100,
                    'source': 'database',
                }
        except Exception as e:
            logger.warning(f"Could not fetch transition metrics for {team_abbr}: {e}")
        
        # Return league averages
        return {
            'transition_freq': 0.15,  # ~15% of possessions
            'transition_ppp': self.LEAGUE_AVG['transition_ppp'],
            'halfcourt_ppp': self.LEAGUE_AVG['halfcourt_ppp'],
            'fastbreak_pts_game': 14.0,
            'transition_advantage': 0.0,
            'source': 'league_average',
        }
    
    def get_secondary_assist_metrics(self, team_abbr: str) -> Dict:
        """
        Get team secondary assist (hockey assist) metrics.
        Identifies the true offensive engine even when not getting final pass.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    secondary_ast_rate, ast_to_pass_pct,
                    potential_ast_per_game, ast_adj_per_game
                FROM team_playmaking_stats
                WHERE team_abbr = ?
            """, (team_abbr.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'secondary_ast_rate': row['secondary_ast_rate'],
                    'ast_to_pass_pct': row['ast_to_pass_pct'],
                    'potential_ast_game': row['potential_ast_per_game'],
                    'ast_adj_game': row['ast_adj_per_game'],
                    'playmaking_index': (row['secondary_ast_rate'] / self.LEAGUE_AVG['secondary_ast_rate']) * 100,
                    'source': 'database',
                }
        except Exception as e:
            logger.warning(f"Could not fetch secondary assist metrics for {team_abbr}: {e}")
        
        # Return league averages
        return {
            'secondary_ast_rate': self.LEAGUE_AVG['secondary_ast_rate'],
            'ast_to_pass_pct': 0.08,
            'potential_ast_game': 35.0,
            'ast_adj_game': 28.0,
            'playmaking_index': 100.0,
            'source': 'league_average',
        }
    
    def get_turnover_metrics(self, team_abbr: str) -> Dict:
        """
        Get team turnover tendencies.
        High turnover rate + opponent with good transition = bad matchup.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT turnover_rate, turnovers_per_game
                FROM team_defense
                WHERE team_abbr = ?
            """, (team_abbr.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row and row['turnover_rate']:
                return {
                    'turnover_rate': row['turnover_rate'],
                    'turnovers_game': row['turnovers_per_game'] or 14.0,
                    'source': 'database',
                }
        except Exception as e:
            logger.warning(f"Could not fetch turnover metrics for {team_abbr}: {e}")
        
        return {
            'turnover_rate': self.LEAGUE_AVG['turnover_rate'],
            'turnovers_game': 14.0,
            'source': 'league_average',
        }
    
    def get_all_advanced_metrics(self, team_abbr: str) -> Dict:
        """Get all advanced metrics for a team"""
        return {
            'team': team_abbr.upper(),
            'shot_profile': self.get_shot_profile(team_abbr),
            'transition': self.get_transition_metrics(team_abbr),
            'secondary_assists': self.get_secondary_assist_metrics(team_abbr),
            'turnovers': self.get_turnover_metrics(team_abbr),
        }
    
    def calculate_matchup_friction(self, offense_team: str, defense_team: str) -> Dict:
        """
        Calculate matchup friction points between two teams.
        Identifies where the offense's strengths meet the defense's weaknesses.
        """
        off_profile = self.get_shot_profile(offense_team)
        off_transition = self.get_transition_metrics(offense_team)
        def_turnovers = self.get_turnover_metrics(defense_team)
        def_transition = self.get_transition_metrics(defense_team)
        
        friction_points = []
        
        # Corner 3 specialists vs poor corner defense
        if off_profile['corner_3']['freq'] > 0.10:
            friction_points.append({
                'type': 'corner_3_heavy',
                'description': f"{offense_team} takes {off_profile['corner_3']['freq']*100:.1f}% of shots from corners",
                'importance': 'high' if off_profile['corner_3']['pct'] > 0.38 else 'medium',
            })
        
        # Transition teams vs high turnover teams
        if off_transition['transition_ppp'] > 1.15 and def_turnovers['turnover_rate'] > 0.14:
            friction_points.append({
                'type': 'transition_opportunity',
                'description': f"{offense_team} excels in transition ({off_transition['transition_ppp']:.2f} PPP) vs {defense_team} turnover rate ({def_turnovers['turnover_rate']*100:.1f}%)",
                'importance': 'high',
            })
        
        # Pace advantage
        if off_transition['transition_advantage'] > 5:
            friction_points.append({
                'type': 'pace_advantage',
                'description': f"{offense_team} has +{off_transition['transition_advantage']:.1f}% transition efficiency vs league average",
                'importance': 'medium',
            })
        
        return {
            'offense': offense_team,
            'defense': defense_team,
            'friction_points': friction_points,
            'transition_opportunity_score': min(100, max(0, 
                (off_transition['transition_ppp'] / self.LEAGUE_AVG['transition_ppp'] * 50) +
                (def_turnovers['turnover_rate'] / self.LEAGUE_AVG['turnover_rate'] * 50)
            )),
        }


# Singleton instance
_advanced_metrics = None

def get_advanced_metrics() -> AdvancedTeamMetrics:
    """Get or create singleton instance"""
    global _advanced_metrics
    if _advanced_metrics is None:
        _advanced_metrics = AdvancedTeamMetrics()
    return _advanced_metrics


# Quick test
if __name__ == '__main__':
    metrics = AdvancedTeamMetrics()
    
    print("=" * 60)
    print("ADVANCED TEAM METRICS TEST")
    print("=" * 60)
    
    for team in ['MEM', 'NOP', 'BOS', 'LAL']:
        print(f"\n{team}:")
        all_metrics = metrics.get_all_advanced_metrics(team)
        print(f"  Shot Profile Source: {all_metrics['shot_profile']['source']}")
        print(f"  Transition PPP: {all_metrics['transition']['transition_ppp']}")
        print(f"  Secondary Ast Rate: {all_metrics['secondary_assists']['secondary_ast_rate']}")
    
    print("\n" + "=" * 60)
    print("MATCHUP FRICTION: MEM vs NOP")
    print("=" * 60)
    friction = metrics.calculate_matchup_friction('MEM', 'NOP')
    for fp in friction['friction_points']:
        print(f"  [{fp['importance'].upper()}] {fp['type']}: {fp['description']}")
    print(f"  Transition Opportunity Score: {friction['transition_opportunity_score']:.1f}")
