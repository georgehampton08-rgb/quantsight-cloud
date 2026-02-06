"""
Player Passing Stats Fetcher
===============================
Fetches advanced playmaking metrics from NBA API and stores in Firestore.
Populates player_passing collection with assist metrics, potential assists, touches, etc.

Run: python populate_player_passing.py
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# NBA API endpoints
PLAYER_TRACKING_URL = "https://stats.nba.com/stats/leaguedashptstats"
PLAYER_PASSING_URL = "https://stats.nba.com/stats/leaguedashptpass"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Import Firestore
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    # Initialize Firebase if not already
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    
    db = firestore.client()
    HAS_FIREBASE = True
    logger.info("✅ Firebase initialized")
except Exception as e:
    logger.error(f"❌ Firebase init failed: {e}")
    HAS_FIREBASE = False
    db = None


def fetch_player_passing_stats(season: str = "2024-25") -> List[Dict]:
    """
    Fetch player passing stats from NBA API.
    
    Returns list of player passing records with:
    - potential_assists
    - assist_points_created
    - passes_made
    - passes_received
    - secondary_assists
    - adjusted_assists
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    
    params = {
        'LeagueID': '00',
        'Season': season,
        'SeasonType': 'Regular Season',
        'PlayerOrTeam': 'Player',
        'PtMeasureType': 'Passing',
        'PerMode': 'PerGame',
    }
    
    try:
        response = session.get(PLAYER_PASSING_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        result_sets = data.get('resultSets', [])
        if not result_sets:
            logger.warning("No result sets in response")
            return []
        
        headers = result_sets[0].get('headers', [])
        rows = result_sets[0].get('rowSet', [])
        
        idx = {h: i for i, h in enumerate(headers)}
        
        players = []
        for row in rows:
            player = {
                'player_id': str(row[idx.get('PLAYER_ID', 0)]),
                'player_name': row[idx.get('PLAYER_NAME', '')] or '',
                'team': row[idx.get('TEAM_ABBREVIATION', '')] or '',
                'games': row[idx.get('GP', 0)] or 0,
                'minutes': row[idx.get('MIN', 0)] or 0,
                # Passing metrics
                'passes_made': row[idx.get('PASSES_MADE', 0)] or 0,
                'passes_received': row[idx.get('PASSES_RECEIVED', 0)] or 0,
                'assists': row[idx.get('AST', 0)] or 0,
                'potential_assists': row[idx.get('POTENTIAL_AST', 0)] or 0,
                'ast_pts_created': row[idx.get('AST_PTS_CREATED', 0)] or 0,
                'secondary_assists': row[idx.get('SECONDARY_AST', 0)] or 0,
                'ft_assists': row[idx.get('FT_AST', 0)] or 0,
                'ast_adj': row[idx.get('AST_ADJ', 0)] or 0,
                'ast_to_pass_pct': row[idx.get('AST_TO_PASS_PCT', 0)] or 0,
                'ast_to_pass_pct_adj': row[idx.get('AST_TO_PASS_PCT_ADJ', 0)] or 0,
            }
            players.append(player)
        
        logger.info(f"Fetched passing stats for {len(players)} players")
        return players
        
    except Exception as e:
        logger.error(f"Error fetching passing stats: {e}")
        return []


def save_to_firestore(players: List[Dict]) -> int:
    """Save player passing stats to Firestore."""
    if not HAS_FIREBASE or not db:
        logger.error("Firestore not available")
        return 0
    
    saved = 0
    batch = db.batch()
    
    for i, player in enumerate(players):
        try:
            doc_ref = db.collection('player_passing').document(player['player_id'])
            player['updated_at'] = firestore.SERVER_TIMESTAMP
            batch.set(doc_ref, player, merge=True)
            saved += 1
            
            # Commit every 500 docs (Firestore limit)
            if saved % 500 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"Batch committed: {saved} records")
                
        except Exception as e:
            logger.error(f"Error saving player {player.get('player_name')}: {e}")
    
    # Final commit
    if saved % 500 != 0:
        batch.commit()
    
    logger.info(f"✅ Total saved: {saved} player passing records")
    return saved


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("PLAYER PASSING STATS POPULATION")
    logger.info("=" * 60)
    
    # Fetch stats
    players = fetch_player_passing_stats()
    
    if not players:
        logger.error("No players fetched, exiting")
        return
    
    # Save to Firestore
    saved = save_to_firestore(players)
    
    logger.info("=" * 60)
    logger.info(f"COMPLETE: {saved} player passing records populated")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
