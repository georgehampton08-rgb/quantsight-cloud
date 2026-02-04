"""
NBA Data Fetcher - Fetches current stats for all active NBA players
Uses stats.nba.com API with rate limiting to behave like a real user
"""

import sqlite3
import requests
import time
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# All 30 NBA Teams with their IDs
NBA_TEAMS = {
    "ATL": {"id": "1610612737", "name": "Atlanta Hawks"},
    "BOS": {"id": "1610612738", "name": "Boston Celtics"},
    "BKN": {"id": "1610612751", "name": "Brooklyn Nets"},
    "CHA": {"id": "1610612766", "name": "Charlotte Hornets"},
    "CHI": {"id": "1610612741", "name": "Chicago Bulls"},
    "CLE": {"id": "1610612739", "name": "Cleveland Cavaliers"},
    "DAL": {"id": "1610612742", "name": "Dallas Mavericks"},
    "DEN": {"id": "1610612743", "name": "Denver Nuggets"},
    "DET": {"id": "1610612765", "name": "Detroit Pistons"},
    "GSW": {"id": "1610612744", "name": "Golden State Warriors"},
    "HOU": {"id": "1610612745", "name": "Houston Rockets"},
    "IND": {"id": "1610612754", "name": "Indiana Pacers"},
    "LAC": {"id": "1610612746", "name": "LA Clippers"},
    "LAL": {"id": "1610612747", "name": "Los Angeles Lakers"},
    "MEM": {"id": "1610612763", "name": "Memphis Grizzlies"},
    "MIA": {"id": "1610612748", "name": "Miami Heat"},
    "MIL": {"id": "1610612749", "name": "Milwaukee Bucks"},
    "MIN": {"id": "1610612750", "name": "Minnesota Timberwolves"},
    "NOP": {"id": "1610612740", "name": "New Orleans Pelicans"},
    "NYK": {"id": "1610612752", "name": "New York Knicks"},
    "OKC": {"id": "1610612760", "name": "Oklahoma City Thunder"},
    "ORL": {"id": "1610612753", "name": "Orlando Magic"},
    "PHI": {"id": "1610612755", "name": "Philadelphia 76ers"},
    "PHX": {"id": "1610612756", "name": "Phoenix Suns"},
    "POR": {"id": "1610612757", "name": "Portland Trail Blazers"},
    "SAC": {"id": "1610612758", "name": "Sacramento Kings"},
    "SAS": {"id": "1610612759", "name": "San Antonio Spurs"},
    "TOR": {"id": "1610612761", "name": "Toronto Raptors"},
    "UTA": {"id": "1610612762", "name": "Utah Jazz"},
    "WAS": {"id": "1610612764", "name": "Washington Wizards"},
}

