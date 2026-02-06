"""
Team Defense by Position Script (Standalone)
============================================
Fetches team defensive stats and infers position-based adjustments.

Usage:
  python populate_team_defense_v2.py
"""
import logging

from nba_rate_limiter import RateLimiter, make_nba_request, create_session, NBA_BASE_URL

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSITIONS = ['G', 'F', 'C']

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


def fetch_team_defense() -> int:
    """Fetch team defense stats and create position breakdowns."""
    session = create_session()
    rate_limiter = RateLimiter(base_delay=1.5)
    
    logger.info("Fetching team defense stats...")
    
    data = make_nba_request(session, f"{NBA_BASE_URL}/leaguedashteamstats", {
        'LeagueID': '00',
        'Season': '2024-25',
        'SeasonType': 'Regular Season',
        'MeasureType': 'Opponent',
        'PerMode': 'PerGame',
    }, rate_limiter)
    
    if not data:
        logger.error("Failed to fetch team defense")
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
            team = row[idx.get('TEAM_ABBREVIATION', '')] or ''
            if not team:
                continue
            
            base_pts = row[idx.get('OPP_PTS', 115)] or 115
            base_fg_pct = row[idx.get('OPP_FG_PCT', 0.46)] or 0.46
            base_fg3_pct = row[idx.get('OPP_FG3_PCT', 0.36)] or 0.36
            base_def_rtg = row[idx.get('DEF_RATING', 110)] or 110
            
            # Save base team defense
            team_doc = {
                'team': team,
                'opp_pts': base_pts,
                'opp_fg_pct': base_fg_pct,
                'opp_fg3_pct': base_fg3_pct,
                'def_rating': base_def_rtg,
                'updated_at': firestore.SERVER_TIMESTAMP,
            }
            batch.set(db.collection('team_defense').document(team), team_doc, merge=True)
            saved += 1
            
            # Create position-based adjustments
            for pos in POSITIONS:
                if pos == 'G':
                    pts_mult, fg_mult, fg3_mult = 0.42, 0.95, 1.05
                elif pos == 'F':
                    pts_mult, fg_mult, fg3_mult = 0.38, 1.0, 1.0
                else:  # C
                    pts_mult, fg_mult, fg3_mult = 0.20, 1.08, 0.6
                
                pos_doc = {
                    'team': team,
                    'position': pos,
                    'opp_pts': round(base_pts * pts_mult, 1),
                    'opp_fg_pct': round(base_fg_pct * fg_mult, 3),
                    'opp_fg3_pct': round(base_fg3_pct * fg3_mult, 3),
                    'def_rating': round(base_def_rtg, 1),
                    'updated_at': firestore.SERVER_TIMESTAMP,
                }
                doc_id = f"{team}_{pos}"
                batch.set(db.collection('team_defense_by_position').document(doc_id), pos_doc, merge=True)
                saved += 1
        
        batch.commit()
        logger.info(f"✅ Saved {saved} team defense records")
        return saved
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 0


def main():
    logger.info("=" * 60)
    logger.info("TEAM DEFENSE BY POSITION POPULATION")
    logger.info("=" * 60)
    
    saved = fetch_team_defense()
    
    logger.info("=" * 60)
    logger.info(f"COMPLETE: {saved} records")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
