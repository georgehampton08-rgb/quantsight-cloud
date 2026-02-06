"""
Comprehensive NBA Team Stats Collector
=====================================
Fetches ALL possible team statistics from NBA API:
- Base Stats (offensive metrics)
- Advanced Stats (pace, ratings)
- Defensive Stats (opponent metrics)
- Four Factors (efficiency metrics)
- Scoring Stats (points breakdown)
- Misc Stats (technicals, fouls, etc.)

All columns use lowercase for database compatibility.
Includes proper rate limiting, timeouts, and resilience.
"""

import requests
import time
import random
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Add parent to path for centralized imports  
import sys
sys.path.insert(0, str(Path(__file__).parent))

try:
    from data_paths import get_db_path
except ImportError:
    get_db_path = lambda: Path(__file__).parent / 'data' / 'nba_data.db'


class ComprehensiveTeamStatsCollector:
    """
    Collect ALL available team statistics from NBA API.
    Uses proper rate limiting, retry logic, and resilience.
    """
    
    BASE_URL = "https://stats.nba.com/stats"
    CURRENT_SEASON = "2025-26"  # Update for current season
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Host': 'stats.nba.com',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }
    
    # All 30 NBA Teams
    TEAMS = {
        1610612737: {"abbr": "ATL", "name": "Atlanta Hawks", "conference": "East", "division": "Southeast"},
        1610612738: {"abbr": "BOS", "name": "Boston Celtics", "conference": "East", "division": "Atlantic"},
        1610612751: {"abbr": "BKN", "name": "Brooklyn Nets", "conference": "East", "division": "Atlantic"},
        1610612766: {"abbr": "CHA", "name": "Charlotte Hornets", "conference": "East", "division": "Southeast"},
        1610612741: {"abbr": "CHI", "name": "Chicago Bulls", "conference": "East", "division": "Central"},
        1610612739: {"abbr": "CLE", "name": "Cleveland Cavaliers", "conference": "East", "division": "Central"},
        1610612742: {"abbr": "DAL", "name": "Dallas Mavericks", "conference": "West", "division": "Southwest"},
        1610612743: {"abbr": "DEN", "name": "Denver Nuggets", "conference": "West", "division": "Northwest"},
        1610612765: {"abbr": "DET", "name": "Detroit Pistons", "conference": "East", "division": "Central"},
        1610612744: {"abbr": "GSW", "name": "Golden State Warriors", "conference": "West", "division": "Pacific"},
        1610612745: {"abbr": "HOU", "name": "Houston Rockets", "conference": "West", "division": "Southwest"},
        1610612754: {"abbr": "IND", "name": "Indiana Pacers", "conference": "East", "division": "Central"},
        1610612746: {"abbr": "LAC", "name": "LA Clippers", "conference": "West", "division": "Pacific"},
        1610612747: {"abbr": "LAL", "name": "Los Angeles Lakers", "conference": "West", "division": "Pacific"},
        1610612763: {"abbr": "MEM", "name": "Memphis Grizzlies", "conference": "West", "division": "Southwest"},
        1610612748: {"abbr": "MIA", "name": "Miami Heat", "conference": "East", "division": "Southeast"},
        1610612749: {"abbr": "MIL", "name": "Milwaukee Bucks", "conference": "East", "division": "Central"},
        1610612750: {"abbr": "MIN", "name": "Minnesota Timberwolves", "conference": "West", "division": "Northwest"},
        1610612740: {"abbr": "NOP", "name": "New Orleans Pelicans", "conference": "West", "division": "Southwest"},
        1610612752: {"abbr": "NYK", "name": "New York Knicks", "conference": "East", "division": "Atlantic"},
        1610612760: {"abbr": "OKC", "name": "Oklahoma City Thunder", "conference": "West", "division": "Northwest"},
        1610612753: {"abbr": "ORL", "name": "Orlando Magic", "conference": "East", "division": "Southeast"},
        1610612755: {"abbr": "PHI", "name": "Philadelphia 76ers", "conference": "East", "division": "Atlantic"},
        1610612756: {"abbr": "PHX", "name": "Phoenix Suns", "conference": "West", "division": "Pacific"},
        1610612757: {"abbr": "POR", "name": "Portland Trail Blazers", "conference": "West", "division": "Northwest"},
        1610612758: {"abbr": "SAC", "name": "Sacramento Kings", "conference": "West", "division": "Pacific"},
        1610612759: {"abbr": "SAS", "name": "San Antonio Spurs", "conference": "West", "division": "Southwest"},
        1610612761: {"abbr": "TOR", "name": "Toronto Raptors", "conference": "East", "division": "Atlantic"},
        1610612762: {"abbr": "UTA", "name": "Utah Jazz", "conference": "West", "division": "Northwest"},
        1610612764: {"abbr": "WAS", "name": "Washington Wizards", "conference": "East", "division": "Southeast"},
    }
    
    # MeasureType options for leaguedashteamstats endpoint
    MEASURE_TYPES = {
        'base': 'Base',           # Standard box score stats
        'advanced': 'Advanced',   # Advanced metrics (ORtg, DRtg, PACE, etc.)
        'misc': 'Misc',           # Misc stats (2nd chance, fast break, etc.)
        'four_factors': 'Four Factors',  # EFG%, TOV%, ORB%, FT/FGA
        'scoring': 'Scoring',     # Points breakdown by type
        'opponent': 'Opponent',   # What opponents score against
        'usage': 'Usage',         # Usage rate stats
        'defense': 'Defense',     # Defensive stats
    }
    
    def __init__(self, test_mode: bool = False):
        self.db_path = get_db_path()
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.errors = []
        self.test_mode = test_mode
        self.stats_collected = {}
        
        # Ensure data directories exist
        self.data_dir = Path(__file__).parent / 'data' / 'team_stats'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Create comprehensive team_stats table with all lowercase columns"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Drop and recreate for fresh schema
        cursor.execute("DROP TABLE IF EXISTS team_stats_comprehensive")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_stats_comprehensive (
                team_id TEXT PRIMARY KEY,
                team_abbr TEXT NOT NULL,
                team_name TEXT,
                conference TEXT,
                division TEXT,
                
                -- Record
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                win_pct REAL DEFAULT 0,
                
                -- Base Offensive Stats
                pts REAL DEFAULT 0,
                fgm REAL DEFAULT 0,
                fga REAL DEFAULT 0,
                fg_pct REAL DEFAULT 0,
                fg3m REAL DEFAULT 0,
                fg3a REAL DEFAULT 0,
                fg3_pct REAL DEFAULT 0,
                ftm REAL DEFAULT 0,
                fta REAL DEFAULT 0,
                ft_pct REAL DEFAULT 0,
                oreb REAL DEFAULT 0,
                dreb REAL DEFAULT 0,
                reb REAL DEFAULT 0,
                ast REAL DEFAULT 0,
                tov REAL DEFAULT 0,
                stl REAL DEFAULT 0,
                blk REAL DEFAULT 0,
                pf REAL DEFAULT 0,
                plus_minus REAL DEFAULT 0,
                
                -- Advanced Stats
                off_rating REAL DEFAULT 0,
                def_rating REAL DEFAULT 0,
                net_rating REAL DEFAULT 0,
                pace REAL DEFAULT 0,
                pie REAL DEFAULT 0,
                ast_pct REAL DEFAULT 0,
                ast_tov REAL DEFAULT 0,
                ast_ratio REAL DEFAULT 0,
                oreb_pct REAL DEFAULT 0,
                dreb_pct REAL DEFAULT 0,
                reb_pct REAL DEFAULT 0,
                tov_pct REAL DEFAULT 0,
                efg_pct REAL DEFAULT 0,
                ts_pct REAL DEFAULT 0,
                poss REAL DEFAULT 0,
                
                -- Four Factors
                efg_pct_four REAL DEFAULT 0,
                fta_rate REAL DEFAULT 0,
                tov_pct_four REAL DEFAULT 0,
                oreb_pct_four REAL DEFAULT 0,
                opp_efg_pct REAL DEFAULT 0,
                opp_fta_rate REAL DEFAULT 0,
                opp_tov_pct REAL DEFAULT 0,
                opp_oreb_pct REAL DEFAULT 0,
                
                -- Scoring Stats
                pct_pts_2pt REAL DEFAULT 0,
                pct_pts_2pt_mid REAL DEFAULT 0,
                pct_pts_3pt REAL DEFAULT 0,
                pct_pts_fb REAL DEFAULT 0,
                pct_pts_ft REAL DEFAULT 0,
                pct_pts_off_tov REAL DEFAULT 0,
                pct_pts_paint REAL DEFAULT 0,
                pct_ast_2pm REAL DEFAULT 0,
                pct_uast_2pm REAL DEFAULT 0,
                pct_ast_3pm REAL DEFAULT 0,
                pct_uast_3pm REAL DEFAULT 0,
                pct_ast_fgm REAL DEFAULT 0,
                pct_uast_fgm REAL DEFAULT 0,
                
                -- Misc Stats
                pts_off_tov REAL DEFAULT 0,
                pts_2nd_chance REAL DEFAULT 0,
                pts_fb REAL DEFAULT 0,
                pts_paint REAL DEFAULT 0,
                opp_pts_off_tov REAL DEFAULT 0,
                opp_pts_2nd_chance REAL DEFAULT 0,
                opp_pts_fb REAL DEFAULT 0,
                opp_pts_paint REAL DEFAULT 0,
                
                -- Opponent Stats (Defense)
                opp_fgm REAL DEFAULT 0,
                opp_fga REAL DEFAULT 0,
                opp_fg_pct REAL DEFAULT 0,
                opp_fg3m REAL DEFAULT 0,
                opp_fg3a REAL DEFAULT 0,
                opp_fg3_pct REAL DEFAULT 0,
                opp_ftm REAL DEFAULT 0,
                opp_fta REAL DEFAULT 0,
                opp_ft_pct REAL DEFAULT 0,
                opp_oreb REAL DEFAULT 0,
                opp_dreb REAL DEFAULT 0,
                opp_reb REAL DEFAULT 0,
                opp_ast REAL DEFAULT 0,
                opp_tov REAL DEFAULT 0,
                opp_stl REAL DEFAULT 0,
                opp_blk REAL DEFAULT 0,
                opp_pf REAL DEFAULT 0,
                opp_pts REAL DEFAULT 0,
                opp_plus_minus REAL DEFAULT 0,
                
                -- Metadata
                season TEXT,
                data_source TEXT DEFAULT 'nba_api',
                updated_at TEXT,
                raw_data_json TEXT
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_stats_abbr ON team_stats_comprehensive(team_abbr)")
        
        conn.commit()
        conn.close()
        print("✅ Database table 'team_stats_comprehensive' initialized")
    
    def wait(self, min_s: float = 2.0, max_s: float = 4.0):
        """Wait with jitter to avoid rate limiting"""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)
    
    def fetch_with_retry(self, url: str, params: dict, retries: int = 3) -> Optional[dict]:
        """Fetch with retry logic, timeouts, and resilience"""
        for attempt in range(retries):
            try:
                self.wait()
                print(f"      Attempt {attempt+1}/{retries}...", end=" ")
                
                resp = self.session.get(url, params=params, timeout=(15, 60))
                resp.raise_for_status()
                
                data = resp.json()
                print("✓")
                return data
                
            except requests.exceptions.Timeout:
                print(f"⏰ Timeout")
                if attempt < retries - 1:
                    self.wait(10, 20)
                    
            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP {e.response.status_code}"
                print(f"❌ {error_msg}")
                self.errors.append(f"{url}: {error_msg}")
                
                if e.response.status_code == 429:  # Rate limited
                    print("      Rate limited - waiting 60s...")
                    self.wait(60, 90)
                elif e.response.status_code >= 500:
                    self.wait(15, 30)
                else:
                    break
                    
            except requests.exceptions.ConnectionError as e:
                print(f"🔌 Connection error")
                self.errors.append(f"{url}: Connection error")
                if attempt < retries - 1:
                    self.wait(10, 20)
                    
            except Exception as e:
                print(f"❌ {type(e).__name__}: {e}")
                self.errors.append(f"{url}: {e}")
                break
        
        print(f"      ⚠️ Skipping after {retries} failed attempts")
        return None
    
    def _build_params(self, measure_type: str) -> dict:
        """Build standard params for leaguedashteamstats endpoint"""
        return {
            'Conference': '',
            'DateFrom': '',
            'DateTo': '',
            'Division': '',
            'GameScope': '',
            'GameSegment': '',
            'Height': '',
            'LastNGames': '0',
            'LeagueID': '00',
            'Location': '',
            'MeasureType': measure_type,
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
            'Season': self.CURRENT_SEASON,
            'SeasonSegment': '',
            'SeasonType': 'Regular Season',
            'ShotClockRange': '',
            'StarterBench': '',
            'TeamID': '0',
            'TwoWay': '0',
            'VsConference': '',
            'VsDivision': '',
        }
    
    def _parse_response(self, data: dict) -> List[Dict]:
        """Parse NBA API response into list of dicts with lowercase keys"""
        try:
            result_set = data['resultSets'][0]
            headers = [h.lower() for h in result_set['headers']]  # Lowercase!
            rows = result_set['rowSet']
            
            teams = []
            for row in rows:
                team_dict = dict(zip(headers, row))
                teams.append(team_dict)
            
            return teams
        except (KeyError, IndexError) as e:
            print(f"   ⚠️ Failed to parse response: {e}")
            return []
    
    def fetch_base_stats(self) -> Dict[str, Dict]:
        """Fetch base box score stats for all teams"""
        print("\n📊 Fetching BASE stats (box score)...")
        
        data = self.fetch_with_retry(
            f"{self.BASE_URL}/leaguedashteamstats",
            self._build_params('Base')
        )
        
        if not data:
            return {}
        
        teams = self._parse_response(data)
        result = {str(t.get('team_id')): t for t in teams}
        print(f"   ✅ Got base stats for {len(result)} teams")
        return result
    
    def fetch_advanced_stats(self) -> Dict[str, Dict]:
        """Fetch advanced stats (ORtg, DRtg, PACE, PIE, etc.)"""
        print("\n📊 Fetching ADVANCED stats (ratings, pace)...")
        
        data = self.fetch_with_retry(
            f"{self.BASE_URL}/leaguedashteamstats",
            self._build_params('Advanced')
        )
        
        if not data:
            return {}
        
        teams = self._parse_response(data)
        result = {str(t.get('team_id')): t for t in teams}
        print(f"   ✅ Got advanced stats for {len(result)} teams")
        return result
    
    def fetch_four_factors(self) -> Dict[str, Dict]:
        """Fetch Four Factors stats (eFG%, TOV%, ORB%, FT/FGA)"""
        print("\n📊 Fetching FOUR FACTORS stats...")
        
        data = self.fetch_with_retry(
            f"{self.BASE_URL}/leaguedashteamstats",
            self._build_params('Four Factors')
        )
        
        if not data:
            return {}
        
        teams = self._parse_response(data)
        result = {str(t.get('team_id')): t for t in teams}
        print(f"   ✅ Got four factors for {len(result)} teams")
        return result
    
    def fetch_misc_stats(self) -> Dict[str, Dict]:
        """Fetch misc stats (2nd chance pts, fast break pts, etc.)"""
        print("\n📊 Fetching MISC stats (2nd chance, fast break)...")
        
        data = self.fetch_with_retry(
            f"{self.BASE_URL}/leaguedashteamstats",
            self._build_params('Misc')
        )
        
        if not data:
            return {}
        
        teams = self._parse_response(data)
        result = {str(t.get('team_id')): t for t in teams}
        print(f"   ✅ Got misc stats for {len(result)} teams")
        return result
    
    def fetch_scoring_stats(self) -> Dict[str, Dict]:
        """Fetch scoring breakdown stats"""
        print("\n📊 Fetching SCORING stats (points breakdown)...")
        
        data = self.fetch_with_retry(
            f"{self.BASE_URL}/leaguedashteamstats",
            self._build_params('Scoring')
        )
        
        if not data:
            return {}
        
        teams = self._parse_response(data)
        result = {str(t.get('team_id')): t for t in teams}
        print(f"   ✅ Got scoring stats for {len(result)} teams")
        return result
    
    def fetch_opponent_stats(self) -> Dict[str, Dict]:
        """Fetch opponent stats (what teams allow - defensive)"""
        print("\n📊 Fetching OPPONENT stats (defensive metrics)...")
        
        data = self.fetch_with_retry(
            f"{self.BASE_URL}/leaguedashteamstats",
            self._build_params('Opponent')
        )
        
        if not data:
            return {}
        
        teams = self._parse_response(data)
        result = {str(t.get('team_id')): t for t in teams}
        print(f"   ✅ Got opponent stats for {len(result)} teams")
        return result
    
    def merge_all_stats(self, base: Dict, advanced: Dict, four_factors: Dict, 
                        misc: Dict, scoring: Dict, opponent: Dict) -> List[Dict]:
        """Merge all stats into comprehensive team records"""
        print("\n🔗 Merging all statistics...")
        
        merged_teams = []
        
        for team_id, team_info in self.TEAMS.items():
            team_id_str = str(team_id)
            
            # Get data from each source
            base_data = base.get(team_id_str, {})
            adv_data = advanced.get(team_id_str, {})
            ff_data = four_factors.get(team_id_str, {})
            misc_data = misc.get(team_id_str, {})
            score_data = scoring.get(team_id_str, {})
            opp_data = opponent.get(team_id_str, {})
            
            # Skip if no base data
            if not base_data:
                print(f"   ⚠️ No data for {team_info['abbr']}")
                continue
            
            # Build comprehensive record (all lowercase)
            team = {
                # Identity
                'team_id': team_id_str,
                'team_abbr': team_info['abbr'],
                'team_name': team_info['name'],
                'conference': team_info['conference'],
                'division': team_info['division'],
                
                # Record
                'games_played': base_data.get('gp', 0),
                'wins': base_data.get('w', 0),
                'losses': base_data.get('l', 0),
                'win_pct': base_data.get('w_pct', 0),
                
                # Base Offensive
                'pts': base_data.get('pts', 0),
                'fgm': base_data.get('fgm', 0),
                'fga': base_data.get('fga', 0),
                'fg_pct': base_data.get('fg_pct', 0),
                'fg3m': base_data.get('fg3m', 0),
                'fg3a': base_data.get('fg3a', 0),
                'fg3_pct': base_data.get('fg3_pct', 0),
                'ftm': base_data.get('ftm', 0),
                'fta': base_data.get('fta', 0),
                'ft_pct': base_data.get('ft_pct', 0),
                'oreb': base_data.get('oreb', 0),
                'dreb': base_data.get('dreb', 0),
                'reb': base_data.get('reb', 0),
                'ast': base_data.get('ast', 0),
                'tov': base_data.get('tov', 0),
                'stl': base_data.get('stl', 0),
                'blk': base_data.get('blk', 0),
                'pf': base_data.get('pf', 0),
                'plus_minus': base_data.get('plus_minus', 0),
                
                # Advanced
                'off_rating': adv_data.get('off_rating', 0),
                'def_rating': adv_data.get('def_rating', 0),
                'net_rating': adv_data.get('net_rating', 0),
                'pace': adv_data.get('pace', 0),
                'pie': adv_data.get('pie', 0),
                'ast_pct': adv_data.get('ast_pct', 0),
                'ast_tov': adv_data.get('ast_tov', 0),
                'ast_ratio': adv_data.get('ast_ratio', 0),
                'oreb_pct': adv_data.get('oreb_pct', 0),
                'dreb_pct': adv_data.get('dreb_pct', 0),
                'reb_pct': adv_data.get('reb_pct', 0),
                'tov_pct': adv_data.get('tm_tov_pct', adv_data.get('tov_pct', 0)),
                'efg_pct': adv_data.get('efg_pct', 0),
                'ts_pct': adv_data.get('ts_pct', 0),
                'poss': adv_data.get('poss', 0),
                
                # Four Factors
                'efg_pct_four': ff_data.get('efg_pct', 0),
                'fta_rate': ff_data.get('fta_rate', 0),
                'tov_pct_four': ff_data.get('tm_tov_pct', ff_data.get('tov_pct', 0)),
                'oreb_pct_four': ff_data.get('oreb_pct', 0),
                'opp_efg_pct': ff_data.get('opp_efg_pct', 0),
                'opp_fta_rate': ff_data.get('opp_fta_rate', 0),
                'opp_tov_pct': ff_data.get('opp_tov_pct', 0),
                'opp_oreb_pct': ff_data.get('opp_oreb_pct', 0),
                
                # Scoring
                'pct_pts_2pt': score_data.get('pct_pts_2pt', 0),
                'pct_pts_2pt_mid': score_data.get('pct_pts_2pt_mr', score_data.get('pct_pts_mid_range_2', 0)),
                'pct_pts_3pt': score_data.get('pct_pts_3pt', 0),
                'pct_pts_fb': score_data.get('pct_pts_fb', 0),
                'pct_pts_ft': score_data.get('pct_pts_ft', 0),
                'pct_pts_off_tov': score_data.get('pct_pts_off_tov', 0),
                'pct_pts_paint': score_data.get('pct_pts_paint', 0),
                'pct_ast_2pm': score_data.get('pct_ast_2pm', 0),
                'pct_uast_2pm': score_data.get('pct_uast_2pm', 0),
                'pct_ast_3pm': score_data.get('pct_ast_3pm', 0),
                'pct_uast_3pm': score_data.get('pct_uast_3pm', 0),
                'pct_ast_fgm': score_data.get('pct_ast_fgm', 0),
                'pct_uast_fgm': score_data.get('pct_uast_fgm', 0),
                
                # Misc
                'pts_off_tov': misc_data.get('pts_off_tov', 0),
                'pts_2nd_chance': misc_data.get('pts_2nd_chance', 0),
                'pts_fb': misc_data.get('pts_fb', 0),
                'pts_paint': misc_data.get('pts_paint', 0),
                'opp_pts_off_tov': misc_data.get('opp_pts_off_tov', 0),
                'opp_pts_2nd_chance': misc_data.get('opp_pts_2nd_chance', 0),
                'opp_pts_fb': misc_data.get('opp_pts_fb', 0),
                'opp_pts_paint': misc_data.get('opp_pts_paint', 0),
                
                # Opponent (Defensive)
                'opp_fgm': opp_data.get('opp_fgm', opp_data.get('fgm', 0)),
                'opp_fga': opp_data.get('opp_fga', opp_data.get('fga', 0)),
                'opp_fg_pct': opp_data.get('opp_fg_pct', opp_data.get('fg_pct', 0)),
                'opp_fg3m': opp_data.get('opp_fg3m', opp_data.get('fg3m', 0)),
                'opp_fg3a': opp_data.get('opp_fg3a', opp_data.get('fg3a', 0)),
                'opp_fg3_pct': opp_data.get('opp_fg3_pct', opp_data.get('fg3_pct', 0)),
                'opp_ftm': opp_data.get('opp_ftm', opp_data.get('ftm', 0)),
                'opp_fta': opp_data.get('opp_fta', opp_data.get('fta', 0)),
                'opp_ft_pct': opp_data.get('opp_ft_pct', opp_data.get('ft_pct', 0)),
                'opp_oreb': opp_data.get('opp_oreb', opp_data.get('oreb', 0)),
                'opp_dreb': opp_data.get('opp_dreb', opp_data.get('dreb', 0)),
                'opp_reb': opp_data.get('opp_reb', opp_data.get('reb', 0)),
                'opp_ast': opp_data.get('opp_ast', opp_data.get('ast', 0)),
                'opp_tov': opp_data.get('opp_tov', opp_data.get('tov', 0)),
                'opp_stl': opp_data.get('opp_stl', opp_data.get('stl', 0)),
                'opp_blk': opp_data.get('opp_blk', opp_data.get('blk', 0)),
                'opp_pf': opp_data.get('opp_pf', opp_data.get('pf', 0)),
                'opp_pts': opp_data.get('opp_pts', opp_data.get('pts', 0)),
                'opp_plus_minus': opp_data.get('opp_plus_minus', opp_data.get('plus_minus', 0)),
                
                # Metadata
                'season': self.CURRENT_SEASON,
                'data_source': 'nba_api',
                'updated_at': datetime.now().isoformat(),
            }
            
            # Store raw data as JSON for debugging
            team['raw_data_json'] = json.dumps({
                'base': base_data,
                'advanced': adv_data,
                'four_factors': ff_data,
                'misc': misc_data,
                'scoring': score_data,
                'opponent': opp_data,
            })
            
            merged_teams.append(team)
        
        print(f"   ✅ Merged data for {len(merged_teams)} teams")
        return merged_teams
    
    def save_to_database(self, teams: List[Dict]) -> int:
        """Save all team stats to database"""
        print("\n💾 Saving to database...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        saved = 0
        for team in teams:
            columns = list(team.keys())
            placeholders = ','.join(['?' for _ in columns])
            columns_str = ','.join(columns)
            
            cursor.execute(f"""
                INSERT OR REPLACE INTO team_stats_comprehensive
                ({columns_str}) VALUES ({placeholders})
            """, list(team.values()))
            saved += 1
        
        conn.commit()
        conn.close()
        
        print(f"   ✅ Saved {saved} teams to database")
        return saved
    
    def save_to_json(self, teams: List[Dict]) -> Path:
        """Save team stats to JSON file with lookup indices for efficient access"""
        date_str = datetime.now().strftime('%Y%m%d')
        filepath = self.data_dir / f'team_stats_{date_str}.json'
        
        # Build lookup indices for efficient access
        by_id = {}
        by_abbr = {}
        by_name = {}
        
        # Remove raw_data_json for cleaner export and build indices
        clean_teams = []
        for team in teams:
            clean_team = {k: v for k, v in team.items() if k != 'raw_data_json'}
            clean_teams.append(clean_team)
            
            # Build indices
            by_id[team['team_id']] = clean_team
            by_abbr[team['team_abbr'].lower()] = clean_team
            by_name[team['team_name'].lower()] = clean_team
        
        output = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'season': self.CURRENT_SEASON,
                'total_teams': len(clean_teams),
                'data_source': 'nba_api',
                'version': '1.0',
            },
            # List format for iteration
            'teams': clean_teams,
            # Lookup indices for O(1) access
            'by_team_id': by_id,
            'by_abbr': by_abbr,
            'by_name': by_name,
            # Quick reference mapping
            'id_to_abbr': {t['team_id']: t['team_abbr'] for t in clean_teams},
            'abbr_to_id': {t['team_abbr']: t['team_id'] for t in clean_teams},
            'abbr_to_name': {t['team_abbr']: t['team_name'] for t in clean_teams},
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"   ✅ Saved to {filepath}")
        print(f"   📋 Indices: by_team_id, by_abbr, by_name (all lowercase)")
        return filepath
    
    def run(self, test_single: bool = False) -> bool:
        """
        Main entry point.
        
        Args:
            test_single: If True, only fetch first stat type to test connectivity
        """
        print("\n" + "="*60)
        print("🏀 COMPREHENSIVE NBA TEAM STATS COLLECTOR")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🏟️  Season: {self.CURRENT_SEASON}")
        print("="*60)
        
        if test_single:
            print("\n⚡ TEST MODE: Fetching only base stats")
            base = self.fetch_base_stats()
            if base:
                print(f"\n✅ TEST PASSED: Got {len(base)} teams")
                sample_id = list(base.keys())[0]
                sample = base[sample_id]
                print(f"\n📋 Sample team data ({sample.get('team_name', sample_id)}):")
                for key in ['gp', 'pts', 'reb', 'ast', 'fg_pct']:
                    print(f"   {key}: {sample.get(key, 'N/A')}")
                return True
            else:
                print("\n❌ TEST FAILED: Could not fetch data")
                return False
        
        # Fetch all stat types
        base = self.fetch_base_stats()
        if not base:
            print("\n❌ CRITICAL: Could not fetch base stats - aborting")
            return False
        
        advanced = self.fetch_advanced_stats()
        four_factors = self.fetch_four_factors()
        misc = self.fetch_misc_stats()
        scoring = self.fetch_scoring_stats()
        opponent = self.fetch_opponent_stats()
        
        # Merge all stats
        teams = self.merge_all_stats(base, advanced, four_factors, misc, scoring, opponent)
        
        if not teams:
            print("\n❌ FAILED: No teams to save")
            return False
        
        # Save to database and JSON
        saved = self.save_to_database(teams)
        json_path = self.save_to_json(teams)
        
        # Summary
        print("\n" + "="*60)
        print("📊 COLLECTION COMPLETE")
        print("="*60)
        print(f"   ✅ Teams collected: {len(teams)}")
        print(f"   ✅ Saved to database: {saved}")
        print(f"   ✅ JSON export: {json_path}")
        
        if self.errors:
            print(f"\n   ⚠️ Errors encountered: {len(self.errors)}")
            for err in self.errors[:5]:
                print(f"      - {err}")
        
        # Show sample
        if teams:
            sample = teams[0]
            print(f"\n📋 Sample: {sample['team_name']} ({sample['team_abbr']})")
            print(f"   Record: {sample['wins']}-{sample['losses']} ({sample['games_played']} GP)")
            print(f"   PPG: {sample['pts']} | Off Rtg: {sample['off_rating']} | Def Rtg: {sample['def_rating']}")
            print(f"   Pace: {sample['pace']} | Net Rtg: {sample['net_rating']}")
        
        print("="*60)
        return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Collect NBA team stats')
    parser.add_argument('--test', action='store_true', help='Run test mode (single fetch)')
    args = parser.parse_args()
    
    collector = ComprehensiveTeamStatsCollector()
    
    if args.test:
        success = collector.run(test_single=True)
    else:
        success = collector.run()
    
    exit(0 if success else 1)
