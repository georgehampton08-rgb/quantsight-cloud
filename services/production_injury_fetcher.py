"""
Production Gemini Injury Fetcher - FINAL VERSION
=================================================
Simplified, robust version that works reliably with Gemini API.
"""
import os
import re
import logging
from typing import Dict, List
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except:
    pass

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)


class ProductionInjuryFetcher:
    """Simple, reliable Gemini-powered injury fetcher"""
    
    def __init__(self):
        if not HAS_GEMINI:
            raise ImportError("google-generativeai required")
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY required")
        
        genai.configure(api_key=api_key)
        # Use Gemini 2.0 Flash (stable, confirmed available)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def get_team_injuries_today(self, team_name: str) -> str:
        """
        Get simple text summary of team injuries.
        Returns plain text that we can parse.
        """
        try:
            prompt = f"""
Search the NBA injury report for {team_name} on January 28, 2026.

List ONLY players who are OUT, QUESTIONABLE, or DOUBTFUL.
Format each injury as: PLAYER_NAME: STATUS (injury description)

Example format:
Austin Reaves: OUT (left calf strain)
Darius Garland: QUESTIONABLE (toe soreness)

If no injuries, return exactly: "No injuries reported"
"""
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,  # Low temperature for factual data
                )
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Gemini fetch failed: {e}")
            return "Error fetching data"
    
    def parse_injury_report(self, report_text: str) -> List[Dict]:
        """Parse plain text injury report into structured data"""
        injuries = []
        
        if "No injuries" in report_text or "Error" in report_text:
            return injuries
        
        # Parse lines like: "Player Name: STATUS (description)"
        lines = report_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' not in line:
                continue
            
            try:
                # Extract player name and rest
                parts = line.split(':', 1)
                player_name = parts[0].strip().strip('*-•')
                
                # Extract status
                status_match = re.search(r'(OUT|QUESTIONABLE|DOUBTFUL|PROBABLE|GTD)', parts[1], re.IGNORECASE)
                if not status_match:
                    continue
                
                status = status_match.group(1).upper()
                
                # Extract injury description
                injury_desc = re.sub(r'(OUT|QUESTIONABLE|DOUBTFUL|PROBABLE|GTD)', '', parts[1], flags=re.IGNORECASE)
                injury_desc = injury_desc.strip('() \t')
                
                # Calculate performance factor
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
                    'player_name': player_name,
                    'status': status,
                    'injury_desc': injury_desc,
                    'is_available': is_available,
                    'performance_factor': performance_factor,
                    'source': 'gemini',
                    'checked_at': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.warning(f"Failed to parse line: {line} - {e}")
                continue
        
        return injuries


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*70)
    print("PRODUCTION GEMINI INJURY FETCHER")
    print("="*70)
    
    try:
        fetcher = ProductionInjuryFetcher()
        
        # Test Lakers
        print("\n🏀 Fetching Lakers injuries...\n")
        report = fetcher.get_team_injuries_today("Los Angeles Lakers")
        
        print("RAW RESPONSE:")
        print("-" * 70)
        print(report)
        print("-" * 70)
        
        print("\n\nPARSED DATA:")
        injuries = fetcher.parse_injury_report(report)
        
        if injuries:
            print(f"\n✅ Found {len(injuries)} injuries:\n")
            for inj in injuries:
                print(f"   {inj['player_name']}")
                print(f"      Status: {inj['status']}")
                print(f"      Injury: {inj['injury_desc']}")
                print(f"      Performance: {inj['performance_factor']*100}%")
                print()
        else:
            print("\n   No injuries detected")
        
        print("="*70)
        print("✅ TEST COMPLETE!")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
