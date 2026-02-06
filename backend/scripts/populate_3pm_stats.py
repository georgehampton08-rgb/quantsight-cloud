"""
3PM Stats Population Script (Standalone)
========================================
Fetches 3-point made baseline stats and H2H 3PM data.
Uses smart rate limiting.

Usage:
  python populate_3pm_stats.py
"""
import logging
from datetime import datetime

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


def fetch_player_3pm_stats() -> int:
    """Fetch and save 3PM baseline stats for all players."""
    session = create_session()
    rate_limiter = RateLimiter(base_delay=1.5)
    
    logger.info("Fetching league-wide 3PM stats...")
    
    data = make_nba_request(session, f"{NBA_BASE_URL}/leaguedashplayerstats", {
        'Season': '2024-25',
        'SeasonType': 'Regular Season',
        'PerMode': 'PerGame',
        'LeagueID': '00',
    }, rate_limiter)
    
    if not data:
        logger.error("Failed to fetch 3PM stats")
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
                'avg_fg3m': row[idx.get('FG3M', 0)] or 0,
                'avg_fg3a': row[idx.get('FG3A', 0)] or 0,
                'fg3_pct': row[idx.get('FG3_PCT', 0)] or 0,
                'avg_pts': row[idx.get('PTS', 0)] or 0,
                'avg_reb': row[idx.get('REB', 0)] or 0,
                'avg_ast': row[idx.get('AST', 0)] or 0,
                'updated_at': firestore.SERVER_TIMESTAMP,
            }
            
            doc_ref = db.collection('player_stats').document(player_id)
            batch.set(doc_ref, stats, merge=True)
            saved += 1
            
            if saved % 500 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"Committed {saved} records")
        
        if saved % 500 != 0:
            batch.commit()
        
        logger.info(f"✅ Saved 3PM stats for {saved} players")
        return saved
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 0


def update_h2h_with_3pm() -> int:
    """Update existing H2H records with 3PM calculations."""
    if not HAS_FIREBASE:
        return 0
    
    logger.info("Calculating 3PM averages from H2H game logs...")
    
    # Get all H2H game records
    try:
        games_ref = db.collection('player_h2h_games').limit(5000)
        
        aggregates = {}
        for doc in games_ref.stream():
            data = doc.to_dict()
            player_id = data.get('player_id')
            opponent = data.get('opponent')
            fg3m = data.get('fg3m', 0) or 0
            
            if not player_id or not opponent:
                continue
            
            key = f"{player_id}_{opponent}"
            if key not in aggregates:
                aggregates[key] = {'total': 0, 'count': 0}
            
            aggregates[key]['total'] += fg3m
            aggregates[key]['count'] += 1
        
        # Update H2H docs with 3PM
        batch = db.batch()
        updated = 0
        
        for doc_id, agg in aggregates.items():
            if agg['count'] > 0:
                avg_3pm = round(agg['total'] / agg['count'], 1)
                doc_ref = db.collection('player_h2h').document(doc_id)
                batch.set(doc_ref, {'3pm': avg_3pm, 'avg_3pm': avg_3pm}, merge=True)
                updated += 1
                
                if updated % 500 == 0:
                    batch.commit()
                    batch = db.batch()
        
        if updated % 500 != 0:
            batch.commit()
        
        logger.info(f"✅ Updated {updated} H2H records with 3PM")
        return updated
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 0


def main():
    logger.info("=" * 60)
    logger.info("3PM STATS POPULATION")
    logger.info("=" * 60)
    
    # Step 1: Baseline stats
    baseline = fetch_player_3pm_stats()
    
    # Step 2: Update H2H with 3PM
    h2h_updated = update_h2h_with_3pm()
    
    logger.info("=" * 60)
    logger.info(f"COMPLETE: {baseline} baseline, {h2h_updated} H2H updated")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
