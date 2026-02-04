"""
NBA Today's Games Fetcher - Players in Today's Games Only
Fast focused fetch for players playing TODAY
Includes: game logs, bio (height/weight/age), headshots
"""

import requests
import time
import random
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core.config import CURRENT_SEASON

class NBATodayFetcher:
    """Fetch data only for players in today's games"""
    
    BASE_URL = "https://stats.nba.com/stats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
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
    TEAMS_REV = {v: k for k, v in TEAMS.items()}
    
    def __init__(self, db_path: str, data_dir: str):
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.timeout = (15, 60)
        
        self.min_delay = 10.0
        self.max_delay = 18.0
        
        self.run_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.errors = []
        
        self._init_db()
    
    def _init_db(self):
        """Create tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_game_logs (
                player_id TEXT, game_id TEXT, game_date TEXT,
                opponent TEXT, result TEXT, points INTEGER,
                rebounds INTEGER, assists INTEGER, minutes INTEGER,
                fg_pct REAL, fetched_at TEXT,
                PRIMARY KEY (player_id, game_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_bio (
                player_id TEXT PRIMARY KEY, player_name TEXT, team TEXT,
                position TEXT, height TEXT, weight INTEGER, age INTEGER,
                country TEXT, college TEXT, headshot_url TEXT, updated_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_rolling_averages (
                player_id TEXT PRIMARY KEY, player_name TEXT,
                last_n_games INTEGER, avg_points REAL, avg_rebounds REAL,
                avg_assists REAL, trend TEXT, updated_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def wait(self):
        """Wait with jitter"""
        w = random.uniform(self.min_delay, self.max_delay)
        if random.random() < 0.1:
            w += random.uniform(10, 25)
        print(f"⏳{w:.0f}s", end="... ")
        time.sleep(w)
    
    def make_request(self, url: str, params: dict) -> Optional[dict]:
        """Make request"""
        for attempt in range(3):
            try:
                self.wait()
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:
                    print("🚫 Rate limit, 5min wait...")
                    time.sleep(300)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                print(f"❌{attempt+1}/3", end=" ")
                if attempt < 2:
                    time.sleep(30)
        return None
    
    def get_todays_games(self) -> List[Dict]:
        """Get today's scheduled games"""
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"\n📅 Fetching games for {today}...")
        
        data = self.make_request(f"{self.BASE_URL}/scoreboardv2", {
            'DayOffset': '0',
            'GameDate': today,
            'LeagueID': '00',
        })
        
        if not data:
            return []
        
        try:
            # GameHeader has game info
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
        except:
            return []
        
        games = []
        for row in rows:
            game = dict(zip(headers, row))
            games.append({
                'game_id': game.get('GAME_ID', ''),
                'home_team_id': game.get('HOME_TEAM_ID'),
                'away_team_id': game.get('VISITOR_TEAM_ID'),
            })
        
        print(f"   ✅ Found {len(games)} games today")
        return games
    
    def get_team_roster(self, team_id: int) -> List[Dict]:
        """Get roster for a team"""
        data = self.make_request(f"{self.BASE_URL}/commonteamroster", {
            'TeamID': team_id,
            'Season': CURRENT_SEASON,
        })
        
        if not data:
            return []
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
        except:
            return []
        
        players = []
        for row in rows:
            p = dict(zip(headers, row))
            players.append({
                'player_id': str(p.get('PLAYER_ID', '')),
                'name': p.get('PLAYER', ''),
                'team': self.TEAMS.get(team_id, ''),
                'position': p.get('POSITION', ''),
                'height': p.get('HEIGHT', ''),
                'weight': int(p.get('WEIGHT', 0) or 0),
                'age': int(p.get('AGE', 0) or 0),
            })
        
        return players
    
    def get_game_log(self, player_id: str) -> List[Dict]:
        """Get last 15 games"""
        data = self.make_request(f"{self.BASE_URL}/playergamelog", {
            'PlayerID': player_id,
            'Season': CURRENT_SEASON,
            'SeasonType': 'Regular Season',
        })
        
        if not data:
            return []
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet'][:15]
        except:
            return []
        
        games = []
        for row in rows:
            g = dict(zip(headers, row))
            matchup = g.get('MATCHUP', '')
            games.append({
                'game_id': str(g.get('Game_ID', '')),
                'game_date': g.get('GAME_DATE', ''),
                'opponent': matchup.split(' ')[-1] if matchup else '',
                'result': g.get('WL', ''),
                'points': int(g.get('PTS', 0) or 0),
                'rebounds': int(g.get('REB', 0) or 0),
                'assists': int(g.get('AST', 0) or 0),
                'minutes': int(g.get('MIN', 0) or 0),
                'fg_pct': float(g.get('FG_PCT', 0) or 0),
            })
        
        return games
    
    def save_player(self, player: Dict, games: List[Dict]):
        """Save player data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Save bio
        cursor.execute("""
            INSERT OR REPLACE INTO player_bio 
            (player_id, player_name, team, position, height, weight, age,
             headshot_url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player['player_id'], player['name'], player['team'],
            player['position'], player['height'], player['weight'],
            player['age'],
            f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player['player_id']}.png",
            datetime.now().isoformat()
        ))
        
        # Save games
        new_games = 0
        for g in games:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO player_game_logs
                    (player_id, game_id, game_date, opponent, result,
                     points, rebounds, assists, minutes, fg_pct, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player['player_id'], g['game_id'], g['game_date'],
                    g['opponent'], g['result'], g['points'], g['rebounds'],
                    g['assists'], g['minutes'], g['fg_pct'],
                    datetime.now().isoformat()
                ))
                if cursor.rowcount > 0:
                    new_games += 1
            except:
                pass
        
        # Rolling averages
        if games:
            n = len(games)
            cursor.execute("""
                INSERT OR REPLACE INTO player_rolling_averages
                (player_id, player_name, last_n_games, avg_points,
                 avg_rebounds, avg_assists, trend, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player['player_id'], player['name'], n,
                round(sum(g['points'] for g in games) / n, 1),
                round(sum(g['rebounds'] for g in games) / n, 1),
                round(sum(g['assists'] for g in games) / n, 1),
                'neutral', datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
        return new_games
    
    def fetch_all(self):
        """Main entry"""
        print("\n" + "="*60)
        print("🏀 NBA TODAY'S GAMES FETCHER")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Get today's games
        games = self.get_todays_games()
        if not games:
            print("❌ No games today or API error")
            return
        
        # Get teams playing today
        team_ids = set()
        for g in games:
            team_ids.add(g['home_team_id'])
            team_ids.add(g['away_team_id'])
        
        print(f"\n📋 {len(team_ids)} teams playing: ", end="")
        print(", ".join(self.TEAMS.get(t, '?') for t in team_ids))
        
        # Get rosters for all teams
        all_players = []
        for team_id in team_ids:
            team = self.TEAMS.get(team_id, 'UNK')
            print(f"\n🏀 Fetching {team} roster...", end=" ")
            roster = self.get_team_roster(team_id)
            if roster:
                all_players.extend(roster)
                print(f"✅ {len(roster)} players")
            else:
                print("❌ Failed")
        
        print(f"\n📊 Total: {len(all_players)} players to fetch")
        est_min = (len(all_players) * 15) / 60
        print(f"⏰ Estimated: ~{est_min:.0f} minutes")
        print("-"*60)
        
        total_games = 0
        skipped = 0
        
        for i, player in enumerate(all_players):
            pid = player['player_id']
            name = player['name']
            
            # Check if player already has 15 games (skip if so)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM player_game_logs WHERE player_id = ?
            """, (pid,))
            existing_games = cursor.fetchone()[0]
            conn.close()
            
            if existing_games >= 15:
                skipped += 1
                print(f"[{i+1}/{len(all_players)}] {name[:18]}... SKIP ({existing_games}g)")
                continue
            
            print(f"[{i+1}/{len(all_players)}] {name[:18]}...", end=" ")
            
            games = self.get_game_log(pid)
            
            if games:
                new = self.save_player(player, games)
                total_games += new
                avg = sum(g['points'] for g in games) / len(games)
                print(f"✅ {len(games)}g {new}new {avg:.1f}ppg {player['height']}")
            else:
                # Still save bio even without games
                self.save_player(player, [])
                print(f"⚠️ No games (bio saved)")
        
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print(f"   Players: {len(all_players)}")
        print(f"   Skipped (already had 15g): {skipped}")
        print(f"   New games saved: {total_games}")
        print(f"   Teams: {len(team_ids)}")
        print("="*60)


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    data_dir = script_dir / 'data' / 'fetched'
    
    fetcher = NBATodayFetcher(str(db_path), str(data_dir))
    fetcher.fetch_all()
