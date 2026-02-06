"""
NBA Complete Data Fetcher v3 - All Players + Advanced Analytics + Health Stats
Fetches from multiple stats.nba.com endpoints with proper timeouts and rate limiting
"""

import requests
import time
import random
import csv
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import socket
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core.config import CURRENT_SEASON

class NBAAdvancedFetcher:
    """Fetches all NBA players with advanced stats and health data"""
    
    BASE_URL = "https://stats.nba.com/stats"
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
    
    # Team ID to abbreviation mapping
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
    
    def __init__(self, db_path: str, data_dir: str):
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Session with proper timeout settings
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        # Timeouts: (connect_timeout, read_timeout)
        self.timeout = (10, 30)  # 10s connect, 30s read
        
        # Rate limiting: 12-18 seconds between requests (conservative)
        self.min_delay = 12.0
        self.max_delay = 18.0
        self.last_request_time = 0
        
        # Progress tracking
        self.progress_file = self.data_dir / "fetch_progress_v3.json"
        self.csv_file = self.data_dir / "nba_complete_2024_25.csv"
        self.completed_players = set()
        self.errors = []
        self.retries = {}
        
        self._load_progress()
    
    def _load_progress(self):
        """Load progress from previous run for resume capability"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.completed_players = set(data.get('completed', []))
                    self.errors = data.get('errors', [])
                    print(f"📂 Resuming: {len(self.completed_players)} players already fetched")
            except:
                pass
    
    def _save_progress(self):
        """Save progress for resume capability"""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'completed': list(self.completed_players),
                'errors': self.errors[-50:],  # Keep last 50 errors
                'last_update': datetime.now().isoformat(),
                'total_completed': len(self.completed_players)
            }, f, indent=2)
    
    def wait_with_jitter(self):
        """Wait with random jitter to appear human-like"""
        base_wait = random.uniform(self.min_delay, self.max_delay)
        
        # 15% chance of extra long pause (20-40s) for safety
        if random.random() < 0.15:
            base_wait += random.uniform(20, 40)
            print(f"    💤 Taking a longer break ({base_wait:.1f}s)...")
        else:
            print(f"    ⏳ Waiting {base_wait:.1f}s...")
        
        time.sleep(base_wait)
        self.last_request_time = time.time()
    
    def make_request(self, url: str, params: dict, max_retries: int = 3) -> Optional[dict]:
        """Make request with proper timeout and retry logic"""
        for attempt in range(max_retries):
            try:
                self.wait_with_jitter()
                
                response = self.session.get(
                    url, 
                    params=params, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                print(f"    ⏰ Timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(30)  # Wait 30s before retry on timeout
                    
            except requests.exceptions.ConnectionError:
                print(f"    🔌 Connection error (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(60)  # Wait 60s before retry on connection error
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    print(f"    🚫 Rate limited! Waiting 5 minutes...")
                    time.sleep(300)  # 5 minute cooldown on rate limit
                elif e.response.status_code >= 500:
                    print(f"    🔥 Server error {e.response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(60)
                else:
                    self.errors.append(f"HTTP {e.response.status_code}")
                    return None
                    
            except Exception as e:
                self.errors.append(f"Unknown: {str(e)[:50]}")
                return None
        
        return None
    
    def get_all_players_league(self) -> List[Dict]:
        """Get ALL players from league dashboard (more complete list)"""
        print("\n📋 Fetching complete player list from league dashboard...")
        
        url = f"{self.BASE_URL}/leaguedashplayerstats"
        params = {
            'College': '',
            'Conference': '',
            'Country': '',
            'DateFrom': '',
            'DateTo': '',
            'Division': '',
            'DraftPick': '',
            'DraftYear': '',
            'GameScope': '',
            'GameSegment': '',
            'Height': '',
            'ISTRound': '',
            'LastNGames': '0',
            'LeagueID': '00',
            'Location': '',
            'MeasureType': 'Base',
            'Month': '0',
            'OpponentTeamID': '0',
            'Outcome': '',
            'PORound': '0',
            'PaceAdjust': 'N',
            'PerMode': 'PerGame',
            'Period': '0',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'PlusMinus': 'N',
            'Rank': 'N',
            'Season': CURRENT_SEASON,
            'SeasonSegment': '',
            'SeasonType': 'Regular Season',
            'ShotClockRange': '',
            'StarterBench': '',
            'TeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'Weight': ''
        }
        
        data = self.make_request(url, params)
        if not data:
            print("   ❌ Failed to get player list")
            return []
        
        headers = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        
        players = []
        for row in rows:
            player = dict(zip(headers, row))
            team_id = player.get('TEAM_ID')
            players.append({
                'player_id': str(player.get('PLAYER_ID', '')),
                'name': player.get('PLAYER_NAME', ''),
                'team_id': team_id,
                'team': self.TEAMS.get(team_id, 'UNK'),
                'age': player.get('AGE', 0),
                # Basic stats already included!
                'games': player.get('GP', 0),
                'minutes': player.get('MIN', 0),
                'points': player.get('PTS', 0),
                'rebounds': player.get('REB', 0),
                'assists': player.get('AST', 0),
                'steals': player.get('STL', 0),
                'blocks': player.get('BLK', 0),
                'turnovers': player.get('TOV', 0),
                'fg_pct': player.get('FG_PCT', 0),
                'fg3_pct': player.get('FG3_PCT', 0),
                'ft_pct': player.get('FT_PCT', 0),
                'plus_minus': player.get('PLUS_MINUS', 0),
            })
        
        print(f"   ✅ Found {len(players)} active players with basic stats")
        return players
    
    def get_advanced_stats_batch(self) -> Dict[str, Dict]:
        """Get advanced stats for all players in one call"""
        print("\n📊 Fetching advanced stats for all players...")
        
        url = f"{self.BASE_URL}/leaguedashplayerstats"
        params = {
            'College': '',
            'Conference': '',
            'Country': '',
            'DateFrom': '',
            'DateTo': '',
            'Division': '',
            'DraftPick': '',
            'DraftYear': '',
            'GameScope': '',
            'GameSegment': '',
            'Height': '',
            'ISTRound': '',
            'LastNGames': '0',
            'LeagueID': '00',
            'Location': '',
            'MeasureType': 'Advanced',  # Advanced stats!
            'Month': '0',
            'OpponentTeamID': '0',
            'Outcome': '',
            'PORound': '0',
            'PaceAdjust': 'N',
            'PerMode': 'PerGame',
            'Period': '0',
            'PlayerExperience': '',
            'PlayerPosition': '',
            'PlusMinus': 'N',
            'Rank': 'N',
            'Season': CURRENT_SEASON,
            'SeasonSegment': '',
            'SeasonType': 'Regular Season',
            'ShotClockRange': '',
            'StarterBench': '',
            'TeamID': '0',
            'VsConference': '',
            'VsDivision': '',
            'Weight': ''
        }
        
        data = self.make_request(url, params)
        if not data:
            print("   ❌ Failed to get advanced stats")
            return {}
        
        headers = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        
        advanced = {}
        for row in rows:
            player = dict(zip(headers, row))
            player_id = str(player.get('PLAYER_ID', ''))
            advanced[player_id] = {
                'off_rating': player.get('OFF_RATING', 0),
                'def_rating': player.get('DEF_RATING', 0),
                'net_rating': player.get('NET_RATING', 0),
                'ast_pct': player.get('AST_PCT', 0),
                'ast_to_tov': player.get('AST_TO', 0),
                'ast_ratio': player.get('AST_RATIO', 0),
                'oreb_pct': player.get('OREB_PCT', 0),
                'dreb_pct': player.get('DREB_PCT', 0),
                'reb_pct': player.get('REB_PCT', 0),
                'eff_fg_pct': player.get('EFG_PCT', 0),  # Effective FG%
                'ts_pct': player.get('TS_PCT', 0),  # True Shooting %
                'usage': player.get('USG_PCT', 0),  # Usage rate
                'pace': player.get('PACE', 0),
                'pie': player.get('PIE', 0),  # Player Impact Estimate
                'poss': player.get('POSS', 0),
            }
        
        print(f"   ✅ Got advanced stats for {len(advanced)} players")
        return advanced
    
    def get_injury_report(self) -> Dict[str, Dict]:
        """Get current injury/health status - Note: NBA API doesn't have direct injury endpoint"""
        # We'll track games missed as a proxy for health
        print("\n🏥 Calculating health metrics from games played...")
        
        # In a real scenario you'd scrape injury reports from ESPN or similar
        # For now, we'll use games played vs team games as health indicator
        return {}
    
    def save_to_csv(self, players: List[Dict], advanced: Dict[str, Dict]):
        """Save all data to comprehensive CSV"""
        csv_path = self.csv_file
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'player_id', 'name', 'team', 'age', 'games', 'minutes',
                'points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers',
                'fg_pct', 'fg3_pct', 'ft_pct', 'plus_minus',
                # Advanced stats
                'off_rating', 'def_rating', 'net_rating',
                'ts_pct', 'eff_fg_pct', 'usage', 'ast_pct', 'reb_pct', 'pie',
                # Health proxy
                'games_missed_est', 'availability_pct',
                'updated_at'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Assume season is ~50 games in by late January
            expected_games = 50
            
            for player in players:
                player_id = player['player_id']
                adv = advanced.get(player_id, {})
                
                games_played = player.get('games', 0) or 0
                games_missed = max(0, expected_games - games_played)
                availability = round((games_played / expected_games * 100) if expected_games > 0 else 100, 1)
                
                row = {
                    'player_id': player_id,
                    'name': player['name'],
                    'team': player['team'],
                    'age': player.get('age', 0),
                    'games': games_played,
                    'minutes': round(float(player.get('minutes', 0) or 0), 1),
                    'points': round(float(player.get('points', 0) or 0), 1),
                    'rebounds': round(float(player.get('rebounds', 0) or 0), 1),
                    'assists': round(float(player.get('assists', 0) or 0), 1),
                    'steals': round(float(player.get('steals', 0) or 0), 1),
                    'blocks': round(float(player.get('blocks', 0) or 0), 1),
                    'turnovers': round(float(player.get('turnovers', 0) or 0), 1),
                    'fg_pct': round(float(player.get('fg_pct', 0) or 0), 3),
                    'fg3_pct': round(float(player.get('fg3_pct', 0) or 0), 3),
                    'ft_pct': round(float(player.get('ft_pct', 0) or 0), 3),
                    'plus_minus': round(float(player.get('plus_minus', 0) or 0), 1),
                    # Advanced
                    'off_rating': round(float(adv.get('off_rating', 0) or 0), 1),
                    'def_rating': round(float(adv.get('def_rating', 0) or 0), 1),
                    'net_rating': round(float(adv.get('net_rating', 0) or 0), 1),
                    'ts_pct': round(float(adv.get('ts_pct', 0) or 0), 3),
                    'eff_fg_pct': round(float(adv.get('eff_fg_pct', 0) or 0), 3),
                    'usage': round(float(adv.get('usage', 0) or 0), 3),
                    'ast_pct': round(float(adv.get('ast_pct', 0) or 0), 3),
                    'reb_pct': round(float(adv.get('reb_pct', 0) or 0), 3),
                    'pie': round(float(adv.get('pie', 0) or 0), 3),
                    # Health
                    'games_missed_est': games_missed,
                    'availability_pct': availability,
                    'updated_at': datetime.now().isoformat()
                }
                writer.writerow(row)
        
        print(f"\n💾 Saved {len(players)} players to {csv_path}")
        return str(csv_path)
    
    def update_database(self, players: List[Dict], advanced: Dict[str, Dict]):
        """Update SQLite database with all data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create advanced_stats table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_advanced_stats (
                player_id TEXT PRIMARY KEY,
                season TEXT,
                off_rating REAL,
                def_rating REAL,
                net_rating REAL,
                ts_pct REAL,
                eff_fg_pct REAL,
                usage_pct REAL,
                ast_pct REAL,
                reb_pct REAL,
                pie REAL,
                games_missed INTEGER,
                availability_pct REAL,
                updated_at TEXT
            )
        """)
        
        expected_games = 50
        updated = 0
        
        for player in players:
            player_id = player['player_id']
            adv = advanced.get(player_id, {})
            
            games_played = player.get('games', 0) or 0
            games_missed = max(0, expected_games - games_played)
            availability = round((games_played / expected_games * 100) if expected_games > 0 else 100, 1)
            
            # Update players table
            cursor.execute("""
                INSERT OR REPLACE INTO players 
                (player_id, name, team_id, status)
                VALUES (?, ?, ?, 'active')
            """, (
                player_id,
                player['name'],
                player['team']
            ))
            
            # Update player_stats table
            cursor.execute("""
                INSERT OR REPLACE INTO player_stats 
                (player_id, season, games, points_avg, rebounds_avg, assists_avg, 
                 fg_pct, three_p_pct, ft_pct)
                VALUES (?, CURRENT_SEASON, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_id,
                games_played,
                round(float(player.get('points', 0) or 0), 1),
                round(float(player.get('rebounds', 0) or 0), 1),
                round(float(player.get('assists', 0) or 0), 1),
                round(float(player.get('fg_pct', 0) or 0), 3),
                round(float(player.get('fg3_pct', 0) or 0), 3),
                round(float(player.get('ft_pct', 0) or 0), 3)
            ))
            
            # Update advanced stats table
            cursor.execute("""
                INSERT OR REPLACE INTO player_advanced_stats 
                (player_id, season, off_rating, def_rating, net_rating, 
                 ts_pct, eff_fg_pct, usage_pct, ast_pct, reb_pct, pie,
                 games_missed, availability_pct, updated_at)
                VALUES (?, CURRENT_SEASON, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_id,
                round(float(adv.get('off_rating', 0) or 0), 1),
                round(float(adv.get('def_rating', 0) or 0), 1),
                round(float(adv.get('net_rating', 0) or 0), 1),
                round(float(adv.get('ts_pct', 0) or 0), 3),
                round(float(adv.get('eff_fg_pct', 0) or 0), 3),
                round(float(adv.get('usage', 0) or 0), 3),
                round(float(adv.get('ast_pct', 0) or 0), 3),
                round(float(adv.get('reb_pct', 0) or 0), 3),
                round(float(adv.get('pie', 0) or 0), 3),
                games_missed,
                availability,
                datetime.now().isoformat()
            ))
            
            updated += 1
        
        conn.commit()
        conn.close()
        print(f"   ✅ Updated {updated} player records in database")
        return updated
    
    def fetch_all(self):
        """Main entry point: fetch all players with advanced stats"""
        print("\n" + "="*70)
        print("🏀 NBA COMPLETE DATA FETCHER v3")
        print("   Advanced Analytics + Health Metrics")
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Rate limit: {self.min_delay}-{self.max_delay}s between requests")
        print(f"⏰ Timeouts: {self.timeout[0]}s connect, {self.timeout[1]}s read")
        print("="*70)
        
        # Step 1: Get all players with basic stats (single API call!)
        players = self.get_all_players_league()
        if not players:
            print("❌ Failed to get player list. Exiting.")
            return
        
        # Step 2: Get advanced stats (single API call!)
        advanced = self.get_advanced_stats_batch()
        
        # Step 3: Save to CSV
        self.save_to_csv(players, advanced)
        
        # Step 4: Update database
        print("\n📥 Updating database...")
        self.update_database(players, advanced)
        
        # Save progress
        self._save_progress()
        
        # Summary
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print(f"   Total players: {len(players)}")
        print(f"   With advanced stats: {len(advanced)}")
        print(f"   Errors: {len(self.errors)}")
        print(f"   CSV: {self.csv_file}")
        print(f"   Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Print top players by PPG
        print("\n🌟 Top 10 Scorers:")
        sorted_players = sorted(players, key=lambda x: float(x.get('points', 0) or 0), reverse=True)
        for i, p in enumerate(sorted_players[:10]):
            adv = advanced.get(p['player_id'], {})
            print(f"   {i+1}. {p['name']} ({p['team']}): {p['points']:.1f} PPG, TS%: {float(adv.get('ts_pct', 0) or 0):.1%}, Usage: {float(adv.get('usage', 0) or 0):.1%}")
        
        return players, advanced


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    data_dir = script_dir / 'data' / 'fetched'
    
    print(f"📁 Database: {db_path}")
    print(f"📁 Output dir: {data_dir}")
    
    fetcher = NBAAdvancedFetcher(str(db_path), str(data_dir))
    fetcher.fetch_all()
    
    print("\n✅ Complete!")
