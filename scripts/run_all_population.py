"""
Master H2H Data Population Script
================================
Runs all 4 data population tasks in parallel with smart rate limiting.
Fetches H2H matchup data, 3PM stats, player passing, and team defense data.

Run: python run_all_population.py
"""
import asyncio
import concurrent.futures
import logging
import time
import random
from datetime import datetime
from typing import Dict, List, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# NBA API config
NBA_BASE_URL = "https://stats.nba.com/stats"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

# All NBA teams
TEAMS = [
    'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
    'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK',
    'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
]

TEAM_IDS = {
    'ATL': 1610612737, 'BOS': 1610612738, 'CLE': 1610612739, 'NOP': 1610612740,
    'CHI': 1610612741, 'DAL': 1610612742, 'DEN': 1610612743, 'GSW': 1610612744,
    'HOU': 1610612745, 'LAC': 1610612746, 'LAL': 1610612747, 'MIA': 1610612748,
    'MIL': 1610612749, 'MIN': 1610612750, 'BKN': 1610612751, 'NYK': 1610612752,
    'ORL': 1610612753, 'IND': 1610612754, 'PHI': 1610612755, 'PHX': 1610612756,
    'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'OKC': 1610612760,
    'TOR': 1610612761, 'UTA': 1610612762, 'MEM': 1610612763, 'WAS': 1610612764,
    'DET': 1610612765, 'CHA': 1610612766,
}

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


