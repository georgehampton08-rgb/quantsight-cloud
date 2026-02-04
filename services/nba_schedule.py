"""
NBA Live Schedule Service
Fetches today's games from the NBA API scoreboard endpoint
"""
import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

# NBA Team ID to Abbreviation mapping
TEAM_ID_TO_ABBR = {
    1610612737: 'ATL', 1610612738: 'BOS', 1610612739: 'CLE', 1610612740: 'NOP',
    1610612741: 'CHI', 1610612742: 'DAL', 1610612743: 'DEN', 1610612744: 'GSW',
    1610612745: 'HOU', 1610612746: 'LAC', 1610612747: 'LAL', 1610612748: 'MIA',
    1610612749: 'MIL', 1610612750: 'MIN', 1610612751: 'BKN', 1610612752: 'NYK',
    1610612753: 'ORL', 1610612754: 'IND', 1610612755: 'PHI', 1610612756: 'PHX',
    1610612757: 'POR', 1610612758: 'SAC', 1610612759: 'SAS', 1610612760: 'OKC',
    1610612761: 'TOR', 1610612762: 'UTA', 1610612763: 'MEM', 1610612764: 'WAS',
    1610612765: 'DET', 1610612766: 'CHA',
}

# Reverse mapping
ABBR_TO_TEAM_ID = {v: k for k, v in TEAM_ID_TO_ABBR.items()}


class NBAScheduleService:
    """Fetches live NBA schedule and game status"""
    
    # NBA API endpoints
    SCOREBOARD_URL = "https://stats.nba.com/stats/scoreboardV2"
    TODAY_SCOREBOARD = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._cache = {}
        self._cache_time = 0
        self._cache_ttl = 60  # 1 minute cache
    
    def get_todays_games(self) -> List[Dict]:
        """
        Fetch today's games from NBA API.
        Returns list of game dicts with home/away teams and status.
        """
        # Check cache
        now = time.time()
        if self._cache.get('games') and (now - self._cache_time) < self._cache_ttl:
            return self._cache['games']
        
        games = []
        
        try:
            # Try the CDN endpoint first (more reliable)
            response = self.session.get(self.TODAY_SCOREBOARD, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                scoreboard = data.get('scoreboard', {})
                game_list = scoreboard.get('games', [])
                
                for game in game_list:
                    home_team = game.get('homeTeam', {})
                    away_team = game.get('awayTeam', {})
                    
                    # Get game status
                    game_status = game.get('gameStatus', 1)
                    status_text = game.get('gameStatusText', 'Scheduled')
                    
                    # Map status codes
                    if game_status == 1:
                        status = 'scheduled'
                    elif game_status == 2:
                        status = 'live'
                    elif game_status == 3:
                        status = 'final'
                    else:
                        status = 'unknown'
                    
                    game_info = {
                        'game_id': game.get('gameId', ''),
                        'home_team': home_team.get('teamTricode', 'UNK'),
                        'away_team': away_team.get('teamTricode', 'UNK'),
                        'home_team_id': home_team.get('teamId'),
                        'away_team_id': away_team.get('teamId'),
                        'home_score': home_team.get('score', 0),
                        'away_score': away_team.get('score', 0),
                        'game_time': game.get('gameTimeUTC', ''),
                        'game_time_local': game.get('gameEt', ''),
                        'status': status,
                        'status_text': status_text,
                        'period': game.get('period', 0),
                        'game_clock': game.get('gameClock', ''),
                        'display': f"{away_team.get('teamTricode', 'UNK')} @ {home_team.get('teamTricode', 'UNK')}",
                    }
                    
                    # Add live score to display if game is live
                    if status == 'live':
                        game_info['display'] = (
                            f"{away_team.get('teamTricode', 'UNK')} {away_team.get('score', 0)} @ "
                            f"{home_team.get('teamTricode', 'UNK')} {home_team.get('score', 0)} "
                            f"({status_text})"
                        )
                    elif status == 'final':
                        game_info['display'] = (
                            f"{away_team.get('teamTricode', 'UNK')} {away_team.get('score', 0)} @ "
                            f"{home_team.get('teamTricode', 'UNK')} {home_team.get('score', 0)} "
                            f"(Final)"
                        )
                    
                    games.append(game_info)
                
                logger.info(f"Fetched {len(games)} games from NBA API")
        
        except requests.RequestException as e:
            logger.error(f"NBA API request failed: {e}")
        except Exception as e:
            logger.error(f"Error parsing NBA scoreboard: {e}")
        
        # Cache results
        if games:
            self._cache['games'] = games
            self._cache_time = now
        
        return games
    
    def get_live_games(self) -> List[Dict]:
        """Get only games that are currently live"""
        all_games = self.get_todays_games()
        return [g for g in all_games if g['status'] == 'live']
    
    def get_upcoming_games(self) -> List[Dict]:
        """Get only games that haven't started yet"""
        all_games = self.get_todays_games()
        return [g for g in all_games if g['status'] == 'scheduled']
    
    def get_game_by_teams(self, home: str, away: str) -> Optional[Dict]:
        """Find a specific game by team abbreviations"""
        all_games = self.get_todays_games()
        for game in all_games:
            if game['home_team'] == home.upper() and game['away_team'] == away.upper():
                return game
        return None


# Singleton instance
_schedule_service = None

def get_schedule_service() -> NBAScheduleService:
    global _schedule_service
    if _schedule_service is None:
        _schedule_service = NBAScheduleService()
    return _schedule_service


if __name__ == "__main__":
    # Test the service
    service = get_schedule_service()
    games = service.get_todays_games()
    
    print(f"\n{'='*60}")
    print(f"NBA SCHEDULE - {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")
    
    if not games:
        print("No games found or API unavailable")
    else:
        for game in games:
            status_icon = {'scheduled': '⏰', 'live': '🔴', 'final': '✅'}.get(game['status'], '❓')
            print(f"{status_icon} {game['display']}")
            if game['status'] == 'live':
                print(f"   Q{game['period']} - {game['game_clock']}")
        
        print(f"\nTotal: {len(games)} games")
        print(f"Live: {len([g for g in games if g['status'] == 'live'])}")
        print(f"Upcoming: {len([g for g in games if g['status'] == 'scheduled'])}")
