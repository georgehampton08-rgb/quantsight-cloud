import logging
import os
from typing import Dict, Any, Optional, List
from google import genai
from .nba_api_connector import NBAAPIConnector
from .gemini_injury_fetcher import GeminiInjuryFetcher
from .ai_insights import GeminiInsights

logger = logging.getLogger(__name__)

class UnifiedIntelligenceBridge:
    """
    Unified Bridge for all external intelligence (NBA API + Gemini).
    Simplifies the flow by providing a single point of interaction.
    """
    
    def __init__(self, db_path: str, gemini_api_key: Optional[str] = None):
        self.db_path = db_path
        self.gemini_api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        
        # Initialize sub-services
        self.nba = NBAAPIConnector(db_path=db_path)
        
        # New Gemini Client
        self.gemini_client = None
        if self.gemini_api_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                logger.info("UnifiedBridge: Gemini Client Initialized")
            except Exception as e:
                logger.error(f"UnifiedBridge: Failed to initialize Gemini Client: {e}")
        
        # Legacy wrappers (migrated internally)
        self.injury_fetcher = GeminiInjuryFetcher(api_key=self.gemini_api_key)
        self.insights_generator = GeminiInsights(api_key=self.gemini_api_key)
        
    def get_player_full_context(self, player_id: str, player_name: str) -> Dict[str, Any]:
        """
        Get everything about a player: stats, injury status, and AI insights.
        """
        logger.info(f"UnifiedBridge: Fetching full context for {player_name} ({player_id})")
        
        # 1. Fetch Stats from NBA API (via Aegis/NBAConnector logic)
        stats = self.nba.get_player_stats(player_id)
        logs = self.nba.get_player_game_logs(player_id)
        
        # 2. Fetch Injury Status from Gemini
        injury = self.injury_fetcher.fetch_player_injury(player_name)
        
        # 3. Generate AI Insights if stats available
        insights = None
        if logs and logs.get('data'):
             # Wrap data for insights generator
             confluence_data = {
                 'player_name': player_name,
                 'projections': [{'player_name': player_name, 'projections': self._calc_simple_proj(logs.get('data'))}],
                 'game': 'Tonight'
             }
             insights = self.insights_generator.generate_insights(confluence_data)
             
        return {
            'player_id': player_id,
            'player_name': player_name,
            'stats': stats,
            'game_logs': logs,
            'injury': injury,
            'insights': insights,
            'timestamp': os.times() # Just placeholder
        }
    
    def _calc_simple_proj(self, logs: List[Dict]) -> Dict:
        """Helper to calculate simple projections from logs for AI context"""
        if not logs: return {}
        last_5 = logs[:5]
        return {
            'pts': {'projected': sum(g.get('pts', 0) for g in last_5) / 5, 'grade': 'B'},
            'reb': {'projected': sum(g.get('reb', 0) for g in last_5) / 5, 'grade': 'B'},
            'ast': {'projected': sum(g.get('ast', 0) for g in last_5) / 5, 'grade': 'B'}
        }
