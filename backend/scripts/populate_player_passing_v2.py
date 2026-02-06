"""
Player Passing Stats Script (Standalone)
========================================
Fetches advanced playmaking metrics from NBA API.

Usage:
  python populate_player_passing_v2.py
"""
import logging

from nba_rate_limiter import RateLimiter, make_nba_request, create_session, NBA_BASE_URL

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Firebase
try:
    import firebase_admin
    from firebase_admin import firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    db = firestore.client()
    HAS_FIREBASE = True
except Exception as e:
    logger.warning(f"Firebase not available: {e}")
    HAS_FIREBASE = False
    db = None


def fetch_passing_stats() -> int:
    """Fetch player passing stats from NBA API."""
    session = create_session()
    rate_limiter = RateLimiter(base_delay=1.5)
    
    logger.info("Fetching player passing stats...")
    
    data = make_nba_request(session, f"{NBA_BASE_URL}/leaguedashptstats", {
        'LeagueID': '00',
        'Season': '2024-25',
        'SeasonType': 'Regular Season',
        'PlayerOrTeam': 'Player',
        'PtMeasureType': 'Passing',
        'PerMode': 'PerGame',
    }, rate_limiter)
    
    if not data:
        logger.error("Failed to fetch passing stats")
        return 0
    
    if not HAS_FIREBASE:
        logger.error("Firebase not available")
        return 0
    
    try:
        headers = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        idx = {h: i for i, h in enumerate(headers)}
        
        batch = db.batch()
        saved = 0
        
        for row in rows:
            player_id = str(row[idx.get('PLAYER_ID', 0)])
            
            stats = {
                'player_id': player_id,
                'player_name': row[idx.get('PLAYER_NAME', '')] or '',
                'team': row[idx.get('TEAM_ABBREVIATION', '')] or '',
                'passes_made': row[idx.get('PASSES_MADE', 0)] or 0,
                'passes_received': row[idx.get('PASSES_RECEIVED', 0)] or 0,
                'assists': row[idx.get('AST', 0)] or 0,
                'potential_assists': row[idx.get('POTENTIAL_AST', 0)] or 0,
                'ast_pts_created': row[idx.get('AST_PTS_CREATED', 0)] or 0,
                'secondary_assists': row[idx.get('SECONDARY_AST', 0)] or 0,
                'updated_at': firestore.SERVER_TIMESTAMP,
            }
            
            doc_ref = db.collection('player_passing').document(player_id)
            batch.set(doc_ref, stats, merge=True)
            saved += 1
            
            if saved % 500 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"Committed {saved} records")
        
        if saved % 500 != 0:
            batch.commit()
        
        logger.info(f"✅ Saved passing stats for {saved} players")
        return saved
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 0


def main():
    logger.info("=" * 60)
    logger.info("PLAYER PASSING STATS POPULATION")
    logger.info("=" * 60)
    
    saved = fetch_passing_stats()
    
    logger.info("=" * 60)
    logger.info(f"COMPLETE: {saved} player passing records")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
