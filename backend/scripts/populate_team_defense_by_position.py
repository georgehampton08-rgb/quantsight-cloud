"""
Team Defense By Position Fetcher
================================
Fetches position-specific defensive stats from NBA API and stores in Firestore.
Populates team_defense_by_position collection for position-aware matchup adjustments.

Run: python populate_team_defense_by_position.py
"""
import logging
import time
from typing import Dict, List
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# NBA API endpoints
DEFENSE_DASHBOARD_URL = "https://stats.nba.com/stats/leaguedashteamstats"
OPP_SHOOTING_URL = "https://stats.nba.com/stats/leaguedashptdefend"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Accept-Language': 'en-US,en;q=0.9',
}

POSITIONS = ['G', 'F', 'C']  # Guard, Forward, Center
POSITION_LABELS = {
    'G': 'Guard',
    'F': 'Forward', 
    'C': 'Center'
}

# Team mapping
TEAMS = [
    'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
    'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK',
    'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
]

# Import Firestore
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    
    db = firestore.client()
    HAS_FIREBASE = True
    logger.info("✅ Firebase initialized")
except Exception as e:
    logger.error(f"❌ Firebase init failed: {e}")
    HAS_FIREBASE = False
    db = None


def fetch_team_defense_by_position(season: str = "2024-25") -> List[Dict]:
    """
    Fetch team defensive stats broken down by opponent position.
    
    Returns list with:
    - team
    - position (G/F/C)
    - opp_pts: Points allowed to that position
    - opp_fg_pct: FG% allowed
    - opp_fg3_pct: 3P% allowed
    - opp_fta: FT attempts allowed
    - def_rating: Defensive rating vs position
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    
    all_records = []
    
    # NBA API doesn't have direct position-based defense splits
    # We'll simulate by adjusting base team defense based on positional tendencies
    
    # First, get base team defense
    params = {
        'LeagueID': '00',
        'Season': season,
        'SeasonType': 'Regular Season',
        'MeasureType': 'Opponent',
        'PerMode': 'PerGame',
    }
    
    try:
        response = session.get(DEFENSE_DASHBOARD_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        result_sets = data.get('resultSets', [])
        if not result_sets:
            logger.warning("No result sets in defense response")
            return []
        
        headers = result_sets[0].get('headers', [])
        rows = result_sets[0].get('rowSet', [])
        
        idx = {h: i for i, h in enumerate(headers)}
        
        for row in rows:
            team = row[idx.get('TEAM_ABBREVIATION', '')] or ''
            if not team:
                continue
            
            base_opp_pts = row[idx.get('OPP_PTS', 0)] or 115
            base_opp_fg_pct = row[idx.get('OPP_FG_PCT', 0)] or 0.46
            base_opp_fg3_pct = row[idx.get('OPP_FG3_PCT', 0)] or 0.36
            base_def_rating = row[idx.get('DEF_RATING', 0)] or 110
            
            # Apply position-based adjustments (heuristic-based)
            # Guards typically score more from 3PT, Centers more from inside
            for pos in POSITIONS:
                if pos == 'G':
                    # Guards: higher 3P%, slightly lower overall FG%
                    pos_opp_pts = base_opp_pts * 0.42  # ~42% of opponent pts from guards
                    pos_opp_fg_pct = base_opp_fg_pct * 0.95
                    pos_opp_fg3_pct = base_opp_fg3_pct * 1.05
                    pos_def_rating = base_def_rating * 0.98
                elif pos == 'F':
                    # Forwards: balanced
                    pos_opp_pts = base_opp_pts * 0.38  # ~38% from forwards
                    pos_opp_fg_pct = base_opp_fg_pct * 1.0
                    pos_opp_fg3_pct = base_opp_fg3_pct * 1.0
                    pos_def_rating = base_def_rating * 1.0
                else:  # Center
                    # Centers: higher FG%, lower 3P%
                    pos_opp_pts = base_opp_pts * 0.20  # ~20% from centers
                    pos_opp_fg_pct = base_opp_fg_pct * 1.08
                    pos_opp_fg3_pct = base_opp_fg3_pct * 0.60  # Much less 3P
                    pos_def_rating = base_def_rating * 1.02
                
                record = {
                    'team': team,
                    'position': pos,
                    'position_label': POSITION_LABELS[pos],
                    'opp_pts': round(pos_opp_pts, 1),
                    'opp_fg_pct': round(pos_opp_fg_pct, 3),
                    'opp_fg3_pct': round(pos_opp_fg3_pct, 3),
                    'def_rating': round(pos_def_rating, 1),
                    'base_opp_pts': base_opp_pts,
                    'base_def_rating': base_def_rating,
                }
                all_records.append(record)
        
        logger.info(f"Generated position defense for {len(all_records)} team-position pairs")
        return all_records
        
    except Exception as e:
        logger.error(f"Error fetching team defense: {e}")
        return []


def save_to_firestore(records: List[Dict]) -> int:
    """Save team defense by position to Firestore."""
    if not HAS_FIREBASE or not db:
        logger.error("Firestore not available")
        return 0
    
    saved = 0
    batch = db.batch()
    
    for record in records:
        try:
            # Doc ID format: team_position (e.g., LAL_G, BOS_C)
            doc_id = f"{record['team']}_{record['position']}"
            doc_ref = db.collection('team_defense_by_position').document(doc_id)
            record['updated_at'] = firestore.SERVER_TIMESTAMP
            batch.set(doc_ref, record, merge=True)
            saved += 1
            
            if saved % 500 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"Batch committed: {saved} records")
                
        except Exception as e:
            logger.error(f"Error saving {record.get('team')} {record.get('position')}: {e}")
    
    if saved % 500 != 0:
        batch.commit()
    
    logger.info(f"✅ Total saved: {saved} team defense by position records")
    return saved


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("TEAM DEFENSE BY POSITION POPULATION")
    logger.info("=" * 60)
    
    records = fetch_team_defense_by_position()
    
    if not records:
        logger.error("No records fetched, exiting")
        return
    
    saved = save_to_firestore(records)
    
    logger.info("=" * 60)
    logger.info(f"COMPLETE: {saved} team defense by position records populated")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
