"""
Real Injury Data API
====================
Fetches live NBA injury data and serves via API endpoint.
"""
from fastapi import APIRouter
from typing import List, Dict
import requests
import logging
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
router = APIRouter()


def fetch_rotowire_injuries() -> List[Dict]:
    """
    Fetch real injury data from RotoWire.
    Returns list of current NBA injuries.
    """
    try:
        url = "https://www.rotowire.com/basketball/nba-lineups.php"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"RotoWire returned {response.status_code}")
            return []
        
        # Parse HTML for injury data
        soup = BeautifulSoup(response.text, 'html.parser')
        injuries = []
        
        # Look for injury sections (structure varies, this is a simplified example)
        injury_sections = soup.find_all(class_='lineup__inj')
        
        for section in injury_sections[:20]:  # Limit to prevent overload
            try:
                player_name = section.find(class_='lineup__player').text.strip()
                status = section.find(class_='lineup__inj-status').text.strip()
                injury_desc = section.find(class_='lineup__inj-detail').text.strip()
                team = section.get('data-team', 'UNK')
                
                injuries.append({
                    'player_name': player_name,
                    'team': team.upper(),
                    'status': status.upper(),
                    'injury_desc': injury_desc,
                    'source': 'rotowire',
                    'fetched_at': datetime.now().isoformat()
                })
            except Exception as e:
                continue
        
        logger.info(f"✅ Fetched {len(injuries)} injuries from RotoWire")
        return injuries
        
    except Exception as e:
        logger.error(f"Failed to fetch from RotoWire: {e}")
        return []


def fetch_nba_official_injuries() -> List[Dict]:
    """
    Fallback: Try to fetch from NBA.com injury report.
    """
    try:
        # NBA.com injury endpoint (may require API key or return 403)
        url = "https://www.nba.com/stats/injury-report"
        response = requests.get(url, timeout=10)
        
        # This would need proper parsing based on NBA's actual API structure
        # For now, return empty as fallback
        return []
    except:
        return []


@router.get("/injuries/live")
async def get_live_injuries():
    """
    Fetch current NBA injuries from live sources.
    
    Returns:
        List of current injuries with status and descriptions
    """
    injuries = fetch_rotowire_injuries()
    
    if not injuries:
        # Try fallback source
        injuries = fetch_nba_official_injuries()
    
    return {
        "injuries": injuries,
        "count": len(injuries),
        "source": injuries[0]['source'] if injuries else 'none',
        "fetched_at": datetime.now().isoformat()
    }


@router.get("/injuries/team/{team_abbr}")
async def get_team_injuries(team_abbr: str):
    """
    Get injuries for a specific team.
    """
    all_injuries = fetch_rotowire_injuries()
    team_injuries = [inj for inj in all_injuries if inj['team'] == team_abbr.upper()]
    
    return {
        "team": team_abbr.upper(),
        "injuries": team_injuries,
        "count": len(team_injuries),
        "fetched_at": datetime.now().isoformat()
    }


@router.post("/injuries/sync")
async def sync_injuries_to_db():
    """
    Fetch live injuries and sync to database.
    """
    from services.automated_injury_worker import get_injury_worker
    
    # Fetch from web
    injuries = fetch_rotowire_injuries()
    
    if not injuries:
        return {"success": False, "message": "No injuries fetched"}
    
    # Sync to database
    injury_worker = get_injury_worker()
    synced_count = 0
    
    for inj in injuries:
        try:
            injury_worker.mark_injured(
                player_id=inj.get('player_id', '0'),  # Would need player ID lookup
                player_name=inj['player_name'],
                team=inj['team'],
                status=inj['status'],
                injury_desc=inj['injury_desc']
            )
            synced_count += 1
        except Exception as e:
            logger.error(f"Failed to sync {inj['player_name']}: {e}")
    
    return {
        "success": True,
        "injuries_fetched": len(injuries),
        "injuries_synced": synced_count,
        "source": "rotowire"
    }
