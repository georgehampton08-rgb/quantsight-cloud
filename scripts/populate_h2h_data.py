"""
H2H Data Population Script (Standalone)
=======================================
Fetches H2H matchup data from NBA API for specified teams.
Uses smart rate limiting. Run independently or in parallel.

Usage:
  python populate_h2h_data.py                    # All teams
  python populate_h2h_data.py --teams ATL BOS   # Specific teams
  python populate_h2h_data.py --workers 4       # Parallel workers
"""
import argparse
import concurrent.futures
import logging
from datetime import datetime
from typing import Dict, List

from nba_rate_limiter import (
    RateLimiter, make_nba_request, create_session,
    NBA_BASE_URL, TEAM_IDS
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TEAMS = list(TEAM_IDS.keys())

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


def fetch_roster(session, team: str, rate_limiter: RateLimiter) -> List[Dict]:
    """Fetch team roster."""
    team_id = TEAM_IDS.get(team)
    if not team_id:
        return []
    
    data = make_nba_request(session, f"{NBA_BASE_URL}/commonteamroster", {
        'LeagueID': '00', 'Season': '2024-25', 'TeamID': team_id
    }, rate_limiter)
    
    if not data:
        return []
    
    try:
        headers = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        idx = {h: i for i, h in enumerate(headers)}
        return [{'player_id': str(row[idx['PLAYER_ID']]), 'name': row[idx['PLAYER']]} for row in rows]
    except:
        return []


def fetch_player_h2h(session, player_id: str, opponent: str, rate_limiter: RateLimiter) -> Dict:
    """Fetch H2H game logs."""
    opponent_id = TEAM_IDS.get(opponent.upper())
    if not opponent_id:
        return {'games': [], 'aggregates': None}
    
    all_games = []
    for offset in range(3):
        season = f"{2024-offset}-{str(2025-offset)[-2:]}"
        data = make_nba_request(session, f"{NBA_BASE_URL}/playergamelogs", {
            'PlayerID': player_id, 'Season': season,
            'SeasonType': 'Regular Season', 'OpponentTeamID': opponent_id
        }, rate_limiter)
        
        if not data:
            continue
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            idx = {h: i for i, h in enumerate(headers)}
            
            for row in rows:
                all_games.append({
                    'game_date': str(row[idx.get('GAME_DATE', '')])[:10],
                    'pts': row[idx.get('PTS', 0)] or 0,
                    'reb': row[idx.get('REB', 0)] or 0,
                    'ast': row[idx.get('AST', 0)] or 0,
                    'fg3m': row[idx.get('FG3M', 0)] or 0,
                })
        except:
            continue
    
    if all_games:
        n = len(all_games)
        return {
            'games': all_games,
            'aggregates': {
                'games': n,
                'pts': round(sum(g['pts'] for g in all_games) / n, 1),
                'reb': round(sum(g['reb'] for g in all_games) / n, 1),
                'ast': round(sum(g['ast'] for g in all_games) / n, 1),
                '3pm': round(sum(g['fg3m'] for g in all_games) / n, 1),
            }
        }
    return {'games': [], 'aggregates': None}


def save_h2h(player_id: str, opponent: str, h2h_data: Dict) -> bool:
    """Save to Firestore."""
    if not HAS_FIREBASE or not h2h_data.get('aggregates'):
        return False
    
    try:
        doc_id = f"{player_id}_{opponent.upper()}"
        agg = h2h_data['aggregates']
        agg['player_id'] = player_id
        agg['opponent'] = opponent.upper()
        agg['updated_at'] = firestore.SERVER_TIMESTAMP
        db.collection('player_h2h').document(doc_id).set(agg, merge=True)
        return True
    except Exception as e:
        logger.error(f"Save failed: {e}")
        return False


def process_team_pair(team_a: str, team_b: str, worker_id: int) -> int:
    """Process one team pair."""
    session = create_session()
    rate_limiter = RateLimiter(base_delay=1.2)
    saved = 0
    
    roster = fetch_roster(session, team_a, rate_limiter)
    logger.info(f"[W{worker_id}] {team_a} vs {team_b}: {len(roster)} players")
    
    for player in roster[:12]:
        h2h = fetch_player_h2h(session, player['player_id'], team_b, rate_limiter)
        if save_h2h(player['player_id'], team_b, h2h):
            saved += 1
            logger.info(f"[W{worker_id}] {player['name']} vs {team_b}: {h2h['aggregates']['games']} games")
    
    return saved


def main():
    parser = argparse.ArgumentParser(description='H2H Data Population')
    parser.add_argument('--teams', nargs='+', default=TEAMS, help='Teams to process')
    parser.add_argument('--workers', type=int, default=4, help='Parallel workers')
    args = parser.parse_args()
    
    teams = [t.upper() for t in args.teams if t.upper() in TEAM_IDS]
    
    # Generate pairs
    pairs = [(a, b) for i, a in enumerate(teams) for b in teams[i+1:]]
    logger.info(f"Processing {len(pairs)} team pairs with {args.workers} workers")
    
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_team_pair, a, b, i % args.workers): (a, b) 
                   for i, (a, b) in enumerate(pairs)}
        for f in concurrent.futures.as_completed(futures):
            total += f.result()
    
    logger.info(f"COMPLETE: {total} H2H records saved")


if __name__ == "__main__":
    main()
