"""
Shared Core Pure Function Tests
===============================
Platform-agnostic tests that can run on any environment.
"""

import unittest
from datetime import date

# Import pure functions from shared_core
from shared_core.engines.pie_calculator import calculate_pie, calculate_pie_percentile
from shared_core.engines.fatigue_engine import (
    calculate_fatigue_adjustment,
    apply_fatigue_to_mean,
    get_in_game_fatigue_penalty,
    FatigueResult
)
from shared_core.engines.defense_matrix import (
    calculate_defense_friction,
    apply_def_rating_modifier,
    calculate_team_defense_modifier,
    DefenderProfile
)
from shared_core.engines.crucible_core import (
    CrucibleCore,
    PlayerSimState,
    PlayType,
    GamePhase
)
from shared_core.calculators.advanced_stats import (
    calculate_true_shooting,
    calculate_effective_fg,
    calculate_usage_rate
)
from shared_core.calculators.matchup_grades import (
    calculate_matchup_grade,
    calculate_target_fade_classification,
    calculate_confidence_score
)


class TestPIECalculator(unittest.TestCase):
    """Test PIE calculation pure functions."""
    
    def test_basic_pie_calculation(self):
        """Test PIE with standard stat line."""
        stats = {
            'pts': 25, 'fgm': 9, 'fga': 18,
            'ftm': 5, 'fta': 6, 'reb': 8,
            'ast': 5, 'stl': 1.5, 'blk': 0.5,
            'pf': 2.5, 'to': 2
        }
        pie = calculate_pie(stats)
        self.assertGreater(pie, 0.05)
        self.assertLess(pie, 0.30)
    
    def test_pie_with_zeros(self):
        """Test PIE handles zero stats gracefully."""
        stats = {'pts': 0, 'fgm': 0, 'fga': 0, 'reb': 0, 'ast': 0}
        pie = calculate_pie(stats)
        self.assertEqual(pie, 0.0)
    
    def test_pie_percentile(self):
        """Test PIE percentile conversion."""
        self.assertGreaterEqual(calculate_pie_percentile(0.20), 95)
        self.assertGreaterEqual(calculate_pie_percentile(0.15), 85)
        self.assertLessEqual(calculate_pie_percentile(0.05), 30)


class TestFatigueEngine(unittest.TestCase):
    """Test fatigue calculation pure functions."""
    
    def test_back_to_back_road(self):
        """Test B2B on road gives -8%."""
        games = [{'date': '2026-01-31'}]
        result = calculate_fatigue_adjustment(
            date(2026, 2, 1),
            is_road=True,
            recent_games=games
        )
        self.assertEqual(result.modifier, -0.08)
        self.assertTrue(result.is_b2b)
    
    def test_back_to_back_home(self):
        """Test B2B at home gives -5%."""
        games = [{'date': '2026-01-31'}]
        result = calculate_fatigue_adjustment(
            date(2026, 2, 1),
            is_road=False,
            recent_games=games
        )
        self.assertEqual(result.modifier, -0.05)
    
    def test_well_rested(self):
        """Test 3+ days rest gives +3%."""
        games = [{'date': '2026-01-28'}]
        result = calculate_fatigue_adjustment(
            date(2026, 2, 1),
            is_road=False,
            recent_games=games
        )
        self.assertEqual(result.modifier, 0.03)
    
    def test_apply_to_mean(self):
        """Test fatigue applied to projection mean."""
        result = FatigueResult(-0.08, "B2B", 1, True, True)
        adjusted = apply_fatigue_to_mean(25.0, result)
        self.assertEqual(adjusted, 23.0)
    
    def test_in_game_fatigue(self):
        """Test in-game fatigue accumulation."""
        penalty = get_in_game_fatigue_penalty(24.0, age=25)
        self.assertAlmostEqual(penalty, 0.03, places=2)
        
        # Older players fatigue faster
        penalty_older = get_in_game_fatigue_penalty(24.0, age=35)
        self.assertGreater(penalty_older, penalty)