class NBADataFetcher:
    """Fetches current NBA stats with natural human-like delays"""
    
    BASE_URL = "https://stats.nba.com/stats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Connection': 'keep-alive',
    }
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.stats_fetched = 0
        self.errors = []
    
    def human_delay(self, min_sec=1.5, max_sec=4.0):
        """Random delay to simulate human browsing"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def get_team_roster(self, team_id: str, team_abbr: str) -> List[Dict]:
        """Fetch current roster for a team"""
        url = f"{self.BASE_URL}/commonteamroster"
        params = {
            'LeagueID': '00',
            'Season': '2024-25',
            'TeamID': team_id
        }
        
        try:
            self.human_delay(2, 4)  # Longer delay between teams
            print(f"  📋 Fetching {team_abbr} roster...")
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            roster = []
            for row in rows:
                player = dict(zip(headers, row))
                roster.append({
                    'player_id': str(player.get('PLAYER_ID', '')),
                    'name': player.get('PLAYER', ''),
                    'position': player.get('POSITION', ''),
                    'jersey_number': player.get('NUM', ''),
                    'height': player.get('HEIGHT', ''),
                    'weight': player.get('WEIGHT', ''),
                    'age': player.get('AGE', ''),
                    'exp': player.get('EXP', ''),
                })
            
            return roster
        except Exception as e:
            print(f"  ❌ Error fetching {team_abbr} roster: {e}")
            self.errors.append(f"{team_abbr} roster: {e}")
            return []
    
    def get_player_stats(self, player_id: str, player_name: str) -> Optional[Dict]:
        """Fetch current season stats for a player"""
        url = f"{self.BASE_URL}/playercareerstats"
        params = {
            'PlayerID': player_id,
            'PerMode': 'PerGame'
        }
        
        try:
            self.human_delay(1.0, 2.5)  # Shorter delay for player stats
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            # Find 2024-25 season stats
            for row in rows:
                stats = dict(zip(headers, row))
                if stats.get('SEASON_ID') == '2024-25':
                    self.stats_fetched += 1
                    return {
                        'games': stats.get('GP', 0),
                        'points_avg': round(float(stats.get('PTS', 0) or 0), 1),
                        'rebounds_avg': round(float(stats.get('REB', 0) or 0), 1),
                        'assists_avg': round(float(stats.get('AST', 0) or 0), 1),
                        'steals_avg': round(float(stats.get('STL', 0) or 0), 1),
                        'blocks_avg': round(float(stats.get('BLK', 0) or 0), 1),
                        'fg_pct': round(float(stats.get('FG_PCT', 0) or 0), 3),
                        'three_p_pct': round(float(stats.get('FG3_PCT', 0) or 0), 3),
                        'ft_pct': round(float(stats.get('FT_PCT', 0) or 0), 3),
                        'minutes_avg': round(float(stats.get('MIN', 0) or 0), 1),
                    }
            
            return None  # No 2024-25 season data found
        except Exception as e:
            self.errors.append(f"{player_name}: {e}")
            return None
    
    def update_database(self, players: List[Dict]):
        """Update database with fetched player data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create/update tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_id TEXT PRIMARY KEY,
                name TEXT,
                team_id TEXT,
                position TEXT,
                height TEXT,
                weight TEXT,
                experience TEXT,
                status TEXT DEFAULT 'active'
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                season TEXT,
                games INTEGER,
                points_avg REAL,
                rebounds_avg REAL,
                assists_avg REAL,
                steals_avg REAL,
                blocks_avg REAL,
                fg_pct REAL,
                three_p_pct REAL,
                ft_pct REAL,
                minutes_avg REAL,
                updated_at TEXT,
                UNIQUE(player_id, season)
            )
        """)
        
        updated_count = 0
        for player in players:
            if not player.get('stats'):
                continue
            
            stats = player['stats']
            
            # Update player info
            cursor.execute("""
                INSERT OR REPLACE INTO players 
                (player_id, name, team_id, position, height, weight, experience, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
            """, (
                player['player_id'],
                player['name'],
                player['team'],
                player['position'],
                player['height'],
                player['weight'],
                player['exp']
            ))
            
            # Update stats
            cursor.execute("""
                INSERT OR REPLACE INTO player_stats 
                (player_id, season, games, points_avg, rebounds_avg, assists_avg, 
                 steals_avg, blocks_avg, fg_pct, three_p_pct, ft_pct, minutes_avg, updated_at)
                VALUES (?, '2024-25', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player['player_id'],
                stats['games'],
                stats['points_avg'],
                stats['rebounds_avg'],
                stats['assists_avg'],
                stats['steals_avg'],
                stats['blocks_avg'],
                stats['fg_pct'],
                stats['three_p_pct'],
                stats['ft_pct'],
                stats['minutes_avg'],
                datetime.now().isoformat()
            ))
            updated_count += 1
        
        conn.commit()
        conn.close()
        return updated_count
    
    def fetch_all_teams(self, teams_to_fetch: List[str] = None):
        """Fetch data for all (or specified) teams"""
        teams = teams_to_fetch or list(NBA_TEAMS.keys())
        all_players = []
        
        print(f"\n🏀 NBA Data Fetcher - Starting fetch for {len(teams)} teams")
        print(f"📅 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        for i, team_abbr in enumerate(teams):
            team_info = NBA_TEAMS[team_abbr]
            print(f"\n[{i+1}/{len(teams)}] {team_info['name']} ({team_abbr})")
            
            # Get roster
            roster = self.get_team_roster(team_info['id'], team_abbr)
            print(f"  ✅ Found {len(roster)} players")
            
            # Get stats for each player
            for j, player in enumerate(roster):
                print(f"    [{j+1}/{len(roster)}] {player['name']}...", end=" ", flush=True)
                stats = self.get_player_stats(player['player_id'], player['name'])
                
                if stats:
                    player['stats'] = stats
                    player['team'] = team_abbr
                    all_players.append(player)
                    print(f"✅ {stats['points_avg']} PPG")
                else:
                    print("⚠️ No 2024-25 stats")
            
            # Longer pause between teams
            if i < len(teams) - 1:
                pause = random.uniform(3, 6)
                print(f"  ⏳ Pausing {pause:.1f}s before next team...")
                time.sleep(pause)
        
        print("\n" + "=" * 60)
        print(f"📊 Summary:")
        print(f"   Teams processed: {len(teams)}")
        print(f"   Players with stats: {len(all_players)}")
        print(f"   Errors: {len(self.errors)}")
        
        # Update database
        print(f"\n💾 Updating database...")
        updated = self.update_database(all_players)
        print(f"   ✅ Updated {updated} player records")
        
        return all_players


if __name__ == '__main__':
    import os
    
    # Find database
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        exit(1)
    
    print(f"📁 Database: {db_path}")
    
    fetcher = NBADataFetcher(str(db_path))
    
    # Fetch all 30 teams
    fetcher.fetch_all_teams()
    
    print("\n✅ Complete!")
