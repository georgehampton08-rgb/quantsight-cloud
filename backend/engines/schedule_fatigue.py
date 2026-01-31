"""
Schedule Fatigue Engine v3.1
============================
Rest-Decay Factor applied to Gaussian μ.

Modifiers:
- B2B Road: -8%
- B2B Home: -5%
- 3-in-4: -6%
- 4-in-6: -4%
- 3+ Days Rest: +3%
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FatigueResult:
    """Result of fatigue calculation"""
    modifier: float
    reason: str
    days_rest: int
    is_b2b: bool
    is_road: bool


class ScheduleFatigueEngine:
    """
    Rest-Decay Factor applied directly to Gaussian μ.
    
    NBA schedule fatigue significantly impacts performance:
    - B2B on road: Players average -8% in scoring
    - Extended rest: Small boost in efficiency
    """
    
    FATIGUE_MODIFIERS = {
        'B2B_road': -0.08,     # Back-to-back on road
        'B2B_home': -0.05,     # Back-to-back at home
        '3_in_4': -0.06,       # 3 games in 4 nights
        '4_in_6': -0.04,       # 4 games in 6 nights
        'rest_3plus': +0.03,   # 3+ days rest bonus
        'rest_2': 0.0,         # Normal rest
        'rest_1': -0.02,       # One day rest (not B2B but close)
    }
    
    def __init__(self):
        self._schedule_cache: Dict[str, List[Dict]] = {}
    
    def calculate_fatigue(
        self,
        game_date: date,
        is_road: bool,
        recent_games: List[Dict]
    ) -> FatigueResult:
        """
        Calculate fatigue modifier based on schedule.
        
        Args:
            game_date: Date of upcoming game
            is_road: Whether game is on the road
            recent_games: List of recent game dicts with 'date' field
            
        Returns:
            FatigueResult with modifier and context
        """
        if not recent_games:
            return FatigueResult(
                modifier=0.0,
                reason="No recent game data",
                days_rest=7,
                is_b2b=False,
                is_road=is_road
            )
        
        # Parse game dates
        game_dates = self._parse_dates(recent_games)
        
        if not game_dates:
            return FatigueResult(
                modifier=0.0,
                reason="Could not parse game dates",
                days_rest=7,
                is_b2b=False,
                is_road=is_road
            )
        
        # Get most recent game date
        last_game = max(game_dates)
        days_rest = (game_date - last_game).days
        
        # Check for B2B
        is_b2b = days_rest <= 1
        
        # Check for 3-in-4 or 4-in-6
        games_in_4 = sum(1 for d in game_dates if (game_date - d).days <= 4)
        games_in_6 = sum(1 for d in game_dates if (game_date - d).days <= 6)
        
        # Determine modifier
        if is_b2b and is_road:
            modifier = self.FATIGUE_MODIFIERS['B2B_road']
            reason = "Back-to-back on road"
        elif is_b2b:
            modifier = self.FATIGUE_MODIFIERS['B2B_home']
            reason = "Back-to-back at home"
        elif games_in_4 >= 3:
            modifier = self.FATIGUE_MODIFIERS['3_in_4']
            reason = "3 games in 4 nights"
        elif games_in_6 >= 4:
            modifier = self.FATIGUE_MODIFIERS['4_in_6']
            reason = "4 games in 6 nights"
        elif days_rest >= 3:
            modifier = self.FATIGUE_MODIFIERS['rest_3plus']
            reason = f"{days_rest} days rest (well-rested)"
        elif days_rest == 1:
            modifier = self.FATIGUE_MODIFIERS['rest_1']
            reason = "One day rest"
        else:
            modifier = 0.0
            reason = "Normal rest"
        
        return FatigueResult(
            modifier=modifier,
            reason=reason,
            days_rest=days_rest,
            is_b2b=is_b2b,
            is_road=is_road
        )
    
    def _parse_dates(self, games: List[Dict]) -> List[date]:
        """Parse game dates from various formats"""
        dates = []
        
        for game in games:
            date_str = game.get('date') or game.get('game_date') or game.get('GAME_DATE')
            
            if not date_str:
                continue
            
            try:
                if isinstance(date_str, date):
                    dates.append(date_str)
                elif isinstance(date_str, datetime):
                    dates.append(date_str.date())
                else:
                    # Try common formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d']:
                        try:
                            dates.append(datetime.strptime(str(date_str)[:10], fmt).date())
                            break
                        except ValueError:
                            continue
            except Exception:
                continue
        
        return dates
    
    def apply_to_mean(self, base_mean: float, fatigue_result: FatigueResult) -> float:
        """
        Apply fatigue modifier to Gaussian mean.
        
        Args:
            base_mean: Original EMA mean
            fatigue_result: Result from calculate_fatigue()
            
        Returns:
            Adjusted mean
        """
        return base_mean * (1 + fatigue_result.modifier)
    
    def get_modifier_table(self) -> Dict[str, float]:
        """Return the fatigue modifier table for reference"""
        return self.FATIGUE_MODIFIERS.copy()