class TestDefenseMatrix(unittest.TestCase):
    """Test defensive friction pure functions."""
    
    def test_elite_defender_friction(self):
        """Test elite defender reduces shooting."""
        adjusted, reason = calculate_defense_friction(0.52, 0.42, '2PT')
        self.assertLess(adjusted, 0.52)
        self.assertIn('Elite', reason)
    
    def test_poor_defender_friction(self):
        """Test poor defender boosts shooting."""
        adjusted, reason = calculate_defense_friction(0.52, 0.52, '2PT')
        self.assertGreater(adjusted, 0.52)
        self.assertIn('Weak', reason)
    
    def test_def_rating_modifier(self):
        """Test defensive rating modifier."""
        adjusted, reason = apply_def_rating_modifier(0.50, 105.0)
        self.assertLess(adjusted, 0.50)
        self.assertIn('Elite', reason)
    
    def test_team_defense_modifier(self):
        """Test team-level defense modifier."""
        modifier = calculate_team_defense_modifier(105.0)  # Elite defense
        self.assertLess(modifier, 1.0)
        
        modifier = calculate_team_defense_modifier(118.0)  # Poor defense
        self.assertGreater(modifier, 1.0)


class TestCrucibleCore(unittest.TestCase):
    """Test Crucible core pure functions."""
    
    def test_play_probabilities_cold_streak(self):
        """Test play probabilities adjust for cold streak."""
        player = PlayerSimState(
            player_id="123",
            name="Test Player",
            consecutive_misses=4
        )
        probs = CrucibleCore.get_play_probabilities(player)
        
        # Cold player should pass more
        self.assertGreater(probs[PlayType.PASS], 0.30)
    
    def test_play_probabilities_clutch(self):
        """Test clutch time boosts high PIE player."""
        player = PlayerSimState(
            player_id="123",
            name="Test Player",
            archetype="Scorer",
            pie=0.18
        )
        probs_normal = CrucibleCore.get_play_probabilities(player, is_clutch_time=False)
        probs_clutch = CrucibleCore.get_play_probabilities(
            player, is_clutch_time=True, is_highest_pie_on_floor=True
        )
        
        # Clutch should increase shooting probability
        total_shots_clutch = probs_clutch[PlayType.TWO_POINT_ATTEMPT] + probs_clutch[PlayType.THREE_POINT_ATTEMPT]
        total_shots_normal = probs_normal[PlayType.TWO_POINT_ATTEMPT] + probs_normal[PlayType.THREE_POINT_ATTEMPT]
        self.assertGreater(total_shots_clutch, total_shots_normal)
    
    def test_game_phase_detection(self):
        """Test game phase determination."""
        phase = CrucibleCore.determine_game_phase(4, 200, 3)
        self.assertEqual(phase, GamePhase.CLUTCH)
        
        phase = CrucibleCore.determine_game_phase(4, 100, 22)
        self.assertEqual(phase, GamePhase.GARBAGE_TIME)


class TestAdvancedStats(unittest.TestCase):
    """Test advanced stats calculators."""
    
    def test_true_shooting(self):
        """Test TS% calculation."""
        ts = calculate_true_shooting(25, 18, 6)
        self.assertGreater(ts, 0.55)
        self.assertLess(ts, 0.65)
    
    def test_effective_fg(self):
        """Test eFG% calculation."""
        efg = calculate_effective_fg(9, 3, 18)
        self.assertAlmostEqual(efg, 0.583, places=2)
    
    def test_usage_rate(self):
        """Test USG% calculation."""
        usg = calculate_usage_rate(18, 6, 2, 36, 90, 25, 12)
        self.assertGreater(usg, 0.25)
        self.assertLess(usg, 0.35)


class TestMatchupGrades(unittest.TestCase):
    """Test matchup grading functions."""
    
    def test_grade_a(self):
        """Test A grade threshold."""
        grade, score = calculate_matchup_grade(22, 2.0, 0.15)
        self.assertEqual(grade, 'A')
    
    def test_grade_f(self):
        """Test F grade threshold."""
        grade, score = calculate_matchup_grade(3, -1.0, -0.2)
        self.assertEqual(grade, 'F')
    
    def test_target_classification(self):
        """Test TARGET/FADE classification."""
        classification, reason = calculate_target_fade_classification(28, 24)
        self.assertEqual(classification, 'TARGET')
        
        classification, reason = calculate_target_fade_classification(20, 24)
        self.assertEqual(classification, 'FADE')
    
    def test_confidence_score(self):
        """Test confidence score calculation."""
        confidence, breakdown = calculate_confidence_score(
            sample_size=15,
            h2h_weight=0.20,
            form_clarity=0.08,
            environment_balance=0.05
        )
        self.assertGreater(confidence, 0.85)
        self.assertEqual(breakdown['base'], 0.60)


if __name__ == '__main__':
    unittest.main()
