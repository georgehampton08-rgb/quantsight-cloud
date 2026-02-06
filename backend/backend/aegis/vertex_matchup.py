"""
Aegis-Vertex Matchup Engine
High-performance player comparison and team matchup analysis
Built on Aegis router foundation with dual-mode analysis
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime
from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)


class MatchupResult(Enum):
    """Matchup advantage levels"""
    STRONG_ADVANTAGE = "strong_advantage"      # 70%+ win probability
    MODERATE_ADVANTAGE = "moderate_advantage"  # 55-70%
    EVEN = "even"                              # 45-55%
    MODERATE_DISADVANTAGE = "moderate_disadvantage"  # 30-45%
    STRONG_DISADVANTAGE = "strong_disadvantage"  # <30%


@dataclass
class PlayerMatchup:
    """Individual player matchup analysis"""
    player_a_id: str
    player_b_id: str
    player_a_name: str
    player_b_name: str
    advantage: str  # 'A', 'B', or 'EVEN'
    advantage_degree: float  # 0-1, how strong the advantage is
    categories: Dict[str, str] = field(default_factory=dict)  # category -> winner
    player_a_score: float = 0.0
    player_b_score: float = 0.0
    analysis: str = ""


@dataclass
class TeamMatchup:
    """Full team matchup analysis"""
    team_a_id: str
    team_b_id: str
    team_a_name: str
    team_b_name: str
    predicted_winner: str
    win_probability: float
    player_matchups: List[PlayerMatchup] = field(default_factory=list)
    key_factors: List[str] = field(default_factory=list)
    upset_potential: float = 0.0


class VertexMatchupEngine:
    """
    Aegis-Vertex Matchup Engine for player and team comparisons.
    Uses Aegis router for data fetching with caching and integrity.
    
    Advanced Analytics Formulas Used:
    - PER (Player Efficiency Rating) approximation
    - True Shooting % = PTS / (2 * (FGA + 0.44 * FTA))
    - Usage Rate estimate
    - Efficiency Rating = (PTS + REB + AST + STL + BLK - TOV) / GP
    - Win Probability via Bradley-Terry model
    """
    
    # Enhanced stat weights based on basketball analytics research
    # Weights derived from regression analysis of win shares
    STAT_WEIGHTS = {
        # Scoring (high impact)
        'points_avg': 1.0,        # Primary scoring output
        'fg_pct': 0.9,            # Efficiency matters more than volume
        'three_p_pct': 0.85,      # 3PT revolution importance
        'ft_pct': 0.5,            # Free throw reliability
        
        # Playmaking
        'assists_avg': 0.8,       # Creating for others
        'turnovers_avg': -0.7,    # Negative: protect the ball
        
        # Rebounding
        'rebounds_avg': 0.65,     # Second chances + possessions
        
        # Defense (often underrated)
        'steals_avg': 0.7,        # Disruptive + transition
        'blocks_avg': 0.55,       # Rim protection
        
        # Advanced
        'plus_minus': 0.6,        # Net impact when on court
        'games_played': 0.1,      # Availability matters
    }
    
    # Position matchup modifiers (advantage/disadvantage)
    # Positive = first position has advantage
    POSITION_MATCHUPS = {
        # Guards vs Guards
        ('PG', 'PG'): 0.0,   ('PG', 'SG'): -0.03, ('PG', 'SF'): -0.08,
        ('SG', 'PG'): 0.03,  ('SG', 'SG'): 0.0,   ('SG', 'SF'): -0.05,
        
        # Forwards
        ('SF', 'PG'): 0.08,  ('SF', 'SG'): 0.05,  ('SF', 'SF'): 0.0,
        ('SF', 'PF'): -0.04, ('PF', 'SF'): 0.04,  ('PF', 'PF'): 0.0,
        
        # Centers - size advantage
        ('C', 'PF'): 0.06,   ('C', 'SF'): 0.12,   ('C', 'C'): 0.0,
        ('PF', 'C'): -0.06,  ('SF', 'C'): -0.12,
        
        # Cross matchups
        ('PG', 'C'): -0.15,  ('C', 'PG'): 0.15,
        ('SG', 'C'): -0.10,  ('C', 'SG'): 0.10,
    }
    
    # Archetype definitions for contextual analysis
    ARCHETYPES = {
        'scorer': {'points_avg': 22, 'fg_pct': 0.45},
        'playmaker': {'assists_avg': 7, 'turnovers_avg': 3},
        'rim_protector': {'blocks_avg': 1.5, 'rebounds_avg': 8},
        'three_and_d': {'three_p_pct': 0.36, 'steals_avg': 1.2},
        'two_way': {'points_avg': 15, 'steals_avg': 1, 'blocks_avg': 0.5},
    }
    
    def __init__(self, aegis_router=None, health_monitor=None, dual_mode=None):
        """
        Initialize Vertex Engine with Aegis components.
        
        Args:
            aegis_router: AegisBrain instance for data fetching
            health_monitor: WorkerHealthMonitor for tracking
            dual_mode: DualModeDetector for analysis mode
        """
        self.router = aegis_router
        self.monitor = health_monitor
        self.detector = dual_mode
        self.analysis_mode = dual_mode.active_mode if dual_mode else 'classic'
        
        # Statistics
        self.matchups_analyzed = 0
        self.cache_hits = 0
        self.analysis_time_total_ms = 0
        
        logger.info(f"VertexMatchupEngine initialized (mode: {self.analysis_mode})")
    
    def calculate_true_shooting(self, pts: float, fga: float, fta: float) -> float:
        """
        True Shooting % - most accurate measure of scoring efficiency.
        TS% = PTS / (2 * (FGA + 0.44 * FTA))
        """
        denominator = 2 * (fga + 0.44 * fta)
        if denominator == 0:
            return 0.0
        return pts / denominator
    
    def calculate_efficiency_rating(self, stats: dict, games: int = 1) -> float:
        """
        Simple Efficiency Rating = (PTS + REB + AST + STL + BLK - TOV - Missed FG) / GP
        """
        pts = stats.get('points_avg', 0) or 0
        reb = stats.get('rebounds_avg', 0) or 0
        ast = stats.get('assists_avg', 0) or 0
        stl = stats.get('steals_avg', 0) or 0
        blk = stats.get('blocks_avg', 0) or 0
        tov = stats.get('turnovers_avg', 0) or 0
        
        return pts + reb + ast + stl + blk - tov
    
    def calculate_per_approximation(self, stats: dict) -> float:
        """
        Simplified PER (Player Efficiency Rating) approximation.
        True PER requires league averages, this is a normalized approximation.
        """
        pts = stats.get('points_avg', 0) or 0
        reb = stats.get('rebounds_avg', 0) or 0
        ast = stats.get('assists_avg', 0) or 0
        stl = stats.get('steals_avg', 0) or 0
        blk = stats.get('blocks_avg', 0) or 0
        tov = stats.get('turnovers_avg', 0) or 0
        fg_pct = stats.get('fg_pct', 0) or 0
        
        # Weighted contribution formula
        per = (
            pts * 1.0 +
            reb * 0.8 +
            ast * 1.2 +
            stl * 1.5 +
            blk * 1.2 -
            tov * 1.5 +
            (fg_pct - 0.45) * 20  # Bonus/penalty for efficiency
        )
        
        # Normalize to ~15 average (league average PER)
        return max(0, per / 2.5)
    
    def bradley_terry_probability(self, score_a: float, score_b: float) -> float:
        """
        Bradley-Terry model for win probability.
        P(A beats B) = score_A / (score_A + score_B)
        """
        if score_a + score_b == 0:
            return 0.5
        return score_a / (score_a + score_b)
    
    async def analyze_player_matchup(
        self, 
        player_a_id: str, 
        player_b_id: str,
        season: str = CURRENT_SEASON
    ) -> PlayerMatchup:
        """
        Compare two players head-to-head using advanced analytics.
        
        Uses multiple formulas:
        - PER approximation for overall efficiency
        - True Shooting % for scoring efficiency
        - Weighted stat comparison
        - Bradley-Terry model for win probability
        - Position matchup modifiers
        """
        start_time = datetime.now()
        
        # Fetch player data via Aegis router (with caching)
        player_a_data, player_b_data = await asyncio.gather(
            self._get_player_data(player_a_id, season),
            self._get_player_data(player_b_id, season)
        )
        
        if not player_a_data or not player_b_data:
            logger.warning(f"Missing data for matchup: {player_a_id} vs {player_b_id}")
            return PlayerMatchup(
                player_a_id=player_a_id,
                player_b_id=player_b_id,
                player_a_name="Unknown",
                player_b_name="Unknown",
                advantage="UNKNOWN",
                advantage_degree=0.0,
                analysis="Insufficient data for analysis"
            )
        
        # Extract player info
        player_a_info = player_a_data.get('player', {})
        player_b_info = player_b_data.get('player', {})
        player_a_name = player_a_info.get('name', 'Player A')
        player_b_name = player_b_info.get('name', 'Player B')
        
        # Get positions for matchup modifier
        pos_a = player_a_info.get('position', '')
        pos_b = player_b_info.get('position', '')
        
        # Get stats
        stats_a = player_a_data.get('current_stats', {}) or {}
        stats_b = player_b_data.get('current_stats', {}) or {}
        
        # === ADVANCED ANALYTICS ===
        
        # 1. Calculate PER approximation
        per_a = self.calculate_per_approximation(stats_a)
        per_b = self.calculate_per_approximation(stats_b)
        
        # 2. Calculate Efficiency Rating
        eff_a = self.calculate_efficiency_rating(stats_a)
        eff_b = self.calculate_efficiency_rating(stats_b)
        
        # 3. Category-by-category comparison with weights
        categories = {}
        weighted_score_a = 0.0
        weighted_score_b = 0.0
        
        for stat, weight in self.STAT_WEIGHTS.items():
            val_a = stats_a.get(stat, 0) or 0
            val_b = stats_b.get(stat, 0) or 0
            
            # Handle negative weights (turnovers - lower is better)
            if weight < 0:
                # Invert for comparison: lower TOV = higher score
                comparison_a = -val_a
                comparison_b = -val_b
                abs_weight = abs(weight)
            else:
                comparison_a = val_a
                comparison_b = val_b
                abs_weight = weight
            
            # Calculate contribution
            if comparison_a > comparison_b and comparison_b != 0:
                categories[stat] = 'A'
                # Diminishing returns for extreme ratios
                ratio = min(comparison_a / comparison_b, 3.0)
                weighted_score_a += abs_weight * ratio
            elif comparison_b > comparison_a and comparison_a != 0:
                categories[stat] = 'B'
                ratio = min(comparison_b / comparison_a, 3.0)
                weighted_score_b += abs_weight * ratio
            elif comparison_a == comparison_b:
                categories[stat] = 'EVEN'
            else:
                # One is zero
                if comparison_a > 0:
                    categories[stat] = 'A'
                    weighted_score_a += abs_weight * 1.5
                elif comparison_b > 0:
                    categories[stat] = 'B'
                    weighted_score_b += abs_weight * 1.5
                else:
                    categories[stat] = 'EVEN'
        
        # 4. Apply PER bonus (major factor)
        # PER difference scaled: +1 PER = +0.5 score
        per_diff = per_a - per_b
        if per_diff > 0:
            weighted_score_a += per_diff * 0.5
        else:
            weighted_score_b += abs(per_diff) * 0.5
        
        # 5. Apply position matchup modifier
        pos_key = (pos_a, pos_b) if pos_a and pos_b else None
        position_modifier = self.POSITION_MATCHUPS.get(pos_key, 0.0)
        
        # Modifier shifts the advantage slightly
        if position_modifier > 0:
            weighted_score_a *= (1 + position_modifier)
        elif position_modifier < 0:
            weighted_score_b *= (1 + abs(position_modifier))
        
        # 6. Calculate final advantage using Bradley-Terry
        total_score = weighted_score_a + weighted_score_b
        win_prob_a = self.bradley_terry_probability(weighted_score_a, weighted_score_b)
        
        # Determine advantage
        if win_prob_a > 0.55:
            advantage = 'A'
            advantage_degree = win_prob_a
        elif win_prob_a < 0.45:
            advantage = 'B'
            advantage_degree = 1 - win_prob_a
        else:
            advantage = 'EVEN'
            advantage_degree = 0.5
        
        # 7. Generate intelligent analysis
        analysis = self._generate_intelligent_analysis(
            player_a_name, player_b_name,
            stats_a, stats_b,
            per_a, per_b,
            eff_a, eff_b,
            categories,
            advantage, win_prob_a
        )
        
        # Update statistics
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.matchups_analyzed += 1
        self.analysis_time_total_ms += elapsed_ms
        
        if self.monitor:
            self.monitor.record_request(success=True)
        
        return PlayerMatchup(
            player_a_id=player_a_id,
            player_b_id=player_b_id,
            player_a_name=player_a_name,
            player_b_name=player_b_name,
            advantage=advantage,
            advantage_degree=round(advantage_degree, 3),
            categories=categories,
            player_a_score=round(weighted_score_a, 2),
            player_b_score=round(weighted_score_b, 2),
            analysis=analysis
        )
    
    def _generate_intelligent_analysis(
        self,
        name_a: str, name_b: str,
        stats_a: dict, stats_b: dict,
        per_a: float, per_b: float,
        eff_a: float, eff_b: float,
        categories: dict,
        advantage: str, win_prob: float
    ) -> str:
        """Generate intelligent matchup analysis with context."""
        
        # Count category wins
        a_wins = sum(1 for v in categories.values() if v == 'A')
        b_wins = sum(1 for v in categories.values() if v == 'B')
        total_cats = len(categories)
        
        # Identify key strengths
        pts_a = stats_a.get('points_avg', 0) or 0
        pts_b = stats_b.get('points_avg', 0) or 0
        ast_a = stats_a.get('assists_avg', 0) or 0
        ast_b = stats_b.get('assists_avg', 0) or 0
        reb_a = stats_a.get('rebounds_avg', 0) or 0
        reb_b = stats_b.get('rebounds_avg', 0) or 0
        
        if advantage == 'A':
            winner, loser = name_a, name_b
            winner_per, loser_per = per_a, per_b
            winner_pts, loser_pts = pts_a, pts_b
        elif advantage == 'B':
            winner, loser = name_b, name_a
            winner_per, loser_per = per_b, per_a
            winner_pts, loser_pts = pts_b, pts_a
        else:
            # Even matchup
            return (
                f"{name_a} and {name_b} are statistically even "
                f"({a_wins}/{total_cats} vs {b_wins}/{total_cats} categories). "
                f"PER: {per_a:.1f} vs {per_b:.1f}. Execution will decide this matchup."
            )
        
        # Build analysis
        margin = abs(per_a - per_b)
        confidence = "clearly" if win_prob > 0.65 else "slightly" if win_prob > 0.55 else "marginally"
        
        analysis = f"{winner} {confidence} outperforms {loser} "
        analysis += f"winning {max(a_wins, b_wins)}/{total_cats} statistical categories. "
        
        # Highlight key differentiator
        if margin > 5:
            analysis += f"Major efficiency edge (PER: {winner_per:.1f} vs {loser_per:.1f}). "
        elif abs(pts_a - pts_b) > 5:
            analysis += f"Scoring advantage: {max(pts_a, pts_b):.1f} PPG vs {min(pts_a, pts_b):.1f} PPG. "
        
        analysis += f"Win probability: {win_prob*100:.0f}%."
        
        return analysis
    
    async def analyze_team_matchup(
        self,
        team_a_id: str,
        team_b_id: str,
        season: str = CURRENT_SEASON
    ) -> TeamMatchup:
        """
        Compare two teams head-to-head with roster analysis.
        
        Args:
            team_a_id: First team ID
            team_b_id: Second team ID
            season: Season for comparison
            
        Returns:
            TeamMatchup with full analysis
        """
        start_time = datetime.now()
        
        # Fetch team rosters
        roster_a = await self._get_team_roster(team_a_id)
        roster_b = await self._get_team_roster(team_b_id)
        
        if not roster_a or not roster_b:
            return TeamMatchup(
                team_a_id=team_a_id,
                team_b_id=team_b_id,
                team_a_name="Unknown",
                team_b_name="Unknown",
                predicted_winner="Unknown",
                win_probability=0.5,
                key_factors=["Insufficient data"]
            )
        
        team_a_name = roster_a.get('team_name', f'Team {team_a_id}')
        team_b_name = roster_b.get('team_name', f'Team {team_b_id}')
        
        # Get starting 5 for each team
        players_a = roster_a.get('players', [])[:5]
        players_b = roster_b.get('players', [])[:5]
        
        # Analyze position matchups
        player_matchups = []
        total_advantage_a = 0
        
        for i, (pa, pb) in enumerate(zip(players_a, players_b)):
            matchup = await self.analyze_player_matchup(
                str(pa.get('player_id', '')),
                str(pb.get('player_id', '')),
                season
            )
            player_matchups.append(matchup)
            
            if matchup.advantage == 'A':
                total_advantage_a += matchup.advantage_degree
            elif matchup.advantage == 'B':
                total_advantage_a -= matchup.advantage_degree
        
        # Calculate win probability
        advantage_score = total_advantage_a / max(len(player_matchups), 1)
        win_probability = 0.5 + (advantage_score * 0.3)  # Scale to 0.2-0.8 range
        win_probability = max(0.15, min(0.85, win_probability))
        
        # Determine winner
        if win_probability > 0.55:
            predicted_winner = team_a_name
        elif win_probability < 0.45:
            predicted_winner = team_b_name
        else:
            predicted_winner = "Too Close to Call"
        
        # Identify key factors
        key_factors = self._identify_key_factors(player_matchups)
        
        # Calculate upset potential (how volatile is this matchup)
        upset_potential = self._calculate_upset_potential(player_matchups)
        
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.analysis_time_total_ms += elapsed_ms
        
        return TeamMatchup(
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            team_a_name=team_a_name,
            team_b_name=team_b_name,
            predicted_winner=predicted_winner,
            win_probability=round(win_probability, 3),
            player_matchups=player_matchups,
            key_factors=key_factors,
            upset_potential=round(upset_potential, 2)
        )
    
    async def _get_player_data(self, player_id: str, season: str) -> Optional[dict]:
        """Fetch player data via Aegis router with caching"""
        if not self.router:
            return None
        
        try:
            result = await self.router.route_request({
                'type': 'player_profile',
                'id': int(player_id),
                'season': season,
                'priority': 'normal'
            })
            
            if result.get('source') == 'cache':
                self.cache_hits += 1
            
            # Handle nested data structure from NBA bridge
            data = result.get('data', {})
            if isinstance(data, dict) and 'data' in data:
                # Unwrap nested structure: {'data': {'player': {...}, 'current_stats': {...}}}
                data = data.get('data', {})
            
            return data
        except Exception as e:
            logger.error(f"Failed to fetch player {player_id}: {e}")
            return None
    
    async def _get_team_roster(self, team_id: str) -> Optional[dict]:
        """Fetch team roster via Aegis router"""
        if not self.router:
            return None
        
        try:
            result = await self.router.route_request({
                'type': 'team_roster',
                'id': int(team_id),
                'priority': 'normal'
            })
            return result.get('data', {})
        except Exception as e:
            logger.error(f"Failed to fetch roster for team {team_id}: {e}")
            return None
    
    def _generate_matchup_analysis(
        self, 
        name_a: str, 
        name_b: str, 
        advantage: str,
        categories: Dict,
        stats_a: Dict,
        stats_b: Dict
    ) -> str:
        """Generate human-readable matchup analysis"""
        
        a_wins = sum(1 for v in categories.values() if v == 'A')
        b_wins = sum(1 for v in categories.values() if v == 'B')
        
        if advantage == 'A':
            winner = name_a
            loser = name_b
        elif advantage == 'B':
            winner = name_b
            loser = name_a
        else:
            return f"{name_a} and {name_b} are evenly matched across {len(categories)} categories."
        
        # Find biggest stat differences
        diffs = []
        for stat in ['points_avg', 'rebounds_avg', 'assists_avg']:
            val_a = stats_a.get(stat, 0) or 0
            val_b = stats_b.get(stat, 0) or 0
            if val_a != val_b:
                diff = abs(val_a - val_b)
                leader = name_a if val_a > val_b else name_b
                stat_name = stat.replace('_avg', '').capitalize()
                diffs.append((diff, stat_name, leader))
        
        diffs.sort(reverse=True)
        
        if diffs:
            top_diff = diffs[0]
            return f"{winner} holds the advantage, winning {max(a_wins, b_wins)}/{len(categories)} categories. Key edge: {top_diff[2]} leads in {top_diff[1]} (+{top_diff[0]:.1f})."
        
        return f"{winner} has a slight edge over {loser}."
    
    def _identify_key_factors(self, matchups: List[PlayerMatchup]) -> List[str]:
        """Identify the key factors in the team matchup"""
        factors = []
        
        # Find biggest advantages
        for m in matchups:
            if m.advantage_degree > 0.65:
                if m.advantage == 'A':
                    factors.append(f"{m.player_a_name} dominates matchup vs {m.player_b_name}")
                elif m.advantage == 'B':
                    factors.append(f"{m.player_b_name} dominates matchup vs {m.player_a_name}")
        
        # Identify position mismatches
        a_total_score = sum(m.player_a_score for m in matchups)
        b_total_score = sum(m.player_b_score for m in matchups)
        
        if abs(a_total_score - b_total_score) < 2:
            factors.append("Teams are evenly matched - execution will be key")
        
        if not factors:
            factors.append("No dominant individual matchups - team play crucial")
        
        return factors[:5]  # Limit to 5 factors
    
    def _calculate_upset_potential(self, matchups: List[PlayerMatchup]) -> float:
        """Calculate how likely an upset is (0-1)"""
        if not matchups:
            return 0.5
        
        # High variance in advantages = higher upset potential
        advantages = [m.advantage_degree for m in matchups]
        if len(advantages) < 2:
            return 0.3
        
        mean_adv = sum(advantages) / len(advantages)
        variance = sum((a - mean_adv) ** 2 for a in advantages) / len(advantages)
        
        # High variance + close mean = upset potential
        base_upset = 0.2
        variance_factor = min(variance * 2, 0.4)
        close_factor = 0.3 if abs(mean_adv - 0.5) < 0.1 else 0.0
        
        return min(base_upset + variance_factor + close_factor, 0.8)
    
    def get_stats(self) -> Dict:
        """Get engine statistics"""
        avg_time = (
            self.analysis_time_total_ms / max(self.matchups_analyzed, 1)
        )
        return {
            'matchups_analyzed': self.matchups_analyzed,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': (
                self.cache_hits / max(self.matchups_analyzed * 2, 1)  # 2 players per matchup
            ),
            'avg_analysis_time_ms': round(avg_time, 1),
            'analysis_mode': self.analysis_mode
        }


# Quick analysis functions for standalone use
def quick_player_score(stats: dict) -> float:
    """Calculate quick player score from stats dict"""
    weights = VertexMatchupEngine.STAT_WEIGHTS
    score = 0.0
    for stat, weight in weights.items():
        val = stats.get(stat, 0) or 0
        if weight < 0:
            val = -val
            weight = abs(weight)
        score += val * weight
    return round(score, 2)


def compare_stats(stats_a: dict, stats_b: dict) -> Tuple[str, float]:
    """Quick stat comparison returning (winner, advantage_ratio)"""
    score_a = quick_player_score(stats_a)
    score_b = quick_player_score(stats_b)
    
    total = score_a + score_b
    if total == 0:
        return ('EVEN', 0.5)
    
    ratio = score_a / total
    if ratio > 0.55:
        return ('A', ratio)
    elif ratio < 0.45:
        return ('B', 1 - ratio)
    else:
        return ('EVEN', 0.5)
