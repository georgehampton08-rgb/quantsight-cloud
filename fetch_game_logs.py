"""
NBA Game Log Fetcher v2 - Complete Player Data
- Last 15-20 games per player with opponent info
- Player bio: height, weight, age, position, draft info
- Headshot URLs for player photos
- College, country, years of experience
- APPEND-ONLY: Never overwrites existing game data
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
import os
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core.config import CURRENT_SEASON

class NBAGameLogFetcher:
    """Fetches game logs for all players with proper rate limiting"""
    
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
    
    # Team ID to abbreviation
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
    
    def __init__(self, db_path: str, data_dir: str, games_per_player: int = 15):
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.games_per_player = games_per_player
        
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        # Timeouts: (connect, read) - increased for reliability
        self.timeout = (15, 60)  # 15s connect, 60s read
        
        # Rate limiting: 12-20 seconds
        self.min_delay = 12.0
        self.max_delay = 20.0
        
        # Progress tracking with timestamped files to avoid overwriting
        self.run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.progress_file = self.data_dir / "gamelog_progress.json"
        self.games_csv = self.data_dir / f"player_game_logs_{self.run_timestamp}.csv"
        self.bio_csv = self.data_dir / f"player_bio_{self.run_timestamp}.csv"
        self.completed_players = set()
        self.existing_games = set()  # Track existing game IDs to avoid duplicates
        self.errors = []
        
        self._load_progress()
        self._init_database()
        self._load_existing_games()
    
    def _init_database(self):
        """Create game_logs table if not exists"""
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
                fg_made INTEGER,
                fg_attempted INTEGER,
                fg_pct REAL,
                fg3_made INTEGER,
                fg3_attempted INTEGER,
                fg3_pct REAL,
                ft_made INTEGER,
                ft_attempted INTEGER,
                ft_pct REAL,
                plus_minus INTEGER,
                fetched_at TEXT,
                UNIQUE(player_id, game_id)
            )
        """)
        
        # Create rolling averages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_rolling_averages (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                last_n_games INTEGER,
                avg_points REAL,
                avg_rebounds REAL,
                avg_assists REAL,
                avg_steals REAL,
                avg_blocks REAL,
                avg_minutes REAL,
                avg_fg_pct REAL,
                avg_fg3_pct REAL,
                hot_streak INTEGER DEFAULT 0,
                cold_streak INTEGER DEFAULT 0,
                trend TEXT,
                updated_at TEXT
            )
        """)
        
        # Create player bio table for height, weight, age, position, etc.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_bio (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                team TEXT,
                position TEXT,
                height TEXT,
                height_inches INTEGER,
                weight INTEGER,
                birthdate TEXT,
                age INTEGER,
                country TEXT,
                college TEXT,
                draft_year INTEGER,
                draft_round INTEGER,
                draft_pick INTEGER,
                years_experience INTEGER,
                jersey_number TEXT,
                headshot_url TEXT,
                updated_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_progress(self):
        """Load progress from previous run"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.completed_players = set(data.get('completed', []))
                    print(f"📂 Resuming: {len(self.completed_players)} players already fetched")
            except (json.JSONDecodeError, KeyError) as e:
                pass
    
    def _load_existing_games(self):
        """Load existing game IDs to avoid duplicates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT player_id, game_id FROM player_game_logs")
            for row in cursor.fetchall():
                self.existing_games.add(f"{row[0]}_{row[1]}")
        except sqlite3.Error as e:
            pass
        
        conn.close()
        print(f"   📊 Found {len(self.existing_games)} existing game records")
    
    def _save_progress(self):
        """Save progress for resume"""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'completed': list(self.completed_players),
                'errors': self.errors[-50:],
                'last_update': datetime.now().isoformat()
            }, f, indent=2)
    
    def wait_with_jitter(self):
        """Wait with random jitter"""
        base_wait = random.uniform(self.min_delay, self.max_delay)
        
        # 15% chance of longer pause
        if random.random() < 0.15:
            base_wait += random.uniform(15, 30)
            print(f"    💤 Longer break ({base_wait:.1f}s)...")
        else:
            print(f"    ⏳ Waiting {base_wait:.1f}s...")
        
        time.sleep(base_wait)
    
    def make_request(self, url: str, params: dict, max_retries: int = 3) -> Optional[dict]:
        """Make request with timeout and retry"""
        for attempt in range(max_retries):
            try:
                self.wait_with_jitter()
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                print(f"    ⏰ Timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(30)
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    print(f"    🚫 Rate limited! Waiting 5 minutes...")
                    time.sleep(300)
                else:
                    return None
                    
            except Exception as e:
                self.errors.append(str(e)[:50])
                return None
        
        return None
    
    def get_player_list(self) -> List[Dict]:
        """Get list of all active players"""
        print("\n📋 Fetching player list...")
        
        url = f"{self.BASE_URL}/leaguedashplayerstats"
        params = {
            'LastNGames': '0',
            'LeagueID': '00',
            'MeasureType': 'Base',
            'Month': '0',
            'OpponentTeamID': '0',
            'PORound': '0',
            'PerMode': 'PerGame',
            'Period': '0',
            'Season': CURRENT_SEASON,
            'SeasonType': 'Regular Season',
            'TeamID': '0',
        }
        
        data = self.make_request(url, params)
        if not data:
            return []
        
        headers = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        
        players = []
        for row in rows:
            player = dict(zip(headers, row))
            players.append({
                'player_id': str(player.get('PLAYER_ID', '')),
                'name': player.get('PLAYER_NAME', ''),
                'team': self.TEAMS.get(player.get('TEAM_ID'), 'UNK'),
            })
        
        print(f"   ✅ Found {len(players)} players")
        return players
    
    def get_player_game_log(self, player_id: str, player_name: str) -> List[Dict]:
        """Get last N games for a player"""
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
        for row in rows[:self.games_per_player]:  # Limit to last N games
            game = dict(zip(headers, row))
            
            # Parse matchup to get opponent
            matchup = game.get('MATCHUP', '')
            home_away = 'home' if 'vs.' in matchup else 'away'
            opponent = matchup.split(' ')[-1] if matchup else 'UNK'
            
            # Parse result
            wl = game.get('WL', '')
            result = 'win' if wl == 'W' else 'loss' if wl == 'L' else 'unknown'
            
            games.append({
                'player_id': player_id,
                'player_name': player_name,
                'game_id': str(game.get('Game_ID', '')),
                'game_date': game.get('GAME_DATE', ''),
                'matchup': matchup,
                'opponent': opponent,
                'home_away': home_away,
                'result': result,
                'minutes': int(game.get('MIN', 0) or 0),
                'points': int(game.get('PTS', 0) or 0),
                'rebounds': int(game.get('REB', 0) or 0),
                'assists': int(game.get('AST', 0) or 0),
                'steals': int(game.get('STL', 0) or 0),
                'blocks': int(game.get('BLK', 0) or 0),
                'turnovers': int(game.get('TOV', 0) or 0),
                'fg_made': int(game.get('FGM', 0) or 0),
                'fg_attempted': int(game.get('FGA', 0) or 0),
                'fg_pct': float(game.get('FG_PCT', 0) or 0),
                'fg3_made': int(game.get('FG3M', 0) or 0),
                'fg3_attempted': int(game.get('FG3A', 0) or 0),
                'fg3_pct': float(game.get('FG3_PCT', 0) or 0),
                'ft_made': int(game.get('FTM', 0) or 0),
                'ft_attempted': int(game.get('FTA', 0) or 0),
                'ft_pct': float(game.get('FT_PCT', 0) or 0),
                'plus_minus': int(game.get('PLUS_MINUS', 0) or 0),
            })
        
        return games
    
    def get_player_bio(self, player_id: str, player_name: str) -> Optional[Dict]:
        """Get player bio info: height, weight, age, position, draft, headshot"""
        url = f"{self.BASE_URL}/commonplayerinfo"
        params = {
            'PlayerID': player_id,
        }
        
        data = self.make_request(url, params)
        if not data:
            return None
        
        try:
            headers = data['resultSets'][0]['headers']
            row = data['resultSets'][0]['rowSet'][0]
            player = dict(zip(headers, row))
        except (KeyError, IndexError):
            return None
        
        # Parse height (e.g., "6-6" to "6'6"" and inches)
        height_raw = player.get('HEIGHT', '')
        height_display = height_raw.replace('-', "'") + '"' if height_raw else ''
        height_inches = 0
        if height_raw and '-' in height_raw:
            parts = height_raw.split('-')
            try:
                height_inches = int(parts[0]) * 12 + int(parts[1])
            except (ValueError, IndexError) as e:
                pass
        
        # Calculate age from birthdate
        birthdate = player.get('BIRTHDATE', '')
        age = 0
        if birthdate:
            try:
                birth_dt = datetime.fromisoformat(birthdate.replace('T', ' ').split(' ')[0])
                age = (datetime.now() - birth_dt).days // 365
            except (ValueError, AttributeError) as e:
                pass
        
        # Headshot URL
        headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"
        
        return {
            'player_id': player_id,
            'player_name': player_name,
            'team': player.get('TEAM_ABBREVIATION', ''),
            'position': player.get('POSITION', ''),
            'height': height_display,
            'height_inches': height_inches,
            'weight': int(player.get('WEIGHT', 0) or 0),
            'birthdate': birthdate,
            'age': age,
            'country': player.get('COUNTRY', ''),
            'college': player.get('SCHOOL', ''),
            'draft_year': int(player.get('DRAFT_YEAR', 0) or 0) if player.get('DRAFT_YEAR', '').isdigit() else 0,
            'draft_round': int(player.get('DRAFT_ROUND', 0) or 0) if str(player.get('DRAFT_ROUND', '')).isdigit() else 0,
            'draft_pick': int(player.get('DRAFT_NUMBER', 0) or 0) if str(player.get('DRAFT_NUMBER', '')).isdigit() else 0,
            'years_experience': int(player.get('SEASON_EXP', 0) or 0),
            'jersey_number': player.get('JERSEY', ''),
            'headshot_url': headshot_url,
        }
    
    def save_player_bio(self, bio: Dict):
        """Save player bio to database"""
        if not bio:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO player_bio
            (player_id, player_name, team, position, height, height_inches,
             weight, birthdate, age, country, college, draft_year, draft_round,
             draft_pick, years_experience, jersey_number, headshot_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bio['player_id'], bio['player_name'], bio['team'], bio['position'],
            bio['height'], bio['height_inches'], bio['weight'], bio['birthdate'],
            bio['age'], bio['country'], bio['college'], bio['draft_year'],
            bio['draft_round'], bio['draft_pick'], bio['years_experience'],
            bio['jersey_number'], bio['headshot_url'], datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def save_games_to_db(self, games: List[Dict]) -> int:
        """Save games to database (APPEND ONLY - no overwrite)"""
        if not games:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        new_games = 0
        for game in games:
            game_key = f"{game['player_id']}_{game['game_id']}"
            
            # Skip if game already exists
            if game_key in self.existing_games:
                continue
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO player_game_logs 
                    (player_id, player_name, game_id, game_date, matchup, opponent,
                     home_away, result, minutes, points, rebounds, assists, steals,
                     blocks, turnovers, fg_made, fg_attempted, fg_pct, fg3_made,
                     fg3_attempted, fg3_pct, ft_made, ft_attempted, ft_pct, plus_minus,
                     fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game['player_id'], game['player_name'], game['game_id'],
                    game['game_date'], game['matchup'], game['opponent'],
                    game['home_away'], game['result'], game['minutes'],
                    game['points'], game['rebounds'], game['assists'],
                    game['steals'], game['blocks'], game['turnovers'],
                    game['fg_made'], game['fg_attempted'], game['fg_pct'],
                    game['fg3_made'], game['fg3_attempted'], game['fg3_pct'],
                    game['ft_made'], game['ft_attempted'], game['ft_pct'],
                    game['plus_minus'], datetime.now().isoformat()
                ))
                
                if cursor.rowcount > 0:
                    new_games += 1
                    self.existing_games.add(game_key)
                    
            except sqlite3.IntegrityError:
                pass  # Game already exists
        
        conn.commit()
        conn.close()
        return new_games
    
    def update_rolling_averages(self, player_id: str, player_name: str, games: List[Dict]):
        """Calculate and save rolling averages from game data"""
        if not games:
            return
        
        n = len(games)
        
        # Calculate averages
        avg_points = sum(g['points'] for g in games) / n
        avg_rebounds = sum(g['rebounds'] for g in games) / n
        avg_assists = sum(g['assists'] for g in games) / n
        avg_steals = sum(g['steals'] for g in games) / n
        avg_blocks = sum(g['blocks'] for g in games) / n
        avg_minutes = sum(g['minutes'] for g in games) / n
        
        # FG% average (weighted by attempts)
        total_fgm = sum(g['fg_made'] for g in games)
        total_fga = sum(g['fg_attempted'] for g in games)
        avg_fg_pct = total_fgm / total_fga if total_fga > 0 else 0
        
        total_fg3m = sum(g['fg3_made'] for g in games)
        total_fg3a = sum(g['fg3_attempted'] for g in games)
        avg_fg3_pct = total_fg3m / total_fg3a if total_fg3a > 0 else 0
        
        # Detect streaks (hot/cold based on recent games)
        recent_3 = games[:3] if len(games) >= 3 else games
        avg_recent = sum(g['points'] for g in recent_3) / len(recent_3)
        
        hot_streak = 1 if avg_recent > avg_points * 1.2 else 0
        cold_streak = 1 if avg_recent < avg_points * 0.8 else 0
        
        trend = 'hot' if hot_streak else 'cold' if cold_streak else 'neutral'
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO player_rolling_averages
            (player_id, player_name, last_n_games, avg_points, avg_rebounds,
             avg_assists, avg_steals, avg_blocks, avg_minutes, avg_fg_pct,
             avg_fg3_pct, hot_streak, cold_streak, trend, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player_id, player_name, n,
            round(avg_points, 1), round(avg_rebounds, 1), round(avg_assists, 1),
            round(avg_steals, 1), round(avg_blocks, 1), round(avg_minutes, 1),
            round(avg_fg_pct, 3), round(avg_fg3_pct, 3),
            hot_streak, cold_streak, trend, datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def append_to_csv(self, games: List[Dict]):
        """Append games to CSV (never overwrites)"""
        file_exists = self.games_csv.exists()
        
        with open(self.games_csv, 'a', newline='', encoding='utf-8') as f:
            fieldnames = list(games[0].keys()) + ['fetched_at']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            for game in games:
                game_key = f"{game['player_id']}_{game['game_id']}"
                # Check if already in file (simplified check)
                row = {**game, 'fetched_at': datetime.now().isoformat()}
                writer.writerow(row)
    
    def fetch_all(self):
        """Main entry: fetch game logs for all players"""
        print("\n" + "="*70)
        print("🏀 NBA GAME LOG FETCHER")
        print(f"   Last {self.games_per_player} games per player")
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Rate limit: {self.min_delay}-{self.max_delay}s")
        print(f"⏰ Timeouts: {self.timeout[0]}s connect, {self.timeout[1]}s read")
        print("="*70)
        
        # Get player list
        players = self.get_player_list()
        if not players:
            print("❌ Failed to get player list")
            return
        
        # Filter out completed
        remaining = [p for p in players if p['player_id'] not in self.completed_players]
        print(f"\n📊 {len(remaining)} players remaining to fetch")
        
        if not remaining:
            print("✅ All players already fetched!")
            return
        
        # Estimate time
        avg_wait = (self.min_delay + self.max_delay) / 2
        est_min = (len(remaining) * avg_wait) / 60
        print(f"⏰ Estimated time: ~{est_min:.0f} minutes")
        print("-"*70)
        
        total_new_games = 0
        
        for i, player in enumerate(remaining):
            player_id = player['player_id']
            player_name = player['name']
            
            print(f"[{i+1}/{len(remaining)}] {player_name}...", end=" ")
            
            # Fetch game logs
            games = self.get_player_game_log(player_id, player_name)
            
            # Also fetch player bio (height, weight, age, headshot) every player
            bio = self.get_player_bio(player_id, player_name)
            if bio:
                self.save_player_bio(bio)
            
            if games:
                # Save to database (append only)
                new_games = self.save_games_to_db(games)
                total_new_games += new_games
                
                # Update rolling averages
                self.update_rolling_averages(player_id, player_name, games)
                
                # Append to CSV
                if new_games > 0:
                    self.append_to_csv(games[:new_games])
                
                avg_pts = sum(g['points'] for g in games) / len(games)
                bio_info = f", {bio['height']}, {bio['weight']}lbs" if bio else ""
                print(f"✅ {len(games)} games, {new_games} new, avg {avg_pts:.1f} PPG{bio_info}")
            else:
                print("❌ No game data" + (" (bio saved)" if bio else ""))
            
            self.completed_players.add(player_id)
            
            # Save progress every 20 players
            if (i + 1) % 20 == 0:
                self._save_progress()
                print(f"    💾 Progress saved ({len(self.completed_players)} total)")
        
        # Final save
        self._save_progress()
        
        # Summary
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print(f"   Players processed: {len(remaining)}")
        print(f"   New games saved: {total_new_games}")
        print(f"   Errors: {len(self.errors)}")
        print(f"   Database: {self.db_path}")
        print(f"   CSV: {self.games_csv}")
        print(f"   Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    data_dir = script_dir / 'data' / 'fetched'
    
    print(f"📁 Database: {db_path}")
    print(f"📁 Output dir: {data_dir}")
    
    # Fetch last 15 games per player
    fetcher = NBAGameLogFetcher(str(db_path), str(data_dir), games_per_player=15)
    fetcher.fetch_all()
    
    print("\n✅ Complete!")
