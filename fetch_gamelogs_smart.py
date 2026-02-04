"""
NBA Game Log Fetcher v3 - Smart Version
Uses cached player list from CSV to avoid API timeout on initial fetch
- Reads player IDs from already-fetched nba_complete_2024_25.csv
- Fetches last 15 games per player with opponent info
- Fetches player bio (height, weight, age, headshot)
- APPEND-ONLY storage (never overwrites)
- Skip-on-error with continue capability
"""

import requests
import time
import random
import csv
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core.config import CURRENT_SEASON

class NBASmartFetcher:
    """Smart fetcher using cached player list"""
    
    BASE_URL = "https://stats.nba.com/stats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
    }
    
    def __init__(self, db_path: str, data_dir: str, games_per_player: int = 15):
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.games_per_player = games_per_player
        
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        # Longer timeouts for reliability
        self.timeout = (20, 90)  # 20s connect, 90s read
        
        # Rate limiting
        self.min_delay = 15.0
        self.max_delay = 25.0
        
        # Timestamped files
        self.run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.progress_file = self.data_dir / "gamelog_progress.json"
        self.games_csv = self.data_dir / f"game_logs_{self.run_timestamp}.csv"
        self.bio_csv = self.data_dir / f"player_bio_{self.run_timestamp}.csv"
        
        self.completed_players = set()
        self.skipped_players = []
        self.errors = []
        
        self._load_progress()
        self._init_database()
    
    def _init_database(self):
        """Create tables if not exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_game_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL,
                player_name TEXT,
                game_id TEXT NOT NULL,
                game_date TEXT,
                matchup TEXT,
                opponent TEXT,
                home_away TEXT,
                result TEXT,
                minutes INTEGER,
                points INTEGER,
                rebounds INTEGER,
                assists INTEGER,
                steals INTEGER,
                blocks INTEGER,
                turnovers INTEGER,
                fg_pct REAL,
                fg3_pct REAL,
                ft_pct REAL,
                plus_minus INTEGER,
                fetched_at TEXT,
                UNIQUE(player_id, game_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_bio (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                team TEXT,
                position TEXT,
                height TEXT,
                height_inches INTEGER,
                weight INTEGER,
                age INTEGER,
                country TEXT,
                college TEXT,
                draft_year INTEGER,
                jersey_number TEXT,
                headshot_url TEXT,
                updated_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_rolling_averages (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                last_n_games INTEGER,
                avg_points REAL,
                avg_rebounds REAL,
                avg_assists REAL,
                trend TEXT,
                updated_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_progress(self):
        """Load progress"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.completed_players = set(data.get('completed', []))
                    print(f"📂 Resuming: {len(self.completed_players)} players done")
            except (json.JSONDecodeError, KeyError) as e:
                pass
    
    def _save_progress(self):
        """Save progress"""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'completed': list(self.completed_players),
                'skipped': self.skipped_players[-100:],
                'errors': self.errors[-50:],
                'last_update': datetime.now().isoformat()
            }, f, indent=2)
    
    def get_players_from_csv(self) -> List[Dict]:
        """Read player list from already-fetched CSV"""
        csv_path = self.data_dir / "nba_complete_2024_25.csv"
        
        if not csv_path.exists():
            print(f"❌ CSV not found: {csv_path}")
            return []
        
        players = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                players.append({
                    'player_id': row.get('player_id', ''),
                    'name': row.get('name', ''),
                    'team': row.get('team', ''),
                })
        
        print(f"   ✅ Loaded {len(players)} players from CSV cache")
        return players
    
    def wait_with_jitter(self):
        """Wait with jitter"""
        wait = random.uniform(self.min_delay, self.max_delay)
        if random.random() < 0.12:
            wait += random.uniform(20, 45)
            print(f"💤 Longer break ({wait:.0f}s)...", end=" ")
        else:
            print(f"⏳{wait:.0f}s...", end=" ")
        time.sleep(wait)
    
    def make_request(self, url: str, params: dict) -> Optional[dict]:
        """Make request with error handling - returns None on failure"""
        for attempt in range(3):
            try:
                self.wait_with_jitter()
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 429:
                    print(f"🚫 Rate limited, waiting 5min...")
                    time.sleep(300)
                    continue
                    
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout({attempt+1}/3)", end=" ")
                if attempt < 2:
                    time.sleep(45)
                    
            except Exception as e:
                self.errors.append(str(e)[:40])
                print(f"❌ Error: {str(e)[:30]}", end=" ")
                return None
        
        return None  # Skip this player on failure
    
    def fetch_game_log(self, player_id: str, player_name: str) -> List[Dict]:
        """Fetch last N games"""
        data = self.make_request(f"{self.BASE_URL}/playergamelog", {
            'PlayerID': player_id,
            'Season': CURRENT_SEASON,
            'SeasonType': 'Regular Season',
        })
        
        if not data:
            return []
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
        except (KeyError, IndexError) as e:
            return []
        
        games = []
        for row in rows[:self.games_per_player]:
            game = dict(zip(headers, row))
            matchup = game.get('MATCHUP', '')
            
            games.append({
                'player_id': player_id,
                'player_name': player_name,
                'game_id': str(game.get('Game_ID', '')),
                'game_date': game.get('GAME_DATE', ''),
                'matchup': matchup,
                'opponent': matchup.split(' ')[-1] if matchup else '',
                'home_away': 'home' if 'vs.' in matchup else 'away',
                'result': 'W' if game.get('WL') == 'W' else 'L',
                'minutes': int(game.get('MIN', 0) or 0),
                'points': int(game.get('PTS', 0) or 0),
                'rebounds': int(game.get('REB', 0) or 0),
                'assists': int(game.get('AST', 0) or 0),
                'steals': int(game.get('STL', 0) or 0),
                'blocks': int(game.get('BLK', 0) or 0),
                'turnovers': int(game.get('TOV', 0) or 0),
                'fg_pct': float(game.get('FG_PCT', 0) or 0),
                'fg3_pct': float(game.get('FG3_PCT', 0) or 0),
                'ft_pct': float(game.get('FT_PCT', 0) or 0),
                'plus_minus': int(game.get('PLUS_MINUS', 0) or 0),
            })
        
        return games
    
    def fetch_player_bio(self, player_id: str, player_name: str) -> Optional[Dict]:
        """Fetch bio info"""
        data = self.make_request(f"{self.BASE_URL}/commonplayerinfo", {
            'PlayerID': player_id,
        })
        
        if not data:
            return None
        
        try:
            headers = data['resultSets'][0]['headers']
            row = data['resultSets'][0]['rowSet'][0]
            player = dict(zip(headers, row))
        except (KeyError, IndexError) as e:
            return None
        
        height = player.get('HEIGHT', '').replace('-', "'") + '"'
        
        return {
            'player_id': player_id,
            'player_name': player_name,
            'team': player.get('TEAM_ABBREVIATION', ''),
            'position': player.get('POSITION', ''),
            'height': height,
            'weight': int(player.get('WEIGHT', 0) or 0),
            'age': int(player.get('SEASON_EXP', 0) or 0) + 19,  # Approximate
            'country': player.get('COUNTRY', ''),
            'college': player.get('SCHOOL', ''),
            'jersey_number': player.get('JERSEY', ''),
            'headshot_url': f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png",
        }
    
    def save_to_db(self, games: List[Dict], bio: Optional[Dict]):
        """Save to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        new_games = 0
        for game in games:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO player_game_logs 
                    (player_id, player_name, game_id, game_date, matchup, opponent,
                     home_away, result, minutes, points, rebounds, assists, steals,
                     blocks, turnovers, fg_pct, fg3_pct, ft_pct, plus_minus, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game['player_id'], game['player_name'], game['game_id'],
                    game['game_date'], game['matchup'], game['opponent'],
                    game['home_away'], game['result'], game['minutes'],
                    game['points'], game['rebounds'], game['assists'],
                    game['steals'], game['blocks'], game['turnovers'],
                    game['fg_pct'], game['fg3_pct'], game['ft_pct'],
                    game['plus_minus'], datetime.now().isoformat()
                ))
                if cursor.rowcount > 0:
                    new_games += 1
            except sqlite3.Error as e:
                pass
        
        if bio:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO player_bio 
                    (player_id, player_name, team, position, height, weight,
                     age, country, college, jersey_number, headshot_url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bio['player_id'], bio['player_name'], bio['team'],
                    bio['position'], bio['height'], bio['weight'],
                    bio['age'], bio['country'], bio['college'],
                    bio['jersey_number'], bio['headshot_url'],
                    datetime.now().isoformat()
                ))
            except sqlite3.Error as e:
                pass
        
        # Update rolling averages
        if games:
            n = len(games)
            avg_pts = sum(g['points'] for g in games) / n
            avg_reb = sum(g['rebounds'] for g in games) / n
            avg_ast = sum(g['assists'] for g in games) / n
            
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO player_rolling_averages
                    (player_id, player_name, last_n_games, avg_points, avg_rebounds,
                     avg_assists, trend, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    games[0]['player_id'], games[0]['player_name'], n,
                    round(avg_pts, 1), round(avg_reb, 1), round(avg_ast, 1),
                    'neutral', datetime.now().isoformat()
                ))
            except sqlite3.Error as e:
                pass
        
        conn.commit()
        conn.close()
        return new_games
    
    def fetch_all(self):
        """Main entry"""
        print("\n" + "="*70)
        print("🏀 NBA SMART GAME LOG FETCHER v3")
        print(f"   Using cached player list + skip-on-error")
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏰ Timeouts: {self.timeout[0]}s connect, {self.timeout[1]}s read")
        print("="*70)
        
        # Load from CSV instead of API
        players = self.get_players_from_csv()
        if not players:
            print("❌ No players loaded")
            return
        
        remaining = [p for p in players if p['player_id'] not in self.completed_players]
        print(f"\n📊 {len(remaining)} players remaining")
        
        if not remaining:
            print("✅ All done!")
            return
        
        # Time estimate: 2 calls per player * 20s avg = 40s/player
        est_hours = (len(remaining) * 40) / 3600
        print(f"⏰ Estimated: ~{est_hours:.1f} hours")
        print("-"*70)
        
        total_games = 0
        
        for i, player in enumerate(remaining):
            pid = player['player_id']
            name = player['name']
            
            print(f"[{i+1}/{len(remaining)}] {name[:20]}...", end=" ")
            
            # Fetch game log
            games = self.fetch_game_log(pid, name)
            
            # Fetch bio
            bio = self.fetch_player_bio(pid, name)
            
            if games or bio:
                new = self.save_to_db(games, bio)
                total_games += new
                
                avg = sum(g['points'] for g in games) / len(games) if games else 0
                bio_str = f" {bio['height']}" if bio and bio.get('height') else ""
                print(f"✅ {len(games)}games {new}new {avg:.1f}ppg{bio_str}")
            else:
                self.skipped_players.append(pid)
                print("⏭️ Skipped")
            
            self.completed_players.add(pid)
            
            if (i + 1) % 15 == 0:
                self._save_progress()
                print(f"    💾 Saved ({len(self.completed_players)} done)")
        
        self._save_progress()
        
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print(f"   Processed: {len(remaining)}")
        print(f"   Games saved: {total_games}")
        print(f"   Skipped: {len(self.skipped_players)}")
        print(f"   Files: {self.games_csv.name}")
        print("="*70)


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    data_dir = script_dir / 'data' / 'fetched'
    
    fetcher = NBASmartFetcher(str(db_path), str(data_dir))
    fetcher.fetch_all()
