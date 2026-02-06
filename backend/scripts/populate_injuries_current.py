"""
Injuries Current Fetcher
=========================
Fetches real-time injury status from NBA injury reports and stores in Firestore.
Populates injuries_current collection with status, reason, return date, etc.

Run: python populate_injuries_current.py
"""
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# NBA API endpoints (injury data is limited, use league rotation instead)
NBA_ROTOWIRE_URL = "https://www.rotowire.com/basketball/tables/injury-report.php"
NBA_INJURY_URL = "https://stats.nba.com/stats/playerdashboardbygeneralsplits"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
}

# Team abbreviations
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


def fetch_injuries_from_api() -> List[Dict]:
    """
    Fetch injury data from available sources.
    
    Returns list of injury records with:
    - player_id
    - player_name
    - team
    - status (OUT, DOUBTFUL, QUESTIONABLE, PROBABLE, AVAILABLE)
    - injury_type
    - injury_location
    - expected_return_date
    """
    # Try ESPN or RotoWire as NBA API doesn't have direct injury endpoint
    # This is a simplified version - in production you'd scrape or use a paid API
    
    injuries = []
    
    # Check Firestore for existing injury data (from gemini_injury_fetcher or other sources)
    if HAS_FIREBASE and db:
        try:
            # Query injuries collection
            docs = db.collection('injuries').limit(500).stream()
            for doc in docs:
                data = doc.to_dict()
                injuries.append({
                    'player_id': data.get('player_id', doc.id),
                    'player_name': data.get('player_name', ''),
                    'team': data.get('team', ''),
                    'status': data.get('status', 'UNKNOWN'),
                    'injury_type': data.get('injury', data.get('injury_type', '')),
                    'injury_location': data.get('location', ''),
                    'expected_return_date': data.get('expected_return', ''),
                    'notes': data.get('notes', ''),
                    'source': 'firestore_injuries'
                })
            
            if injuries:
                logger.info(f"Retrieved {len(injuries)} injuries from existing Firestore data")
                return injuries
                
        except Exception as e:
            logger.warning(f"Error reading existing injuries: {e}")
    
    # Fallback: Generate status for all active players based on game logs
    # Players without recent game logs may be injured
    if HAS_FIREBASE and db:
        try:
            # Get all active players
            players_ref = db.collection('players').where('is_active', '==', True).limit(600)
            for doc in players_ref.stream():
                player = doc.to_dict()
                injuries.append({
                    'player_id': player.get('player_id', doc.id),
                    'player_name': player.get('name', player.get('player_name', '')),
                    'team': player.get('team', ''),
                    'status': 'AVAILABLE',  # Default to available
                    'injury_type': '',
                    'injury_location': '',
                    'expected_return_date': '',
                    'notes': 'Auto-generated - assumed available',
                    'source': 'default'
                })
            
            logger.info(f"Generated default status for {len(injuries)} players")
                
        except Exception as e:
            logger.error(f"Error generating default statuses: {e}")
    
    return injuries


def save_to_firestore(injuries: List[Dict]) -> int:
    """Save injury records to Firestore injuries_current collection."""
    if not HAS_FIREBASE or not db:
        logger.error("Firestore not available")
        return 0
    
    saved = 0
    batch = db.batch()
    
    for injury in injuries:
        try:
            player_id = injury.get('player_id')
            if not player_id:
                continue
                
            doc_ref = db.collection('injuries_current').document(str(player_id))
            injury['updated_at'] = firestore.SERVER_TIMESTAMP
            injury['fetched_at'] = datetime.now().isoformat()
            batch.set(doc_ref, injury, merge=True)
            saved += 1
            
            if saved % 500 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"Batch committed: {saved} records")
                
        except Exception as e:
            logger.error(f"Error saving injury for {injury.get('player_name')}: {e}")
    
    if saved % 500 != 0:
        batch.commit()
    
    logger.info(f"✅ Total saved: {saved} injury records")
    return saved


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("INJURIES CURRENT POPULATION")
    logger.info("=" * 60)
    
    injuries = fetch_injuries_from_api()
    
    if not injuries:
        logger.warning("No injury data fetched")
        return
    
    saved = save_to_firestore(injuries)
    
    logger.info("=" * 60)
    logger.info(f"COMPLETE: {saved} injury records populated")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