class RateLimiter:
    """Smart rate limiter with exponential backoff."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 30.0):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.current_delay = base_delay
        self.consecutive_failures = 0
        self.last_request_time = 0
    
    def wait(self):
        """Wait before making the next request."""
        now = time.time()
        elapsed = now - self.last_request_time
        
        # Add jitter to avoid thundering herd
        jitter = random.uniform(0.1, 0.5)
        wait_time = max(0, self.current_delay + jitter - elapsed)
        
        if wait_time > 0:
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def success(self):
        """Reset delay after successful request."""
        self.consecutive_failures = 0
        self.current_delay = self.base_delay
    
    def failure(self):
        """Increase delay after failed request."""
        self.consecutive_failures += 1
        self.current_delay = min(
            self.base_delay * (2 ** self.consecutive_failures),
            self.max_delay
        )
        logger.warning(f"Rate limit hit, backing off to {self.current_delay}s")


def make_nba_request(session: requests.Session, url: str, params: dict, 
                     rate_limiter: RateLimiter, max_retries: int = 3) -> Optional[dict]:
    """Make NBA API request with rate limiting and retries."""
    
    for attempt in range(max_retries):
        rate_limiter.wait()
        
        try:
            response = session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                rate_limiter.success()
                return response.json()
            elif response.status_code == 429:
                # Rate limited
                rate_limiter.failure()
                logger.warning(f"Rate limited, attempt {attempt + 1}/{max_retries}")
            else:
                logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
                rate_limiter.failure()
                
        except requests.Timeout:
            logger.warning(f"Request timeout, attempt {attempt + 1}/{max_retries}")
            rate_limiter.failure()
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            rate_limiter.failure()
    
    return None


def fetch_roster(session: requests.Session, team: str, rate_limiter: RateLimiter) -> List[Dict]:
    """Fetch team roster from NBA API."""
    team_id = TEAM_IDS.get(team)
    if not team_id:
        return []
    
    url = f"{NBA_BASE_URL}/commonteamroster"
    params = {
        'LeagueID': '00',
        'Season': '2024-25',
        'TeamID': team_id,
    }
    
    data = make_nba_request(session, url, params, rate_limiter)
    if not data:
        return []
    
    try:
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
                'player_name': row[idx.get('PLAYER', '')] or '',
                'team': team,
            })
        
        return players
    except Exception as e:
        logger.error(f"Parse error for {team} roster: {e}")
        return []


def fetch_player_h2h(session: requests.Session, player_id: str, opponent: str,
                     rate_limiter: RateLimiter, seasons: int = 3) -> Dict:
    """Fetch H2H game logs for a player vs opponent."""
    opponent_id = TEAM_IDS.get(opponent.upper())
    if not opponent_id:
        return {'games': [], 'aggregates': None}
    
    all_games = []
    current_season = 2024
    
    for offset in range(seasons):
        season = current_season - offset
        season_str = f"{season}-{str(season + 1)[-2:]}"
        
        url = f"{NBA_BASE_URL}/playergamelogs"
        params = {
            'PlayerID': player_id,
            'Season': season_str,
            'SeasonType': 'Regular Season',
            'OpponentTeamID': opponent_id,
        }
        
        data = make_nba_request(session, url, params, rate_limiter)
        if not data:
            continue
        
        try:
            result_sets = data.get('resultSets', [])
            if not result_sets:
                continue
            
            headers = result_sets[0].get('headers', [])
            rows = result_sets[0].get('rowSet', [])
            idx = {h: i for i, h in enumerate(headers)}
            
            for row in rows:
                game = {
                    'game_date': str(row[idx.get('GAME_DATE', '')])[:10],
                    'game_id': str(row[idx.get('GAME_ID', '')]),
                    'pts': row[idx.get('PTS', 0)] or 0,
                    'reb': row[idx.get('REB', 0)] or 0,
                    'ast': row[idx.get('AST', 0)] or 0,
                    'fg3m': row[idx.get('FG3M', 0)] or 0,
                    'fg3a': row[idx.get('FG3A', 0)] or 0,
                    'fgm': row[idx.get('FGM', 0)] or 0,
                    'fga': row[idx.get('FGA', 0)] or 0,
                    'min': int(row[idx.get('MIN', 0)] or 0),
                    'result': row[idx.get('WL', '')] or '',
                }
                all_games.append(game)
                
        except Exception as e:
            logger.error(f"Parse error for player {player_id}: {e}")
    
    # Calculate aggregates
    if all_games:
        aggregates = {
            'games': len(all_games),
            'pts': round(sum(g['pts'] for g in all_games) / len(all_games), 1),
            'reb': round(sum(g['reb'] for g in all_games) / len(all_games), 1),
            'ast': round(sum(g['ast'] for g in all_games) / len(all_games), 1),
            '3pm': round(sum(g['fg3m'] for g in all_games) / len(all_games), 1),
        }
    else:
        aggregates = None
    
    return {'games': all_games, 'aggregates': aggregates}


def save_h2h_to_firestore(player_id: str, opponent: str, h2h_data: Dict) -> bool:
    """Save H2H data to Firestore."""
    if not HAS_FIREBASE or not db:
        return False
    
    try:
        doc_id = f"{player_id}_{opponent.upper()}"
        
        # Save aggregates
        if h2h_data.get('aggregates'):
            agg = h2h_data['aggregates']
            agg['player_id'] = player_id
            agg['opponent'] = opponent.upper()
            agg['updated_at'] = firestore.SERVER_TIMESTAMP
            
            db.collection('player_h2h').document(doc_id).set(agg, merge=True)
        
        # Save individual games
        games = h2h_data.get('games', [])
        if games:
            batch = db.batch()
            for game in games:
                game_doc_id = f"{player_id}_{opponent.upper()}_{game['game_date']}"
                game['player_id'] = player_id
                game['opponent'] = opponent.upper()
                game['updated_at'] = firestore.SERVER_TIMESTAMP
                doc_ref = db.collection('player_h2h_games').document(game_doc_id)
                batch.set(doc_ref, game, merge=True)
            batch.commit()
        
        return True
    except Exception as e:
        logger.error(f"Firestore save failed for {player_id} vs {opponent}: {e}")
        return False


def process_team_pair(team_a: str, team_b: str, worker_id: int) -> Dict:
    """Process H2H data for a team pair (assigned to one worker)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    rate_limiter = RateLimiter(base_delay=1.2, max_delay=30.0)
    
    results = {
        'team_a': team_a,
        'team_b': team_b,
        'worker_id': worker_id,
        'players_processed': 0,
        'h2h_records_saved': 0,
        'errors': []
    }
    
    logger.info(f"[Worker {worker_id}] Processing {team_a} vs {team_b}")
    
    # Get roster for team_a
    roster = fetch_roster(session, team_a, rate_limiter)
    logger.info(f"[Worker {worker_id}] Found {len(roster)} players for {team_a}")
    
    # Fetch H2H for each player vs team_b
    for player in roster[:12]:  # Top 12 players
        player_id = player['player_id']
        player_name = player['player_name']
        
        try:
            h2h_data = fetch_player_h2h(session, player_id, team_b, rate_limiter)
            
            if h2h_data.get('aggregates'):
                if save_h2h_to_firestore(player_id, team_b, h2h_data):
                    results['h2h_records_saved'] += 1
                    logger.info(f"[Worker {worker_id}] Saved H2H: {player_name} vs {team_b} ({h2h_data['aggregates']['games']} games)")
            
            results['players_processed'] += 1
            
        except Exception as e:
            results['errors'].append(f"{player_name}: {str(e)}")
    
    logger.info(f"[Worker {worker_id}] Completed {team_a} vs {team_b}: {results['h2h_records_saved']} records")
    return results


