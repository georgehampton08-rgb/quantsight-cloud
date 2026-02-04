"""
Multi-Stat Confluence Engine
============================
Calculates projections for multiple stats: PTS, REB, AST, 3PM
Combines season averages, H2H history, team defense, pace, and form.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import injury worker (optional - gracefully handle if not available)
try:
    from services.automated_injury_worker import get_injury_worker
    HAS_INJURY_WORKER = True
except ImportError:
    HAS_INJURY_WORKER = False
    get_injury_worker = None

# League averages for reference
LEAGUE_AVG = {
    'pace': 99.5,
    'pts': 115.0,
    'reb': 44.0,
    'ast': 26.0,
    '3pm': 13.0,
}

class MultiStatConfluence:
    """
    Multi-stat projection engine combining all data sources.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = db_path
        
        # Initialize injury worker if available
        self.injury_worker = None
        if HAS_INJURY_WORKER and get_injury_worker:
            try:
                self.injury_worker = get_injury_worker()
                logger.info("Injury worker integrated into confluence")
            except Exception as e:
                logger.warning(f"Could not initialize injury worker: {e}")
    
    def _get_connection(self):
        """Get database connection with WAL mode"""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def get_team_defense(self, team: str) -> Dict:
        """Get team defensive profile"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT def_rating, opp_pts, opp_reb, opp_ast, opp_fg3_pct, pace
                FROM team_defense WHERE team_abbr = ?
            """, (team.upper(),))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'def_rating': row['def_rating'] or 110,
                    'opp_pts': row['opp_pts'] or 115,
                    'opp_reb': row['opp_reb'] or 44,
                    'opp_ast': row['opp_ast'] or 26,
                    'opp_fg3_pct': row['opp_fg3_pct'] or 0.36,
                    'pace': row['pace'] or 99.5,
                }
        except Exception as e:
            logger.error(f"Error getting team defense: {e}")
        
        return {
            'def_rating': 110, 'opp_pts': 115, 'opp_reb': 44,
            'opp_ast': 26, 'opp_fg3_pct': 0.36, 'pace': 99.5
        }
    
    def get_player_stats(self, player_id: str) -> Optional[Dict]:
        """Get player's rolling averages for all stats including 3PM, team, position"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get rolling averages - only select columns that exist in the table
            cursor.execute("""
                SELECT player_name, avg_points, avg_rebounds, avg_assists
                FROM player_rolling_averages
                WHERE player_id = ?
            """, (str(player_id),))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return None
            
            # Get team and position from player_bio
            team = ''
            position = ''
            try:
                cursor.execute("""
                    SELECT team, position FROM player_bio WHERE player_id = ?
                """, (str(player_id),))
                bio_row = cursor.fetchone()
                if bio_row:
                    team = bio_row['team'] if 'team' in bio_row.keys() else ''
                    position = bio_row['position'] if 'position' in bio_row.keys() else ''
            except Exception:
                pass  # Table or columns don't exist
            
            # Get 3PM from game logs - column is fg3_made not fg3m
            fg3m = 0
            try:
                cursor.execute("""
                    SELECT AVG(fg3_made) as avg_fg3m 
                    FROM player_game_logs 
                    WHERE player_id = ? AND fg3_made IS NOT NULL
                    ORDER BY game_date DESC
                    LIMIT 15
                """, (str(player_id),))
                fg3_row = cursor.fetchone()
                if fg3_row and fg3_row['avg_fg3m']:
                    fg3m = fg3_row['avg_fg3m']
            except Exception:
                pass  # Table or column doesn't exist
            
            conn.close()
            
            return {
                'name': row['player_name'],
                'team': team,
                'position': position,
                'pts': row['avg_points'] or 0,
                'reb': row['avg_rebounds'] or 0,
                'ast': row['avg_assists'] or 0,
                '3pm': round(fg3m, 1),
                'trend': 'stable',  # Default - column doesn't exist in rolling_averages
                'hot': False,  # Default - column doesn't exist
                'cold': False,  # Default - column doesn't exist
            }
        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
        return None
    
    def get_h2h_history(self, player_id: str, opponent: str) -> Optional[Dict]:
        """Get player's head-to-head stats vs opponent"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get aggregate stats from player_vs_team
            cursor.execute("""
                SELECT avg_pts, avg_reb, avg_ast, games
                FROM player_vs_team
                WHERE player_id = ? AND opponent = ?
            """, (str(player_id), opponent.upper()))
            row = cursor.fetchone()
            conn.close()
            
            if row and row['games'] and row['games'] > 0:
                return {
                    'pts': row['avg_pts'] or 0,
                    'reb': row['avg_reb'] or 0,
                    'ast': row['avg_ast'] or 0,
                    '3pm': 0,  # Not tracking H2H 3PM yet
                    'games': row['games'],
                }
            
        except Exception as e:
            logger.error(f"Error getting H2H history: {e}")
        return None
    
    def calculate_form_adjustment(self, player_stats: Dict) -> Dict:
        """Calculate form-based adjustments - tuned for meaningful impact"""
        adjustments = {'pts': 0, 'reb': 0, 'ast': 0, '3pm': 0}
        
        if player_stats.get('hot'):
            # HOT streak: 12-15% boost
            adjustments = {'pts': 0.12, 'reb': 0.08, 'ast': 0.10, '3pm': 0.15}
            label = 'HOT'
        elif player_stats.get('cold'):
            # COLD streak: 10-15% reduction
            adjustments = {'pts': -0.12, 'reb': -0.06, 'ast': -0.08, '3pm': -0.18}
            label = 'COLD'
        elif player_stats.get('trend') == 'up':
            adjustments = {'pts': 0.06, 'reb': 0.04, 'ast': 0.05, '3pm': 0.08}
            label = 'RISING'
        elif player_stats.get('trend') == 'down':
            adjustments = {'pts': -0.06, 'reb': -0.04, 'ast': -0.05, '3pm': -0.10}
            label = 'COOLING'
        else:
            label = 'STEADY'
        
        return {'adjustments': adjustments, 'label': label}
    
    def calculate_defense_adjustment(self, opponent_defense: Dict, stat: str) -> float:
        """Calculate defensive impact on a specific stat - uses % of league average.
        
        Example: BOS allows 107.2 PPG (107.2-115)/115 = -6.8%
        This means players score 6.8% less against Boston.
        """
        mappings = {
            'pts': ('opp_pts', LEAGUE_AVG['pts']),
            'reb': ('opp_reb', LEAGUE_AVG['reb']),
            'ast': ('opp_ast', LEAGUE_AVG['ast']),
            '3pm': ('opp_fg3_pct', 0.36),
        }
        
        if stat not in mappings:
            return 0
        
        key, avg = mappings[stat]
        opp_value = opponent_defense.get(key, avg)
        
        # Calculate percentage difference from league average
        # Example: (107.2 - 115) / 115 = -0.068 (-6.8%)
        pct_diff = (opp_value - avg) / avg
        
        # Apply scaling factor (1.0 = full impact, 0.5 = half impact)
        if stat == '3pm':
            return pct_diff * 1.0  # Full impact for 3PM
        elif stat == 'pts':
            return pct_diff * 0.8  # 80% of the defensive differential
        elif stat == 'reb':
            return pct_diff * 0.7  # 70% for rebounds
        else:  # ast
            return pct_diff * 0.8  # 80% for assists
    
    def calculate_pace_multiplier(self, home_defense: Dict, away_defense: Dict) -> float:
        """Calculate pace impact on scoring"""
        pace1 = home_defense.get('pace', LEAGUE_AVG['pace'])
        pace2 = away_defense.get('pace', LEAGUE_AVG['pace'])
        avg_pace = (pace1 + pace2) / 2
        
        return 1 + ((avg_pace - LEAGUE_AVG['pace']) / LEAGUE_AVG['pace'])
    
    def calculate_grade(self, projected: float, baseline: float, h2h_avg: float = None) -> tuple:
        """Calculate matchup grade based on projection delta (with H2H bonus)
        
        ADJUSTED THRESHOLDS (more sensitive):
        - A: >=8% improvement (was 15%)
        - B: >=4% improvement (was 8%)
        - B-: >=1.5% improvement (was 3%)
        - C: -1.5% to +1.5% (was -3% to +3%)
        - D: <=-1.5% (was -3%)
        - D-: <=-4% (was -8%)
        - F: <=-8% (was -15%)
        """
        if not baseline or baseline == 0:
            return 'C', 'Neutral'
        
        delta_pct = (projected - baseline) / baseline * 100
        
        # H2H bonus: if H2H shows strong performance, boost grade
        if h2h_avg and baseline > 0:
            h2h_delta = (h2h_avg - baseline) / baseline * 100
            if h2h_delta > 10:
                delta_pct += 3  # Bonus for proven performer vs this opponent
        
        if delta_pct >= 8:
            return 'A', 'Smash Spot'
        elif delta_pct >= 4:
            return 'B', 'Advantage'
        elif delta_pct >= 1.5:
            return 'B-', 'Slight Edge'
        elif delta_pct >= -1.5:
            return 'C', 'Neutral'
        elif delta_pct >= -4:
            return 'D', 'Tough Matchup'
        elif delta_pct >= -8:
            return 'D-', 'Disadvantage'
        else:
            return 'F', 'Fade Spot'
    
    def calculate_classification(self, delta: float, baseline: float) -> str:
        """Calculate TARGET/FADE/NEUTRAL classification
        
        ADJUSTED THRESHOLDS (more sensitive):
        - TARGET: >=2% improvement (was 5%)
        - FADE: <=-2% decline (was -5%)
        - NEUTRAL: between -2% and +2%
        """
        if baseline == 0:
            return 'NEUTRAL'
        
        delta_pct = (delta / baseline) * 100
        
        if delta_pct >= 2:
            return 'TARGET'
        elif delta_pct <= -2:
            return 'FADE'
        else:
            return 'NEUTRAL'
    
    def project_player(self, player_id: str, opponent: str, opponent_defense: Dict, 
                       pace_mult: float) -> Optional[Dict]:
        """
        Generate multi-stat projection for a player.
        Returns projections for PTS, REB, AST, 3PM.
        """
        stats = self.get_player_stats(player_id)
        if not stats:
            return None
        
        # Check injury status
        injury_status = 'AVAILABLE'
        injury_multiplier = 1.0
        is_available = True
        
        if self.injury_worker:
            try:
                inj = self.injury_worker.get_player_status(player_id)
                injury_status = inj.get('status', 'AVAILABLE')
                injury_multiplier = inj.get('performance_multiplier', 1.0)
                is_available = injury_status not in ['OUT', 'DOUBTFUL']
            except Exception:
                pass  # Default to available
        
        h2h = self.get_h2h_history(player_id, opponent)
        form = self.calculate_form_adjustment(stats)
        
        projections = {}
        
        for stat in ['pts', 'reb', 'ast', '3pm']:
            baseline = stats.get(stat, 0)
            
            # Form adjustment
            form_adj = baseline * form['adjustments'].get(stat, 0)
            
            # H2H contribution (weighted by games played)
            if h2h and h2h.get('games', 0) >= 1:
                h2h_avg = h2h.get(stat, baseline)
                h2h_weight = min(h2h['games'] / 8, 0.35)  # Max 35% weight
                h2h_contrib = (h2h_avg - baseline) * h2h_weight
            else:
                h2h_avg = None
                h2h_contrib = 0
            
            # Defense adjustment
            def_adj = baseline * self.calculate_defense_adjustment(opponent_defense, stat)
            
            # Pace adjustment (mainly affects PTS, AST)
            if stat in ['pts', 'ast']:
                pace_adj = pace_mult
            else:
                pace_adj = 1.0 + (pace_mult - 1.0) * 0.5  # Half effect on REB, 3PM
            
            # Final projection
            raw = baseline + form_adj + h2h_contrib + def_adj
            
            # Apply injury performance multiplier (e.g., QUESTIONABLE = 85%)
            final = raw * pace_adj * injury_multiplier
            
            # Calculate delta
            delta = final - baseline
            
            # Grade (now uses projection delta, not just H2H)
            grade, grade_label = self.calculate_grade(final, baseline, h2h_avg)
            
            # Classification (TARGET/FADE/NEUTRAL)
            classification = self.calculate_classification(delta, baseline)
            
            # Confidence score
            confidence = 60
            if h2h and h2h.get('games', 0) >= 2:
                confidence += 20
            if form['label'] in ['HOT', 'COLD']:
                confidence += 10
            confidence += 10  # Defense data
            
            projections[stat] = {
                'baseline': round(baseline, 1),
                'projected': round(max(0, final), 1),
                'delta': round(delta, 1),
                'h2h_avg': round(h2h_avg, 1) if h2h_avg else None,
                'h2h_games': h2h['games'] if h2h else 0,
                'grade': grade,
                'grade_label': grade_label,
                'form': form['label'],
                'confidence': min(confidence, 100),
                'classification': classification,
            }
        
        # Determine overall player classification using weighted aggregate
        # PTS=40%, REB=20%, AST=20%, 3PM=20% 
        weights = {'pts': 0.40, 'reb': 0.20, 'ast': 0.20, '3pm': 0.20}
        total_score = 0
        best_grade = 'C'
        grade_order = ['A', 'B', 'B-', 'C', 'D', 'D-', 'F']
        
        for stat, weight in weights.items():
            if stat in projections:
                proj = projections[stat]
                baseline = proj['baseline']
                delta = proj['delta']
                if baseline > 0:
                    pct = (delta / baseline) * 100
                    total_score += pct * weight
                # Track best individual grade
                stat_grade = proj.get('grade', 'C')
                if grade_order.index(stat_grade) < grade_order.index(best_grade):
                    best_grade = stat_grade
        
        # Classify based on weighted aggregate - lower threshold for more differentiation
        if total_score >= 3:
            overall_class = 'TARGET'
        elif total_score <= -3:
            overall_class = 'FADE'
        else:
            overall_class = 'NEUTRAL'
        
        return {
            'player_id': player_id,
            'player_name': stats['name'],
            'team': stats.get('team', ''),
            'position': stats.get('position', ''),
            'opponent': opponent,
            'projections': projections,
            'form_label': form['label'],
            'classification': overall_class,
            'overall_grade': best_grade,
            'aggregate_score': round(total_score, 1),
            'injury_status': injury_status,
            'is_available': is_available,
        }
    
    def analyze_game(self, home_team: str, away_team: str) -> Dict:
        """
        Full game analysis with all player projections.
        """
        home_defense = self.get_team_defense(home_team)
        away_defense = self.get_team_defense(away_team)
        pace_mult = self.calculate_pace_multiplier(home_defense, away_defense)
        
        result = {
            'game': f"{away_team} @ {home_team}",
            'generated_at': datetime.now().isoformat(),
            'matchup_context': {
                'home_team': home_team,
                'away_team': away_team,
                'home_defense': home_defense,
                'away_defense': away_defense,
                'pace_multiplier': round(pace_mult, 3),
                'projected_pace': round((home_defense['pace'] + away_defense['pace']) / 2, 1),
            },
            'projections': [],
        }
        
        # Get players for both teams
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for team, opponent, opp_def in [(away_team, home_team, home_defense), 
                                             (home_team, away_team, away_defense)]:
                cursor.execute("""
                    SELECT pra.player_id
                    FROM player_rolling_averages pra
                    JOIN player_bio pb ON pra.player_id = pb.player_id
                    WHERE pb.team = ?
                    ORDER BY pra.avg_points DESC
                    LIMIT 10
                """, (team.upper(),))
                
                for row in cursor.fetchall():
                    proj = self.project_player(row['player_id'], opponent, opp_def, pace_mult)
                    if proj:
                        proj['team'] = team
                        result['projections'].append(proj)
            
            conn.close()
        except Exception as e:
            logger.error(f"Error analyzing game: {e}")
        
        return result


# Quick test
if __name__ == '__main__':
    engine = MultiStatConfluence()
    result = engine.analyze_game('CLE', 'LAL')
    
    print(f"\n{'='*80}")
    print(f"MULTI-STAT CONFLUENCE: {result['game']}")
    print(f"{'='*80}")
    
    for p in result['projections'][:5]:
        print(f"\n{p['player_name']} ({p['team']})")
        for stat in ['pts', 'reb', 'ast', '3pm']:
            proj = p['projections'][stat]
            print(f"  {stat.upper():4}: {proj['baseline']:>5.1f} -> {proj['projected']:>5.1f} ({proj['delta']:+.1f}) [{proj['grade']}] {proj['confidence']}%")
