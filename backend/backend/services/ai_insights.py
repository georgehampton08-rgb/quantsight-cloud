"""
Gemini AI Insights Service (v2 - New SDK)
=========================================
Generates natural language insights from confluence data using NEW Gemini SDK.
"""
import os
import json
import logging
from typing import Dict, List, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiInsights:
    """
    Generates AI-powered matchup insights using NEW Gemini SDK.
    Falls back to rule-based insights if API unavailable.
    """
    
    DEFAULT_MODEL = 'gemini-1.5-flash'
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        self.client = None
        self.model_id = os.getenv('GEMINI_MODEL', self.DEFAULT_MODEL)
        
        if '2.0-flash-exp' in self.model_id:
             self.model_id = 'gemini-1.5-flash'
             
        self._init_gemini()
    
    def _init_gemini(self):
        """Initialize Gemini client"""
        if not self.api_key:
            logger.warning("No Gemini API key found. Using rule-based insights.")
            return
        
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"Gemini AI (New SDK) initialized with model: {self.model_id}")
        except Exception as e:
            logger.error(f"Error initializing Gemini: {e}")
    
    def generate_insights(self, confluence_data: Dict) -> Dict:
        """
        Generate comprehensive insights from confluence data.
        Returns structured insights with summary, top plays, and fade plays.
        """
        # Extract key data
        projections = confluence_data.get('projections', [])
        context = confluence_data.get('matchup_context', {})
        
        # Identify top and fade plays
        top_plays = self._identify_top_plays(projections)
        fade_plays = self._identify_fade_plays(projections)
        
        # Generate AI summary
        if self.client:
            summary = self._generate_gemini_summary(confluence_data, top_plays, fade_plays)
        else:
            summary = self._generate_rule_based_summary(confluence_data, top_plays, fade_plays)
        
        return {
            'summary': summary,
            'top_plays': top_plays,
            'fade_plays': fade_plays,
            'ai_powered': self.client is not None,
            'game': confluence_data.get('game', 'Unknown'),
        }
    
    def _identify_top_plays(self, projections: List[Dict], limit: int = 5) -> List[Dict]:
        """Identify best matchup advantages (same as v1)"""
        plays = []
        for p in projections:
            player_name = p.get('player_name', 'Unknown')
            team = p.get('team', '')
            for stat in ['pts', 'reb', 'ast', '3pm']:
                proj = p.get('projections', {}).get(stat, {})
                # Include A, B, and B- grades for top plays (adjusted thresholds)
                if proj.get('grade', '') in ['A+', 'A', 'B', 'B-'] and proj.get('delta', 0) > 0:
                    plays.append({
                        'player': player_name, 'team': team, 'stat': stat.upper(),
                        'baseline': proj.get('baseline', 0), 'projected': proj.get('projected', 0),
                        'delta': proj.get('delta', 0), 'grade': proj.get('grade', '?'),
                        'confidence': proj.get('confidence', 0), 'reason': f"{proj.get('grade_label', '')} matchup",
                    })
        plays.sort(key=lambda x: (x['delta'] / x['baseline']) if x['baseline'] > 0 else 0, reverse=True)
        return plays[:limit]
    
    def _identify_fade_plays(self, projections: List[Dict], limit: int = 5) -> List[Dict]:
        """Identify worst matchup advantages (same as v1)"""
        plays = []
        for p in projections:
            player_name = p.get('player_name', 'Unknown')
            team = p.get('team', '')
            form_label = p.get('form_label', 'NEUTRAL')
            for stat in ['pts', 'reb', 'ast', '3pm']:
                proj = p.get('projections', {}).get(stat, {})
                # Include D, D-, and F grades for fade plays (adjusted thresholds)
                is_bad_grade = proj.get('grade', '') in ['F', 'D', 'D-']
                is_cold = form_label == 'COLD' and proj.get('delta', 0) < -1
                if (is_bad_grade or is_cold) and proj.get('delta', 0) < 0:
                    plays.append({
                        'player': player_name, 'team': team, 'stat': stat.upper(),
                        'baseline': proj.get('baseline', 0), 'projected': proj.get('projected', 0),
                        'delta': proj.get('delta', 0), 'grade': proj.get('grade', '?'),
                        'form': form_label, 'confidence': proj.get('confidence', 0),
                        'reason': 'Cold streak' if is_cold else proj.get('grade_label', 'Tough matchup'),
                    })
        plays.sort(key=lambda x: x['delta'])
        return plays[:limit]
    
    def _generate_gemini_summary(self, data: Dict, top_plays: List, fade_plays: List) -> str:
        """Generate AI summary using Client.models.generate_content"""
        try:
            context = data.get('matchup_context', {})
            game = data.get('game', 'Game')
            
            # Extract defense data
            home_def = context.get('home_defense', {})
            away_def = context.get('away_defense', {})
            projected_pace = context.get('projected_pace', 0)
            
            # Build matchup context string
            home_def_str = f"{home_def.get('opp_pts', 'N/A')} PPG allowed, DEF RTG: {home_def.get('def_rating', 'N/A')}" if home_def else "N/A"
            away_def_str = f"{away_def.get('opp_pts', 'N/A')} PPG allowed, DEF RTG: {away_def.get('def_rating', 'N/A')}" if away_def else "N/A"
            pace_str = f"{projected_pace:.1f}" if projected_pace else "N/A"
            
            prompt = f"""You are an NBA analytics expert. Analyze this matchup and provide a concise 3-4 sentence insight.

MATCHUP: {game}
Projected Pace: {pace_str} possessions/game
Home Team Defense: {home_def_str}
Away Team Defense: {away_def_str}

TOP ADVANTAGES:
{json.dumps(top_plays[:2], indent=2)}

FADE WARNINGS:
{json.dumps(fade_plays[:2], indent=2)}

Provide specific, actionable insights using the numbers provided. Mention pace if it's notably fast (>100) or slow (<95), and reference defensive ratings when relevant. Keep it to 3-4 sentences maximum."""


            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Gemini API error (New SDK): {e}")
            return self._generate_rule_based_summary(data, top_plays, fade_plays)
    
    def _generate_rule_based_summary(self, data: Dict, top_plays: List, fade_plays: List) -> str:
        """Generic fallback summary"""
        parts = []
        if top_plays:
            top = top_plays[0]
            parts.append(f"{top['player']} is a primary target with a {top['grade']} grade.")
        if fade_plays:
            fade = fade_plays[0]
            parts.append(f"Caution on {fade['player']} - {fade['reason']}.")
        return ' '.join(parts) if parts else "Data synthesis complete. Review individual player cards for details."
