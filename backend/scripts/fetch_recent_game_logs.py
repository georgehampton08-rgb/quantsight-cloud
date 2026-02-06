"""
NBA Game Log Fetcher v5 - Today's Games Focus
Smart approach:
1. Get today's games from schedule service
2. For each game, fetch both team rosters
3. Fetch game logs for all players in today's matchups
4. Group by game_id and matchup for proper organization
"""
import requests
import time
import random
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firestore_db import get_firestore_db
from services.nba_schedule import get_schedule_service

# Try to import CURRENT_SEASON from config
try:
    from core.config import CURRENT_SEASON
except ImportError:
    CURRENT_SEASON = "2025-26"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TodaysGameLogFetcher:
    """
    Fetches game logs for all players in today's games.
    Groups players by matchup and team for proper organization.
    """
    
    BASE_URL = "https://stats.nba.com/stats"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Connection': 'keep-alive',
    }
    
    # Team IDs
    TEAMS = {
        1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
        1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
        1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
        1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
        1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
        1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
        1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
        1610612762: "UTA", 1610612764: "WAS"
    }
    
    # Reverse lookup
    ABBR_TO_ID = {v: k for k, v in TEAMS.items()}
    
    def __init__(self, min_delay=12.0, max_delay=20.0, games_per_player=30):
        self.db = get_firestore_db()
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.schedule_service = get_schedule_service()
        
        self.timeout = (15, 60)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.games_per_player = games_per_player
        
        # Stats
        self.players_processed = 0
        self.games_saved = 0
        self.errors = []
        
        # Game mapping: game_id -> {matchup, home_team, away_team, date, players: {home: [], away: []}}
        self.game_mapping = {}
    
    def wait_with_jitter(self):
        """Wait with random jitter"""
        base_wait = random.uniform(self.min_delay, self.max_delay)
        if random.random() < 0.15:
            base_wait += random.uniform(15, 30)
            logger.info(f"Longer break ({base_wait:.1f}s)...")
        else:
            logger.info(f"Waiting {base_wait:.1f}s...")
        time.sleep(base_wait)
    
    def make_request(self, url: str, params: dict, max_retries: int = 3) -> Optional[dict]:
        """Make request with retry"""
        for attempt in range(max_retries):
            try:
                self.wait_with_jitter()
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(30)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logger.warning("Rate limited! Waiting 5 minutes...")
                    time.sleep(300)
                else:
                    logger.error(f"HTTP {e.response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return None
        return None
    
    def get_todays_games(self) -> List[Dict]:
        """Get today's games from schedule service"""
        logger.info("Fetching today's games...")
        
        games = []
        try:
            todays_games = self.schedule_service.get_todays_games()
            
            for game in todays_games:
                game_id = game.get('game_id', '')
                home_team = game.get('home_team', '')
                away_team = game.get('away_team', '')
                status = game.get('status', '')
                display = game.get('display', '')
                
                matchup = f"{away_team} @ {home_team}"
                
                games.append({
                    'game_id': game_id,
                    'matchup': matchup,
                    'home_team': home_team,
                    'away_team': away_team,
                    'status': status,
                    'display': display,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                })
                
                # Initialize game mapping
                self.game_mapping[game_id] = {
                    'matchup': matchup,
                    'home_team': home_team,
                    'away_team': away_team,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'status': status,
                    'players': {
                        'home': [],
                        'away': [],
                    }
                }
                
            logger.info(f"Found {len(games)} games today")
            for g in games:
                logger.info(f"  - {g['display']} ({g['status']})")
                
        except Exception as e:
            logger.error(f"Error fetching today's games: {e}")
        
        return games
    
    def get_team_roster(self, team_abbr: str) -> List[Dict]:
        """Get active roster for a team"""
        logger.info(f"Fetching roster for {team_abbr}...")
        
        team_id = self.ABBR_TO_ID.get(team_abbr)
        if not team_id:
            logger.error(f"Unknown team: {team_abbr}")
            return []
        
        url = f"{self.BASE_URL}/commonteamroster"
        params = {
            'TeamID': team_id,
            'Season': CURRENT_SEASON,
        }
        
        data = self.make_request(url, params)
        if not data:
            return []
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
        except (KeyError, IndexError):
            return []
        
        players = []
        for row in rows:
            player = dict(zip(headers, row))
            players.append({
                'player_id': str(player.get('PLAYER_ID', '')),
                'name': player.get('PLAYER', ''),
                'team': team_abbr,
                'position': player.get('POSITION', ''),
                'jersey': player.get('NUM', ''),
            })
        
        logger.info(f"  Found {len(players)} players on {team_abbr}")
        return players
    
    def get_player_game_log(self, player_id: str, player_name: str, team: str, 
                            game_id: str, matchup: str, is_home: bool) -> List[Dict]:
        """Get last N games for a player with proper mapping"""
        url = f"{self.BASE_URL}/playergamelog"
        params = {
            'PlayerID': player_id,
            'Season': CURRENT_SEASON,
            'SeasonType': 'Regular Season',
        }
        
        data = self.make_request(url, params)
        if not data:
            return []
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
        except (KeyError, IndexError):
            return []
        
        games = []
        for row in rows[:self.games_per_player]:
            game = dict(zip(headers, row))
            
            # Parse matchup
            matchup_raw = game.get('MATCHUP', '')
            home_away = 'Home' if 'vs.' in matchup_raw else 'Away'
            opponent = matchup_raw.split(' ')[-1] if matchup_raw else 'UNK'
            
            # Calculate advanced metrics
            fgm = int(game.get('FGM', 0) or 0)
            fga = int(game.get('FGA', 0) or 0)
            fg3m = int(game.get('FG3M', 0) or 0)
            ftm = int(game.get('FTM', 0) or 0)
            fta = int(game.get('FTA', 0) or 0)
            pts = int(game.get('PTS', 0) or 0)
            
            ts_pct = 0.0
            if fga > 0 or fta > 0:
                ts_attempts = 2 * (fga + 0.44 * fta)
                ts_pct = pts / ts_attempts if ts_attempts > 0 else 0
            
            efg_pct = (fgm + 0.5 * fg3m) / fga if fga > 0 else 0
            
            log_game_id = str(game.get('Game_ID', ''))
            
            # Parse minutes to integer (e.g., "32:15" -> 32)
            min_raw = str(game.get('MIN', '0'))
            try:
                minutes_int = int(min_raw.split(':')[0]) if ':' in min_raw else int(float(min_raw))
            except:
                minutes_int = 0
            
            # Map WL to result
            wl = game.get('WL', '')
            result = 'win' if wl == 'W' else 'loss' if wl == 'L' else 'unknown'
            
            games.append({
                'id': f"{log_game_id}_{player_id}",
                'game_id': log_game_id,
                'player_id': player_id,
                'player_name': player_name,
                'team': team,
                'game_date': game.get('GAME_DATE', ''),
                'matchup': matchup_raw,
                'opponent': opponent,
                'home_away': home_away,
                'result': result,  # Frontend expects 'result' not 'wl'
                'minutes': minutes_int,  # Frontend expects integer
                'points': pts,
                'rebounds': int(game.get('REB', 0) or 0),
                'assists': int(game.get('AST', 0) or 0),
                'steals': int(game.get('STL', 0) or 0),
                'blocks': int(game.get('BLK', 0) or 0),
                'turnovers': int(game.get('TOV', 0) or 0),
                'fg_made': fgm,
                'fg_attempted': fga,
                'fg_pct': float(game.get('FG_PCT', 0) or 0),
                'fg3_made': fg3m,
                'fg3_attempted': int(game.get('FG3A', 0) or 0),
                'fg3_pct': float(game.get('FG3_PCT', 0) or 0),
                'ft_made': ftm,
                'ft_attempted': fta,
                'ft_pct': float(game.get('FT_PCT', 0) or 0),
                'plus_minus': int(game.get('PLUS_MINUS', 0) or 0),
                'ts_pct': round(ts_pct, 3),
                'efg_pct': round(efg_pct, 3),
                # Mapping fields for today's matchup context
                'todays_game_id': game_id,
                'todays_matchup': matchup,
                'todays_is_home': is_home,
            })
        
        return games
    
    def save_player_to_matchup(self, player_data: Dict, game_info: Dict, games: List[Dict], is_home: bool, force=False) -> int:
        """
        Save player data organized by matchup structure:
        matchups/{date}/games/{game_id} -> contains home_team, away_team info
        matchups/{date}/games/{game_id}/players/{player_id} -> player games
        
        Also saves flat game_logs for backwards compatibility.
        """
        if not games:
            return 0
        
        date = game_info['date']
        game_id = game_info['game_id']
        matchup = game_info['matchup']
        home_team = game_info['home_team']
        away_team = game_info['away_team']
        player_id = player_data['player_id']
        player_name = player_data['name']
        team = player_data['team']
        
        saved = 0
        
        # 1. Save/Update the game document
        game_doc_ref = self.db.collection('matchups').document(date).collection('games').document(game_id)
        game_doc_ref.set({
            'game_id': game_id,
            'date': date,
            'matchup': matchup,
            'home_team': home_team,
            'away_team': away_team,
            'status': game_info.get('status', ''),
            'updated_at': datetime.now().isoformat(),
        }, merge=True)
        
        # 2. Save player summary with their last N games
        player_doc_ref = game_doc_ref.collection('players').document(player_id)
        
        # Calculate averages from game logs
        if games:
            avg_pts = sum(g['points'] for g in games) / len(games)
            avg_reb = sum(g['rebounds'] for g in games) / len(games)
            avg_ast = sum(g['assists'] for g in games) / len(games)
            avg_ts = sum(g['ts_pct'] for g in games) / len(games)
        else:
            avg_pts = avg_reb = avg_ast = avg_ts = 0
        
        player_summary = {
            'player_id': player_id,
            'player_name': player_name,
            'team': team,
            'is_home': is_home,
            'position': player_data.get('position', ''),
            'jersey': player_data.get('jersey', ''),
            # Averages
            'avg_points': round(avg_pts, 1),
            'avg_rebounds': round(avg_reb, 1),
            'avg_assists': round(avg_ast, 1),
            'avg_ts_pct': round(avg_ts, 3),
            'games_count': len(games),
            # Recent games embedded
            'recent_games': games,
            'updated_at': datetime.now().isoformat(),
        }
        
        player_doc_ref.set(player_summary, merge=True)
        saved += 1
        
        # 3. Also save to flat game_logs for backwards compatibility
        flat_collection = self.db.collection('game_logs')
        batch = self.db.batch()
        batch_count = 0
        
        for game in games:
            doc_id = game['id']
            doc_ref = flat_collection.document(doc_id)
            
            if not force:
                if doc_ref.get().exists:
                    continue
            
            batch.set(doc_ref, game)
            batch_count += 1
            
            if batch_count >= 500:
                batch.commit()
                batch = self.db.batch()
                batch_count = 0
        
        if batch_count > 0:
            batch.commit()
        
        return saved
    
    def save_game_mapping(self):
        """Save game mapping to Firestore"""
        collection = self.db.collection('game_mappings')
        
        for game_id, mapping in self.game_mapping.items():
            doc_ref = collection.document(game_id)
            doc_ref.set(mapping)
        
        logger.info(f"Saved {len(self.game_mapping)} game mappings")
    
    def run(self, force=False):
        """Main execution - process today's games"""
        logger.info("="*60)
        logger.info("NBA Game Log Fetcher v5 (Today's Games Focus)")
        logger.info(f"Delay: {self.min_delay}-{self.max_delay}s")
        logger.info(f"Games per player: {self.games_per_player}")
        logger.info("="*60)
        
        start_time = time.time()
        
        # Get today's games
        todays_games = self.get_todays_games()
        if not todays_games:
            logger.error("No games today")
            return
        
        # Process each game
        for game_idx, game in enumerate(todays_games, 1):
            game_id = game['game_id']
            matchup = game['matchup']
            home_team = game['home_team']
            away_team = game['away_team']
            
            logger.info(f"\n{'='*60}")
            logger.info(f"GAME {game_idx}/{len(todays_games)}: {matchup}")
            logger.info("="*60)
            
            # Get rosters for both teams
            home_roster = self.get_team_roster(home_team)
            away_roster = self.get_team_roster(away_team)
            
            # Process home team players
            logger.info(f"\n--- {home_team} (Home) ---")
            for i, player in enumerate(home_roster, 1):
                player_id = player['player_id']
                name = player['name']
                
                logger.info(f"[{i}/{len(home_roster)}] {name}")
                
                games = self.get_player_game_log(
                    player_id, name, home_team,
                    game_id, matchup, is_home=True
                )
                
                if games:
                    saved = self.save_player_to_matchup(player, game, games, is_home=True, force=force)
                    self.games_saved += saved
                    logger.info(f"   Got {len(games)} games, saved to matchup")
                    
                    # Add to mapping
                    self.game_mapping[game_id]['players']['home'].append({
                        'player_id': player_id,
                        'name': name,
                        'position': player.get('position', ''),
                    })
                else:
                    logger.warning(f"   No games found")
                
                self.players_processed += 1
            
            # Process away team players
            logger.info(f"\n--- {away_team} (Away) ---")
            for i, player in enumerate(away_roster, 1):
                player_id = player['player_id']
                name = player['name']
                
                logger.info(f"[{i}/{len(away_roster)}] {name}")
                
                games = self.get_player_game_log(
                    player_id, name, away_team,
                    game_id, matchup, is_home=False
                )
                
                if games:
                    saved = self.save_player_to_matchup(player, game, games, is_home=False, force=force)
                    self.games_saved += saved
                    logger.info(f"   Got {len(games)} games, saved to matchup")
                    
                    # Add to mapping
                    self.game_mapping[game_id]['players']['away'].append({
                        'player_id': player_id,
                        'name': name,
                        'position': player.get('position', ''),
                    })
                else:
                    logger.warning(f"   No games found")
                
                self.players_processed += 1
        
        # Save game mapping
        self.save_game_mapping()
        
        elapsed = time.time() - start_time
        logger.info("\n" + "="*60)
        logger.info("SUMMARY")
        logger.info(f"Games today: {len(todays_games)}")
        logger.info(f"Players processed: {self.players_processed}")
        logger.info(f"Game logs saved: {self.games_saved}")
        logger.info(f"Errors: {len(self.errors)}")
        logger.info(f"Time: {elapsed/60:.1f} minutes")
        logger.info("="*60)


def main():
    parser = argparse.ArgumentParser(description="Fetch game logs for today's NBA games")
    parser.add_argument('--games-per-player', type=int, default=30, help='Games per player (default: 30)')
    parser.add_argument('--force', action='store_true', help='Force overwrite')
    parser.add_argument('--fast', action='store_true', help='Faster rate (risky)')
    
    args = parser.parse_args()
    
    if args.fast:
        fetcher = TodaysGameLogFetcher(min_delay=5.0, max_delay=10.0, games_per_player=args.games_per_player)
    else:
        fetcher = TodaysGameLogFetcher(games_per_player=args.games_per_player)
    
    fetcher.run(force=args.force)


if __name__ == '__main__':
    main()
