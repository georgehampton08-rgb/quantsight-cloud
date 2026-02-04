"""
NBA Team Defense & Matchup Fetcher v2
=====================================
Fetches REAL team defense data and pace for matchup intelligence.
Uses the proper NBA API endpoints with robust error handling.
"""

import requests
import time
import random
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Add parent to path for centralized imports  
import sys
sys.path.insert(0, str(Path(__file__).parent))

try:
    from data_paths import get_db_path
except ImportError:
    get_db_path = lambda: Path(__file__).parent / 'data' / 'nba_data.db'


class TeamDefenseFetcher:
    """Fetch REAL team defensive stats with proper error handling"""
    
    BASE_URL = "https://stats.nba.com/stats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Connection': 'keep-alive',
    }
    
    # Team mapping
    TEAMS = {
        1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
        1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
        1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
        1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
        1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
        1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
        1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
        1610612762: "UTA", 1610612764: "WAS",
    }
    
    def __init__(self):
        self.db_path = get_db_path()
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._init_db()
        self.errors = []
    
    def _init_db(self):
        """Create/verify tables"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_defense (
                team_id TEXT PRIMARY KEY,
                team_abbr TEXT,
                team_name TEXT,
                conference TEXT,
                division TEXT,
                games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                def_rating REAL DEFAULT 0,
                opp_pts REAL DEFAULT 0,
                opp_fg_pct REAL DEFAULT 0,
                opp_fg3_pct REAL DEFAULT 0,
                opp_reb REAL DEFAULT 0,
                opp_ast REAL DEFAULT 0,
                steals REAL DEFAULT 0,
                blocks REAL DEFAULT 0,
                pace REAL DEFAULT 0,
                updated_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def wait(self, min_s=3, max_s=6):
        """Wait with jitter"""
        time.sleep(random.uniform(min_s, max_s))
    
    def fetch_with_retry(self, url: str, params: dict, retries: int = 3) -> Optional[dict]:
        """Fetch with retry and proper error handling"""
        for attempt in range(retries):
            try:
                self.wait()
                resp = self.session.get(url, params=params, timeout=(15, 45))
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                print(f"   ⏰ Timeout (attempt {attempt+1}/{retries})")
                if attempt < retries - 1:
                    self.wait(10, 20)  # Longer wait on retry
            except requests.exceptions.HTTPError as e:
                error = f"HTTP {e.response.status_code}: {e}"
                print(f"   ❌ {error}")
                self.errors.append(error)
                if e.response.status_code == 429:  # Rate limited
                    self.wait(30, 60)
                else:
                    break
            except Exception as e:
                print(f"   ❌ Error: {e}")
                self.errors.append(str(e))
                break
        return None
    
    def fetch_team_stats(self) -> List[Dict]:
        """
        Fetch team offensive stats - includes pace and points.
        The 'Base' measure type returns team's OWN stats, not opponent stats.
        """
        print("\n📊 Fetching team base stats (pace, points)...")
        
        data = self.fetch_with_retry(f"{self.BASE_URL}/leaguedashteamstats", {
            'Conference': '',
            'DateFrom': '',
            'DateTo': '',
            'Division': '',
            'GameScope': '',
            'GameSegment': '',
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
            'Season': '2024-25',
            'SeasonSegment': '',
            'SeasonType': 'Regular Season',
            'ShotClockRange': '',
            'StarterBench': '',
            'TeamID': '0',
            'TwoWay': '0',
            'VsConference': '',
            'VsDivision': '',
        })
        
        if not data:
            print("   ❌ Failed to fetch team stats")
            return []
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            print(f"   📋 Headers available: {headers[:10]}...")
        except (KeyError, IndexError) as e:
            print(f"   ❌ Malformed response: {e}")
            return []
        
        teams = []
        for row in rows:
            team = dict(zip(headers, row))
            team_id = team.get('TEAM_ID')
            abbr = self.TEAMS.get(team_id, 'UNK')
            
            # Extract available fields
            teams.append({
                'team_id': str(team_id),
                'team_abbr': abbr,
                'team_name': team.get('TEAM_NAME', ''),
                'games': team.get('GP', 0),
                'wins': team.get('W', 0),
                'losses': team.get('L', 0),
                # These are TEAM'S stats (not opponent)
                'pts': team.get('PTS', 0),
                'fg_pct': team.get('FG_PCT', 0),
                'reb': team.get('REB', 0),
                'ast': team.get('AST', 0),
                'stl': team.get('STL', 0),
                'blk': team.get('BLK', 0),
            })
        
        print(f"   ✅ Got base stats for {len(teams)} teams")
        return teams
    
    def fetch_advanced_stats(self) -> Dict[str, Dict]:
        """
        Fetch ADVANCED stats - includes DEF_RATING and PACE.
        This is the key endpoint for defense intelligence!
        """
        print("\n📊 Fetching advanced stats (DEF_RATING, PACE)...")
        
        data = self.fetch_with_retry(f"{self.BASE_URL}/leaguedashteamstats", {
            'Conference': '',
            'DateFrom': '',
            'DateTo': '',
            'Division': '',
            'GameScope': '',
            'GameSegment': '',
            'LastNGames': '0',
            'LeagueID': '00',
            'Location': '',
            'MeasureType': 'Advanced',  # ADVANCED - has DEF_RATING and PACE
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
            'Season': '2024-25',
            'SeasonSegment': '',
            'SeasonType': 'Regular Season',
            'ShotClockRange': '',
            'StarterBench': '',
            'TeamID': '0',
            'TwoWay': '0',
            'VsConference': '',
            'VsDivision': '',
        })
        
        if not data:
            print("   ❌ Failed to fetch advanced stats")
            return {}
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            print(f"   📋 Advanced headers: {headers[:12]}...")
        except (KeyError, IndexError) as e:
            print(f"   ❌ Malformed response: {e}")
            return {}
        
        # Build lookup by team_id
        advanced = {}
        for row in rows:
            team = dict(zip(headers, row))
            team_id = str(team.get('TEAM_ID'))
            
            advanced[team_id] = {
                'def_rating': team.get('DEF_RATING', 0),
                'off_rating': team.get('OFF_RATING', 0),
                'net_rating': team.get('NET_RATING', 0),
                'pace': team.get('PACE', 0),
                'poss': team.get('POSS', 0),
            }
        
        print(f"   ✅ Got advanced stats for {len(advanced)} teams")
        
        # Show sample
        if advanced:
            sample_id = list(advanced.keys())[0]
            sample = advanced[sample_id]
            print(f"   📈 Sample: DEF_RATING={sample['def_rating']}, PACE={sample['pace']}")
        
        return advanced
    
    def fetch_opponent_shooting(self) -> Dict[str, Dict]:
        """
        Fetch Opponent Shooting stats - what each team ALLOWS.
        This gives us OPP_FG_PCT, OPP_FG3_PCT.
        """
        print("\n📊 Fetching opponent shooting stats...")
        
        data = self.fetch_with_retry(f"{self.BASE_URL}/leaguedashteamstats", {
            'Conference': '',
            'DateFrom': '',
            'DateTo': '',
            'Division': '',
            'GameScope': '',
            'GameSegment': '',
            'LastNGames': '0',
            'LeagueID': '00',
            'Location': '',
            'MeasureType': 'Opponent',  # OPPONENT - what teams allow
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
            'Season': '2024-25',
            'SeasonSegment': '',
            'SeasonType': 'Regular Season',
            'ShotClockRange': '',
            'StarterBench': '',
            'TeamID': '0',
            'TwoWay': '0',
            'VsConference': '',
            'VsDivision': '',
        })
        
        if not data:
            print("   ❌ Failed to fetch opponent stats")
            return {}
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            print(f"   📋 Opponent headers: {headers[:12]}...")
        except (KeyError, IndexError) as e:
            print(f"   ❌ Malformed response: {e}")
            return {}
        
        # Build lookup by team_id
        opp_stats = {}
        for row in rows:
            team = dict(zip(headers, row))
            team_id = str(team.get('TEAM_ID'))
            
            opp_stats[team_id] = {
                'opp_pts': team.get('OPP_PTS', 0) or team.get('PTS', 0),  # Some endpoints rename
                'opp_fg_pct': team.get('OPP_FG_PCT', 0) or team.get('FG_PCT', 0),
                'opp_fg3_pct': team.get('OPP_FG3_PCT', 0) or team.get('FG3_PCT', 0),
                'opp_reb': team.get('OPP_REB', 0) or team.get('REB', 0),
                'opp_ast': team.get('OPP_AST', 0) or team.get('AST', 0),
            }
        
        print(f"   ✅ Got opponent stats for {len(opp_stats)} teams")
        
        # Show sample
        if opp_stats:
            sample_id = list(opp_stats.keys())[0]
            sample = opp_stats[sample_id]
            print(f"   📈 Sample: OPP_PTS={sample['opp_pts']}, OPP_FG%={sample['opp_fg_pct']}")
        
        return opp_stats
    
    def merge_and_save(self, base_teams: List[Dict], advanced: Dict, opp_stats: Dict):
        """Merge all data and save to database"""
        print("\n💾 Merging and saving team defense data...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        saved = 0
        for team in base_teams:
            team_id = team['team_id']
            adv = advanced.get(team_id, {})
            opp = opp_stats.get(team_id, {})
            
            # Skip if no real data
            if not adv and not opp:
                continue
            
            cursor.execute("""
                INSERT OR REPLACE INTO team_defense
                (team_id, team_abbr, team_name, games, wins, losses,
                 def_rating, opp_pts, opp_fg_pct, opp_fg3_pct, opp_reb, opp_ast,
                 steals, blocks, pace, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team_id,
                team['team_abbr'],
                team['team_name'],
                team['games'],
                team['wins'],
                team['losses'],
                adv.get('def_rating', 0),
                opp.get('opp_pts', 0),
                opp.get('opp_fg_pct', 0),
                opp.get('opp_fg3_pct', 0),
                opp.get('opp_reb', 0),
                opp.get('opp_ast', 0),
                team.get('stl', 0),
                team.get('blk', 0),
                adv.get('pace', 0),
                datetime.now().isoformat()
            ))
            saved += 1
        
        conn.commit()
        conn.close()
        
        print(f"   ✅ Saved {saved} teams with defense data")
        return saved
    
    def calculate_player_vs_team(self):
        """Calculate player vs team from game logs"""
        print("\n📊 Calculating player vs team matchup history...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO player_vs_team
                (player_id, opponent, games_played, avg_pts, avg_reb, avg_ast, avg_fg_pct, last_game_date, updated_at)
                SELECT 
                    player_id,
                    opponent,
                    COUNT(*) as games_played,
                    ROUND(AVG(points), 1) as avg_pts,
                    ROUND(AVG(rebounds), 1) as avg_reb,
                    ROUND(AVG(assists), 1) as avg_ast,
                    ROUND(AVG(fg_pct), 3) as avg_fg_pct,
                    MAX(game_date) as last_game_date,
                    datetime('now') as updated_at
                FROM player_game_logs
                WHERE opponent IS NOT NULL AND opponent != ''
                GROUP BY player_id, opponent
            """)
            
            count = cursor.rowcount
            conn.commit()
            print(f"   ✅ Calculated {count} player vs team matchups")
        except sqlite3.OperationalError as e:
            print(f"   ⚠️  player_game_logs table not ready: {e}")
            count = 0
        
        conn.close()
        return count
    
    def run(self):
        """Main entry point"""
        print("\n" + "="*60)
        print("🏀 NBA TEAM DEFENSE FETCHER v2")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Step 1: Fetch base team stats
        base_teams = self.fetch_team_stats()
        if not base_teams:
            print("\n❌ FAILED: Could not fetch base team stats")
            return False
        
        # Step 2: Fetch advanced stats (DEF_RATING, PACE)
        advanced = self.fetch_advanced_stats()
        
        # Step 3: Fetch opponent stats (what teams allow)
        opp_stats = self.fetch_opponent_shooting()
        
        # Step 4: Merge and save
        saved = self.merge_and_save(base_teams, advanced, opp_stats)
        
        # Step 5: Calculate player vs team from game logs
        self.calculate_player_vs_team()
        
        # Summary
        print("\n" + "="*60)
        if saved > 0:
            print(f"✅ SUCCESS: Saved defense data for {saved} teams")
            print("   DefenseMatrix and PaceEngine can now use REAL data")
        else:
            print("❌ FAILED: No teams saved")
        
        if self.errors:
            print(f"\n⚠️  Errors encountered: {len(self.errors)}")
            for e in self.errors[:5]:
                print(f"   - {e}")
        
        print("="*60)
        return saved > 0


if __name__ == '__main__':
    fetcher = TeamDefenseFetcher()
    fetcher.run()
