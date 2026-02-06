"""
3PM H2H Data Fetcher
====================
Fetches and populates 3-point made (3PM) H2H historical data.
Updates existing H2H records with avg_3pm field from game logs.

Run: python populate_3pm_h2h.py
"""
import logging
from datetime import datetime
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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


def calculate_3pm_from_game_logs() -> Dict[str, Dict]:
    """
    Calculate average 3PM from player_h2h_games collection.
    Groups by player_id + opponent and calculates mean fg3m.
    
    Returns: Dict mapping doc_id to 3pm average
    """
    if not HAS_FIREBASE or not db:
        return {}
    
    # Aggregate 3PM data from game logs
    aggregates = {}
    
    try:
        # Stream all H2H game records
        docs = db.collection('player_h2h_games').limit(5000).stream()
        
        for doc in docs:
            data = doc.to_dict()
            player_id = data.get('player_id')
            opponent = data.get('opponent')
            fg3m = data.get('fg3m', 0) or 0
            
            if not player_id or not opponent:
                continue
            
            key = f"{player_id}_{opponent}"
            
            if key not in aggregates:
                aggregates[key] = {
                    'player_id': player_id,
                    'opponent': opponent,
                    'total_3pm': 0,
                    'games': 0
                }
            
            aggregates[key]['total_3pm'] += fg3m
            aggregates[key]['games'] += 1
        
        # Calculate averages
        for key, agg in aggregates.items():
            if agg['games'] > 0:
                agg['avg_3pm'] = round(agg['total_3pm'] / agg['games'], 1)
            else:
                agg['avg_3pm'] = 0
        
        logger.info(f"Calculated 3PM averages for {len(aggregates)} player-opponent pairs")
        return aggregates
        
    except Exception as e:
        logger.error(f"Error calculating 3PM aggregates: {e}")
        return {}


def update_h2h_with_3pm(aggregates: Dict[str, Dict]) -> int:
    """Update player_h2h collection with 3PM averages."""
    if not HAS_FIREBASE or not db:
        return 0
    
    updated = 0
    batch = db.batch()
    
    for doc_id, agg in aggregates.items():
        try:
            doc_ref = db.collection('player_h2h').document(doc_id)
            
            # Update with 3PM data
            batch.set(doc_ref, {
                '3pm': agg['avg_3pm'],
                'avg_3pm': agg['avg_3pm'],
                '3pm_updated_at': firestore.SERVER_TIMESTAMP,
            }, merge=True)
            
            updated += 1
            
            if updated % 500 == 0:
                batch.commit()
                batch = db.batch()
                logger.info(f"Batch committed: {updated} records")
                
        except Exception as e:
            logger.error(f"Error updating 3PM for {doc_id}: {e}")
    
    if updated % 500 != 0:
        batch.commit()
    
    logger.info(f"✅ Updated 3PM for {updated} H2H records")
    return updated


def fetch_3pm_from_nba_api() -> List[Dict]:
    """
    Fetch 3PM stats from NBA API for players without H2H game data.
    Uses player career stats as fallback.
    """
    import requests
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
    }
    
    url = "https://stats.nba.com/stats/leaguedashplayerstats"
    params = {
        'Season': '2024-25',
        'SeasonType': 'Regular Season',
        'PerMode': 'PerGame',
        'LeagueID': '00',
    }
    
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        result_sets = data.get('resultSets', [])
        if not result_sets:
            return []
        
        headers = result_sets[0].get('headers', [])
        rows = result_sets[0].get('rowSet', [])
        
        idx = {h: i for i, h in enumerate(headers)}
        
        players = []
        for row in rows:
            players.append({
                'player_id': str(row[idx.get('PLAYER_ID', 0)]),
                'player_name': row[idx.get('PLAYER_NAME', '')] or '',
                'team': row[idx.get('TEAM_ABBREVIATION', '')] or '',
                'avg_3pm': row[idx.get('FG3M', 0)] or 0,
                'avg_3pa': row[idx.get('FG3A', 0)] or 0,
                'fg3_pct': row[idx.get('FG3_PCT', 0)] or 0,
            })
        
        logger.info(f"Fetched 3PM stats for {len(players)} players from NBA API")
        return players
        
    except Exception as e:
        logger.error(f"Error fetching 3PM from NBA API: {e}")
        return []


def save_player_3pm_baseline(players: List[Dict]) -> int:
    """Save baseline 3PM stats to player_stats collection."""
    if not HAS_FIREBASE or not db:
        return 0
    
    saved = 0
    batch = db.batch()
    
    for player in players:
        try:
            doc_ref = db.collection('player_stats').document(player['player_id'])
            batch.set(doc_ref, {
                'avg_fg3m': player['avg_3pm'],
                'avg_fg3a': player['avg_3pa'],
                'fg3_pct': player['fg3_pct'],
                '3pm_updated_at': firestore.SERVER_TIMESTAMP,
            }, merge=True)
            
            saved += 1
            
            if saved % 500 == 0:
                batch.commit()
                batch = db.batch()
                
        except Exception as e:
            logger.error(f"Error saving 3PM for {player.get('player_name')}: {e}")
    
    if saved % 500 != 0:
        batch.commit()
    
    logger.info(f"✅ Saved baseline 3PM for {saved} players")
    return saved


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("3PM H2H DATA POPULATION")
    logger.info("=" * 60)
    
    # Step 1: Calculate 3PM from existing H2H game logs
    aggregates = calculate_3pm_from_game_logs()
    
    # Step 2: Update H2H records with 3PM averages
    updated = update_h2h_with_3pm(aggregates)
    
    # Step 3: Fetch baseline 3PM from NBA API
    players = fetch_3pm_from_nba_api()
    
    # Step 4: Save baseline 3PM stats
    saved = save_player_3pm_baseline(players)
    
    logger.info("=" * 60)
    logger.info(f"COMPLETE: {updated} H2H records updated, {saved} player baselines saved")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
