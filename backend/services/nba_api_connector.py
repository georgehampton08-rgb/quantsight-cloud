import logging
import time
import random
from typing import List, Dict, Optional
from core.config import CURRENT_SEASON

# Use the library's official endpoints for resilience
from nba_api.stats.endpoints import (
    commonallplayers,
    commonteamroster,
    playercareerstats,
    playergamelog
)
from nba_api.stats.static import players as static_players

logger = logging.getLogger(__name__)

class NBAAPIConnector:
    """
    Resilient NBA Stats API connector powered by the official nba_api library.
    Handles rate limiting and header management internally.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Be conservative: 1s between requests
        
    def _rate_limit(self):
        """Enforce rate limiting between API calls."""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_request_interval:
            # Add a bit of jitter to avoid pattern detection
            sleep_time = (self.min_request_interval - time_since_last) + random.uniform(0.1, 0.5)
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def fetch(self, entity_type: str, entity_id: str, query: dict = None) -> dict:
        """Generic fetch method used by AegisBrain."""
        if entity_type == 'player_stats':
            return self.get_player_game_logs(entity_id)
        elif entity_type == 'player_profile':
            return self.get_player_stats(entity_id)
        elif entity_type == 'team_roster':
            return self.get_team_roster(entity_id)
        elif entity_type == 'all_players':
            return self.get_all_players()
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def get_all_players(self, season=CURRENT_SEASON) -> List[Dict]:
        """Fetch all players using CommonAllPlayers endpoint."""
        try:
            self._rate_limit()
            logger.info(f"NBA API: Fetching all players for season {season}")
            data = commonallplayers.CommonAllPlayers(
                is_only_current_season=1,
                league_id='00',
                season=season
            )
            return data.get_dict()['resultSets'][0]['rowSet']
        except Exception as e:
            logger.error(f"NBA API: Failed to fetch all players: {e}")
            return []
            
    def get_team_roster(self, team_id: str, season=CURRENT_SEASON) -> List[Dict]:
        """Fetch team roster using CommonTeamRoster endpoint."""
        try:
            self._rate_limit()
            logger.info(f"NBA API: Fetching roster for team {team_id}")
            data = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=season,
                league_id='00'
            )
            return data.get_dict()['resultSets'][0]['rowSet']
        except Exception as e:
            logger.error(f"NBA API: Failed to fetch roster for team {team_id}: {e}")
            return []
    
    def get_player_stats(self, player_id: str, season=CURRENT_SEASON) -> Optional[Dict]:
        """Fetch player career/season stats using PlayerCareerStats endpoint."""
        try:
            self._rate_limit()
            logger.info(f"NBA API: Fetching stats for player {player_id}")
            data = playercareerstats.PlayerCareerStats(
                player_id=player_id,
                per_mode36='PerGame'
            )
            data_dict = data.get_dict()
            
            # Find Regular Season Totals
            for rs in data_dict['resultSets']:
                if rs['name'] == 'SeasonTotalsRegularSeason':
                    headers = rs['headers']
                    rows = rs['rowSet']
                    if not rows: return None
                    # Return the most recent season row
                    return dict(zip(headers, rows[-1]))
            return None
        except Exception as e:
            logger.error(f"NBA API: Failed to fetch stats for player {player_id}: {e}")
            return None

    def get_player_game_logs(self, player_id: str, season=CURRENT_SEASON) -> List[Dict]:
        """Fetch player game logs using PlayerGameLog endpoint."""
        try:
            self._rate_limit()
            logger.info(f"NBA API: Fetching game logs for player {player_id}")
            data = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season,
                season_type_all_star='Regular Season'
            )
            data_dict = data.get_dict()
            headers = data_dict['resultSets'][0]['headers']
            rows = data_dict['resultSets'][0]['rowSet']
            return [dict(zip(headers, row)) for row in rows]
        except Exception as e:
            logger.error(f"NBA API: Failed to fetch game logs for player {player_id}: {e}")
            return []

    def populate_database(self):
        """Minimal sync to verify connection."""
        players_list = self.get_all_players()
        if players_list:
            logger.info(f"Successfully connected to NBA API and found {len(players_list)} players.")
            return True
        return False
