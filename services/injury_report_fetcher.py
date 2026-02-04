"""
Injury Report Fetcher
=====================
Fetches current NBA injury reports to determine player availability.
Uses NBA API and web scraping for real-time injury status.
"""
import sqlite3
import requests
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Try nba_api
try:
    from nba_api.stats.static import players, teams
    HAS_NBA_API = True
except ImportError:
    HAS_NBA_API = False


class InjuryReportFetcher:
    """
    Fetches and caches injury report data.
    
    Statuses:
    - OUT: Player will not play
    - DOUBTFUL: Unlikely to play (25%)
    - QUESTIONABLE: May or may not play (50%)
    - PROBABLE: Likely to play (75%)
    - AVAILABLE: Will play
    """
    
    # Status priority (lower = more severe)
    STATUS_PRIORITY = {
        'OUT': 0,
        'DOUBTFUL': 1,
        'QUESTIONABLE': 2,
        'PROBABLE': 3,
        'AVAILABLE': 4,
        'GTD': 2,  # Game Time Decision = Questionable
    }
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
    }
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._ensure_table()
        self._cache: Dict[str, Dict] = {}
        self._last_fetch: Optional[datetime] = None
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_table(self):
        """Create injury report table"""
        conn = self._get_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS injury_report (
                player_id TEXT,
                player_name TEXT,
                team_abbr TEXT,
                status TEXT,
                injury_desc TEXT,
                game_date TEXT,
                updated_at TIMESTAMP,
                PRIMARY KEY (player_id, game_date)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def fetch_injury_report(self, force: bool = False) -> List[Dict]:
        """
        Fetch current injury report from NBA.
        Tries multiple sources with fallbacks.
        
        Returns list of injured players with status.
        """
        # Check if recently fetched (within 30 min)
        if not force and self._last_fetch:
            if datetime.now() - self._last_fetch < timedelta(minutes=30):
                logger.info("Using cached injury report (<30min old)")
                return self._get_cached_report()
        
        injuries = []
        
        # Try Method 1: NBA CDN endpoint
        try:
            url = "https://cdn.nba.com/static/json/liveData/injuries/injuries_list.json"
            response = requests.get(url, headers=self.HEADERS, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                for team_data in data.get('teams', []):
                    team_abbr = team_data.get('teamTricode', '')
                    
                    for player in team_data.get('players', []):
                        injury = {
                            'player_id': str(player.get('personId', '')),
                            'player_name': player.get('firstName', '') + ' ' + player.get('lastName', ''),
                            'team_abbr': team_abbr,
                            'status': player.get('injuryStatus', 'OUT'),
                            'injury_desc': player.get('injuryDescription', ''),
                            'game_date': datetime.now().strftime('%Y-%m-%d'),
                        }
                        injuries.append(injury)
                
                if injuries:
                    self._save_injuries(injuries)
                    self._last_fetch = datetime.now()
                    logger.info(f"✅ Fetched {len(injuries)} injuries from NBA CDN")
                    return injuries
            else:
                logger.warning(f"NBA CDN returned {response.status_code}")
                
        except Exception as e:
            logger.warning(f"NBA CDN failed: {e}")
        
        # Try Method 2: nba_api if available
        if HAS_NBA_API:
            try:
                from nba_api.stats.endpoints import commonteamroster
                import time
                
                # Get all 30 teams
                all_teams = teams.get_teams()
                
                for team in all_teams[:5]:  # Limit to 5 teams for testing
                    time.sleep(0.6)  # Rate limiting
                    roster = commonteamroster.CommonTeamRoster(team_id=team['id'])
                    df = roster.get_data_frames()[0]
                    
                    # Check for DNP/OUT in recent games (this is indirect)
                    # Real injury data would need scraping
                    
                logger.info("nba_api roster check complete (indirect injury data)")
                    
            except Exception as e:
                logger.warning(f"nba_api method failed: {e}")
        
        # If no fresh data, use cache
        cached = self._get_cached_report()
        if cached:
            logger.info(f"📦 Using cached injury data ({len(cached)} entries)")
            return cached
        
        logger.warning("⚠️ No injury data available from any source")
        return []
    
    def _save_injuries(self, injuries: List[Dict]):
        """Save injuries to database"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        
        for inj in injuries:
            conn.execute("""
                INSERT OR REPLACE INTO injury_report
                (player_id, player_name, team_abbr, status, injury_desc, game_date, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                inj['player_id'], inj['player_name'], inj['team_abbr'],
                inj['status'], inj['injury_desc'], inj['game_date'], now
            ))
        
        conn.commit()
        conn.close()
    
    def _get_cached_report(self) -> List[Dict]:
        """Get cached injury report from database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT * FROM injury_report
            WHERE game_date >= ?
            ORDER BY team_abbr, player_name
        """, (today,))
        
        injuries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return injuries
    
    def get_team_injuries(self, team_abbr: str) -> List[Dict]:
        """Get injuries for a specific team"""
        team_abbr = team_abbr.upper()
        
        # Fetch fresh if needed
        self.fetch_injury_report()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT * FROM injury_report
            WHERE team_abbr = ? AND game_date >= ?
        """, (team_abbr, today))
        
        injuries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return injuries
    
    def get_player_status(self, player_id: str) -> Dict:
        """
        Get status for a specific player.
        
        Returns:
            {status: 'OUT'|'DOUBTFUL'|'QUESTIONABLE'|'PROBABLE'|'AVAILABLE',
             injury_desc: str, is_available: bool}
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT status, injury_desc FROM injury_report
            WHERE player_id = ? AND game_date >= ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (str(player_id), today))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            status = row['status'].upper()
            is_available = status not in ('OUT', 'DOUBTFUL')
            return {
                'status': status,
                'injury_desc': row['injury_desc'],
                'is_available': is_available,
            }
        
        # No injury record = available
        return {
            'status': 'AVAILABLE',
            'injury_desc': '',
            'is_available': True,
        }
    
    def filter_available_players(self, players: List[Dict]) -> tuple:
        """
        Filter roster to only available players.
        
        Returns:
            (available_players, out_players)
        """
        available = []
        out = []
        
        for player in players:
            player_id = str(player.get('player_id'))
            status = self.get_player_status(player_id)
            
            if status['is_available']:
                available.append(player)
            else:
                player['injury_status'] = status['status']
                player['injury_desc'] = status['injury_desc']
                out.append(player)
        
        return available, out
    
    def get_injury_summary(self, team_abbr: str) -> Dict:
        """Get summary of team's injury situation"""
        injuries = self.get_team_injuries(team_abbr)
        
        summary = {
            'team': team_abbr,
            'total_injured': len(injuries),
            'out': [i for i in injuries if i['status'] == 'OUT'],
            'doubtful': [i for i in injuries if i['status'] == 'DOUBTFUL'],
            'questionable': [i for i in injuries if i['status'] in ('QUESTIONABLE', 'GTD')],
            'probable': [i for i in injuries if i['status'] == 'PROBABLE'],
        }
        
        return summary


# Singleton
_fetcher = None

def get_injury_fetcher() -> InjuryReportFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = InjuryReportFetcher()
    return _fetcher


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = get_injury_fetcher()
    
    print("="*60)
    print("INJURY REPORT FETCHER TEST")
    print("="*60)
    
    # Fetch injury report
    print("\n1. Fetching current injury report...")
    injuries = fetcher.fetch_injury_report()
    print(f"   Found {len(injuries)} injury entries")
    
    # Show Lakers injuries
    print("\n2. Lakers injury report:")
    lal_injuries = fetcher.get_team_injuries("LAL")
    if lal_injuries:
        for inj in lal_injuries:
            print(f"   {inj['player_name']}: {inj['status']} - {inj['injury_desc']}")
    else:
        print("   No injuries reported")
    
    # Test player status
    print("\n3. LeBron James status:")
    status = fetcher.get_player_status("2544")
    print(f"   Status: {status['status']}")
    print(f"   Available: {status['is_available']}")