def run_parallel_population(max_workers: int = 4):
    """Run H2H population across all team matchups using parallel workers."""
    logger.info("=" * 70)
    logger.info("PARALLEL H2H DATA POPULATION")
    logger.info(f"Workers: {max_workers}")
    logger.info("=" * 70)
    
    # Generate all unique team pairs
    team_pairs = []
    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i+1:]:  # Avoid duplicates
            team_pairs.append((team_a, team_b))
    
    logger.info(f"Total team pairs to process: {len(team_pairs)}")
    
    all_results = []
    total_saved = 0
    total_players = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        
        for idx, (team_a, team_b) in enumerate(team_pairs):
            worker_id = idx % max_workers
            future = executor.submit(process_team_pair, team_a, team_b, worker_id)
            futures[future] = (team_a, team_b)
        
        for future in concurrent.futures.as_completed(futures):
            team_a, team_b = futures[future]
            try:
                result = future.result()
                all_results.append(result)
                total_saved += result['h2h_records_saved']
                total_players += result['players_processed']
                
                # Progress update every 10 pairs
                if len(all_results) % 10 == 0:
                    logger.info(f"Progress: {len(all_results)}/{len(team_pairs)} pairs, {total_saved} records saved")
                    
            except Exception as e:
                logger.error(f"Worker failed for {team_a} vs {team_b}: {e}")
    
    # Summary
    logger.info("=" * 70)
    logger.info("POPULATION COMPLETE")
    logger.info(f"Team pairs processed: {len(all_results)}")
    logger.info(f"Total players processed: {total_players}")
    logger.info(f"Total H2H records saved: {total_saved}")
    logger.info("=" * 70)
    
    return {
        'pairs_processed': len(all_results),
        'players_processed': total_players,
        'records_saved': total_saved,
    }


def run_3pm_population():
    """Populate 3PM baseline stats for all players."""
    logger.info("=" * 70)
    logger.info("3PM BASELINE POPULATION")
    logger.info("=" * 70)
    
    session = requests.Session()
    session.headers.update(HEADERS)
    rate_limiter = RateLimiter(base_delay=1.5)
    
    url = f"{NBA_BASE_URL}/leaguedashplayerstats"
    params = {
        'Season': '2024-25',
        'SeasonType': 'Regular Season',
        'PerMode': 'PerGame',
        'LeagueID': '00',
    }
    
    data = make_nba_request(session, url, params, rate_limiter)
    if not data:
        logger.error("Failed to fetch 3PM stats")
        return 0
    
    try:
        result_sets = data.get('resultSets', [])
        if not result_sets:
            return 0
        
        headers = result_sets[0].get('headers', [])
        rows = result_sets[0].get('rowSet', [])
        idx = {h: i for i, h in enumerate(headers)}
        
        if not HAS_FIREBASE or not db:
            logger.error("Firestore not available")
            return 0
        
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
                logger.info(f"Committed {saved} player stats")
        
        if saved % 500 != 0:
            batch.commit()
        
        logger.info(f"✅ Saved 3PM stats for {saved} players")
        return saved
        
    except Exception as e:
        logger.error(f"3PM population error: {e}")
        return 0


if __name__ == "__main__":
    start_time = datetime.now()
    
    # Run 3PM baseline first (single request)
    logger.info("\n" + "=" * 70)
    logger.info("STEP 1: 3PM Baseline Stats")
    logger.info("=" * 70)
    three_pm_count = run_3pm_population()
    
    # Run parallel H2H population
    logger.info("\n" + "=" * 70)
    logger.info("STEP 2: H2H Matchup Data (4 parallel workers)")
    logger.info("=" * 70)
    h2h_results = run_parallel_population(max_workers=4)
    
    # Final summary
    duration = (datetime.now() - start_time).total_seconds()
    logger.info("\n" + "=" * 70)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info(f"3PM player stats: {three_pm_count}")
    logger.info(f"H2H pairs: {h2h_results['pairs_processed']}")
    logger.info(f"H2H records: {h2h_results['records_saved']}")
    logger.info("=" * 70)
