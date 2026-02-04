"""
Gemini-Powered Injury Fetcher (v2 - New SDK)
===========================================
FREE, reliable injury data using Gemini API with search grounding.
"""
import os
import logging
import json
from typing import Dict, List
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiInjuryFetcher:
    """
    FREE injury fetcher using NEW Google GenAI SDK with search grounding.
    """
    
    # Use a model that exists in the current environment
    DEFAULT_MODEL = 'gemini-2.5-flash-lite'
    
    def __init__(self, api_key: str = None):
        # Get API key from environment or parameter
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        
        if not self.api_key:
             # Look for .env as fallback
             from dotenv import load_dotenv
             load_dotenv()
             self.api_key = os.getenv('GEMINI_API_KEY')
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY required")
        
        # Configure Gemini Client
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = os.getenv('GEMINI_MODEL', self.DEFAULT_MODEL)
        
        # Verify model exists, fallback if needed
        # (Skip listing for performance in prod, but using flash-lite for safety)
        if '2.0-flash-exp' in self.model_id:
             self.model_id = 'gemini-2.5-flash-lite' # 2.0-flash-exp was 404ing
        
        logger.info(f"GeminiInjuryFetcher initialized with model: {self.model_id}")
    
    def fetch_player_injury(self, player_name: str) -> Dict:
        """Get injury status for a specific player using AI search."""
        try:
            prompt = f"""
Search the web for current NBA injury status for {player_name} as of late January 2026.

Return ONLY a JSON object with this exact structure:
{{
    "player_name": "{player_name}",
    "status": "OUT" or "QUESTIONABLE" or "PROBABLE" or "AVAILABLE",
    "injury_description": "brief injury description or empty string",
    "source": "source name"
}}

If no injury found, return status as "AVAILABLE" with empty injury_description.
"""
            
            # Use search grounding configuration
            search_tool = types.Tool(google_search=types.GoogleSearch())
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[search_tool]
                )
            )
            
            result_text = response.text.strip()
            
            # Parse JSON from response
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            data = json.loads(result_text)
            
            # Calculate performance factor
            status = data.get('status', 'AVAILABLE').upper()
            if status in ('OUT', 'DOUBTFUL'):
                performance_factor = 0.0
                is_available = False
            elif status in ('QUESTIONABLE', 'GTD'):
                performance_factor = 0.85
                is_available = True
            elif status == 'PROBABLE':
                performance_factor = 0.95
                is_available = True
            else:
                performance_factor = 1.0
                is_available = True
            
            return {
                'player_name': data.get('player_name', player_name),
                'status': status,
                'injury_desc': data.get('injury_description', ''),
                'is_available': is_available,
                'performance_factor': performance_factor,
                'source': data.get('source', 'gemini_search'),
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Gemini fetch failed for {player_name}: {e}")
            return {
                'player_name': player_name, 'status': 'AVAILABLE', 'injury_desc': '',
                'is_available': True, 'performance_factor': 1.0, 'source': 'fallback',
                'checked_at': datetime.now().isoformat()
            }

    def fetch_team_injuries(self, team_name: str) -> List[Dict]:
        """Get all injuries for a team using AI search."""
        try:
            prompt = f"""
Search the web for ALL current NBA injuries for the {team_name} as of January 2026.

Return ONLY a JSON array listing ALL injured players with this exact structure:
[
    {{
        "player_name": "Player Name",
        "status": "OUT" or "QUESTIONABLE" or "PROBABLE",
        "injury_description": "brief injury description"
    }}
]

If no injuries found, return an empty array: []
"""
            search_tool = types.Tool(google_search=types.GoogleSearch())
            
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[search_tool]
                )
            )
            
            result_text = response.text.strip()
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            injuries_data = json.loads(result_text)
            
            injuries = []
            for inj in injuries_data:
                status = inj.get('status', 'AVAILABLE').upper()
                if status in ('OUT', 'DOUBTFUL'):
                    performance_factor = 0.0
                    is_available = False
                elif status in ('QUESTIONABLE', 'GTD'):
                    performance_factor = 0.85
                    is_available = True
                elif status == 'PROBABLE':
                    performance_factor = 0.95
                    is_available = True
                else:
                    continue
                
                injuries.append({
                    'player_name': inj.get('player_name', ''),
                    'status': status,
                    'injury_desc': inj.get('injury_description', ''),
                    'is_available': is_available,
                    'performance_factor': performance_factor,
                    'source': 'gemini_search',
                    'checked_at': datetime.now().isoformat()
                })
            
            return injuries
        except Exception as e:
            logger.error(f"Team injury fetch failed for {team_name}: {e}")
            return []
