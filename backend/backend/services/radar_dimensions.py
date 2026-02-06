"""
Radar Dimensions Calculator
============================
Computes the 5 radar chart dimensions from real player stats and opponent defense.
Replaces hardcoded values with data-driven calculations.

Dimensions:
1. Scoring - Based on PPG, TS%, usage rate
2. Playmaking - Based on APG, AST/TO ratio, AST%
3. Rebounding - Based on RPG, REB%
4. Defense - Based on STL, BLK, DFG% impact
5. Pace - Based on team pace and player's pace contribution
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RadarDimensions:
    """Player's 5 radar dimension scores (0-100 scale)"""
    scoring: float
    playmaking: float
    rebounding: float
    defense: float
    pace: float


@dataclass
class OpponentRadarDimensions:
    """Opponent's vulnerability on each dimension (higher = more vulnerable)"""
    scoring: float      # Points allowed over average
    playmaking: float   # Assists allowed over average
    rebounding: float   # Opponent rebounds allowed
    defense: float      # Their defensive weakness (inverted)
    pace: float         # Pace factor


class RadarDimensionsCalculator:
    """
    Calculate radar dimensions from real stats using normalized formulas.
    
    All output values are on 0-100 scale for radar chart display.
    """
    
    # League averages for normalization (2024-25 season baseline)
    LEAGUE_AVERAGES = {
        'ppg': 13.5,       # Average NBA player PPG
        'apg': 2.8,        # Average assists
        'rpg': 4.4,        # Average rebounds
        'spg': 0.75,       # Average steals
        'bpg': 0.45,       # Average blocks
        'fg_pct': 0.465,   # Average FG%
        'three_pct': 0.365, # Average 3P%
        'ts_pct': 0.575,   # Average True Shooting
        'usg_pct': 20.0,   # Average usage rate
        'pace': 100.0,     # League pace baseline
    }
    
    # Max values for 100% score (elite thresholds)
    ELITE_THRESHOLDS = {
        'ppg': 30.0,       # 30 PPG = 100 scoring
        'apg': 10.0,       # 10 APG = 100 playmaking
        'rpg': 14.0,       # 14 RPG = 100 rebounding
        'spg': 2.0,        # 2 SPG elite steals
        'bpg': 2.5,        # 2.5 BPG elite blocks
        'pace': 110.0,     # High pace
    }
    
    def __init__(self):
        pass
    
    def calculate_player_dimensions(self, stats: Dict) -> RadarDimensions:
        """
        Calculate player's 5 radar dimensions from their stats.
        
        Args:
            stats: Dict with points_avg, assists_avg, rebounds_avg, etc.
            
        Returns:
            RadarDimensions with 0-100 scores for each dimension
        """
        # === SCORING DIMENSION ===
        # Formula: 60% volume (PPG) + 25% efficiency (TS%) + 15% usage
        ppg = stats.get('points_avg', 0) or stats.get('points_ema', 0) or 0
        ts_pct = self._calculate_true_shooting(stats)
        usg = stats.get('usage_rate', 20) or 20
        
        # PPG component (scaled to 0-100)
        ppg_score = min(100, (ppg / self.ELITE_THRESHOLDS['ppg']) * 100)
        
        # TS% component (above/below league average)
        ts_above_avg = (ts_pct - self.LEAGUE_AVERAGES['ts_pct']) * 100
        ts_score = 50 + ts_above_avg * 5  # ±10% TS = ±50 points
        ts_score = max(0, min(100, ts_score))
        
        # Usage component
        usg_score = min(100, (usg / 35) * 100)  # 35% usage = 100
        
        scoring = 0.60 * ppg_score + 0.25 * ts_score + 0.15 * usg_score
        
        # === PLAYMAKING DIMENSION ===
        # Formula: 50% assists + 30% AST/TO ratio + 20% assist%
        apg = stats.get('assists_avg', 0) or stats.get('assists_ema', 0) or 0
        tov = stats.get('turnovers_avg', 2) or 2
        ast_ratio = stats.get('ast_ratio', 15) or 15
        
        # APG component
        apg_score = min(100, (apg / self.ELITE_THRESHOLDS['apg']) * 100)
        
        # AST/TO ratio component (2.0 = 50, 4.0 = 100)
        ast_to = apg / max(tov, 0.5)
        ast_to_score = min(100, (ast_to / 4.0) * 100)
        
        # AST% component (20% = 50, 40% = 100)
        ast_ratio_score = min(100, (ast_ratio / 40) * 100)
        
        playmaking = 0.50 * apg_score + 0.30 * ast_to_score + 0.20 * ast_ratio_score
        
        # === REBOUNDING DIMENSION ===
        # Formula: 70% total rebounds + 30% rebound%
        rpg = stats.get('rebounds_avg', 0) or stats.get('rebounds_ema', 0) or 0
        reb_pct = stats.get('reb_pct', 10) or 10  # ~10% is average
        
        rpg_score = min(100, (rpg / self.ELITE_THRESHOLDS['rpg']) * 100)
        reb_pct_score = min(100, (reb_pct / 20) * 100)  # 20% = elite
        
        rebounding = 0.70 * rpg_score + 0.30 * reb_pct_score
        
        # === DEFENSE DIMENSION ===
        # Formula: 35% steals + 35% blocks + 30% DFG% impact
        spg = stats.get('steals_avg', 0) or stats.get('steals_ema', 0) or 0
        bpg = stats.get('blocks_avg', 0) or stats.get('blocks_ema', 0) or 0
        dfg_impact = stats.get('pct_plusminus', 0) or 0  # DFG% vs average
        
        spg_score = min(100, (spg / self.ELITE_THRESHOLDS['spg']) * 100)
        bpg_score = min(100, (bpg / self.ELITE_THRESHOLDS['bpg']) * 100)
        
        # DFG impact: -5% (elite) = +100, +5% (bad) = 0
        dfg_score = 50 - (dfg_impact * 10)  # Scale: -5% = 100, +5% = 0
        dfg_score = max(0, min(100, dfg_score))
        
        defense = 0.35 * spg_score + 0.35 * bpg_score + 0.30 * dfg_score
        
        # === PACE DIMENSION ===
        # Formula: Player's involvement in fast-break, transition play
        player_pace = stats.get('pace', 100) or 100
        
        # Normalize around 100 (league average)
        # 90 pace = 0, 100 = 50, 110 = 100
        pace_score = ((player_pace - 90) / 20) * 100
        pace_score = max(0, min(100, pace_score))
        
        return RadarDimensions(
            scoring=round(scoring, 1),
            playmaking=round(playmaking, 1),
            rebounding=round(rebounding, 1),
            defense=round(defense, 1),
            pace=round(pace_score, 1)
        )
    
    def calculate_opponent_vulnerability(self, team_defense: Dict) -> OpponentRadarDimensions:
        """
        Calculate opponent's vulnerability on each dimension.
        Higher = more vulnerable (better for the player).
        
        Args:
            team_defense: Dict with defensive_rating, paoa, etc.
            
        Returns:
            OpponentRadarDimensions with 0-100 vulnerability scores
        """
        def_rating = team_defense.get('defensive_rating', 110) or 110
        paoa = team_defense.get('paoa', {})  # Points Allowed Over Average
        
        # Get position-specific PAOA if available
        if isinstance(paoa, dict):
            avg_paoa = sum(paoa.values()) / max(len(paoa), 1) if paoa else 0
        else:
            avg_paoa = float(paoa) if paoa else 0
        
        # === SCORING VULNERABILITY ===
        # Based on defensive rating and points allowed
        # 105 def_rating (elite) = 20, 115 (bad) = 80
        scoring_vuln = 50 + (def_rating - 110) * 6
        scoring_vuln += avg_paoa * 3  # PAOA adjustment
        scoring_vuln = max(0, min(100, scoring_vuln))
        
        # === PLAYMAKING VULNERABILITY ===
        # How many assists does this defense allow?
        ast_allowed_over_avg = team_defense.get('ast_allowed_over_avg', 0) or 0
        playmaking_vuln = 50 + ast_allowed_over_avg * 4
        playmaking_vuln = max(0, min(100, playmaking_vuln))
        
        # === REBOUNDING VULNERABILITY ===
        # Opponent rebound rate allowed
        oreb_allowed = team_defense.get('oreb_pct_allowed', 25) or 25  # League avg ~25%
        rebounding_vuln = (oreb_allowed / 35) * 100  # 35% = fully vulnerable
        rebounding_vuln = max(0, min(100, rebounding_vuln))
        
        # === DEFENSE VULNERABILITY ===
        # Their offense efficiency (inverted - high = vulnerable defense is bad for them)
        off_rating = team_defense.get('offensive_rating', 110) or 110
        defense_vuln = 50 - (off_rating - 110) * 4  # Lower off_rating = they struggle to score
        defense_vuln = max(0, min(100, defense_vuln))
        
        # === PACE VULNERABILITY ===
        # Team pace preference
        team_pace = team_defense.get('pace', 100) or 100
        pace_vuln = ((team_pace - 90) / 20) * 100
        pace_vuln = max(0, min(100, pace_vuln))
        
        return OpponentRadarDimensions(
            scoring=round(scoring_vuln, 1),
            playmaking=round(playmaking_vuln, 1),
            rebounding=round(rebounding_vuln, 1),
            defense=round(defense_vuln, 1),
            pace=round(pace_vuln, 1)
        )
    
    def _calculate_true_shooting(self, stats: Dict) -> float:
        """Calculate True Shooting % from stats"""
        pts = stats.get('points_avg', 0) or 0
        fga = stats.get('fga_avg', 0) or stats.get('fga', 10) or 10
        fta = stats.get('fta_avg', 0) or stats.get('fta', 2) or 2
        
        denominator = 2 * (fga + 0.44 * fta)
        if denominator == 0:
            return self.LEAGUE_AVERAGES['ts_pct']
        
        return pts / denominator
    
    def calculate_matchup_radar(
        self, 
        player_stats: Dict, 
        opponent_defense: Dict
    ) -> Tuple[RadarDimensions, OpponentRadarDimensions]:
        """
        Calculate both player dimensions and opponent vulnerability.
        
        Returns:
            Tuple of (player_dimensions, opponent_vulnerability)
        """
        player = self.calculate_player_dimensions(player_stats)
        opponent = self.calculate_opponent_vulnerability(opponent_defense)
        
        logger.info(f"[RADAR] Player: S={player.scoring:.0f} PM={player.playmaking:.0f} "
                   f"R={player.rebounding:.0f} D={player.defense:.0f} P={player.pace:.0f}")
        logger.info(f"[RADAR] Opponent Vuln: S={opponent.scoring:.0f} PM={opponent.playmaking:.0f} "
                   f"R={opponent.rebounding:.0f} D={opponent.defense:.0f} P={opponent.pace:.0f}")
        
        return player, opponent


# Singleton
_calculator = None

def get_radar_calculator() -> RadarDimensionsCalculator:
    global _calculator
    if _calculator is None:
        _calculator = RadarDimensionsCalculator()
    return _calculator
