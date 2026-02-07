"""
NBA API Adapter - Schema Isolation Layer (v2.0 - Native aiohttp)
=================================================================
Centralizes all NBA API interactions and normalizes responses.
If NBA changes their schema, update THIS FILE ONLY.

Uses native aiohttp for true async HTTP requests - no ThreadPoolExecutor.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# CANONICAL DATA STRUCTURES (QuantSight Internal Schema)
# ============================================================================

@dataclass
class NormalizedPlayerStats:
    """Normalized player box score statistics."""
    player_id: str
    name: str
    team_tricode: str
    status: Literal['ACTIVE', 'INACTIVE', 'DNP']
    
    # Counting stats
    pts: int = 0
    fgm: int = 0
    fga: int = 0
    fg3m: int = 0
    fg3a: int = 0
    ftm: int = 0
    fta: int = 0
    oreb: int = 0
    dreb: int = 0
    reb: int = 0
    ast: int = 0
    stl: int = 0
    blk: int = 0
    tov: int = 0
    pf: int = 0
    plus_minus: float = 0.0
    minutes: str = "0:00"
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NormalizedGameInfo:
    """Normalized game information."""
    game_id: str
    status_code: int  # 1=UPCOMING, 2=LIVE, 3=FINAL
    status: Literal['UPCOMING', 'LIVE', 'FINAL', 'UNKNOWN']
    
    # Teams
    home_team_tricode: str
    away_team_tricode: str
    home_score: int = 0
    away_score: int = 0
    
    # Game clock
    period: int = 0
    clock: str = ""
    status_text: str = ""
    
    # Metadata
    game_date: str = ""
    arena: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NormalizedBoxScore:
    """Normalized full box score for a game."""
    game_id: str
    game_info: NormalizedGameInfo
    home_players: List[NormalizedPlayerStats]
    away_players: List[NormalizedPlayerStats]
    
    def all_active_players(self) -> List[NormalizedPlayerStats]:
        """Get all active players from both teams."""
        return [p for p in self.home_players + self.away_players if p.status == 'ACTIVE']
    
    def get_team_stats(self, team_tricode: str) -> Dict[str, float]:
        """
        Get aggregated team stats for usage vacuum calculation.
        
        Args:
            team_tricode: Team abbreviation (e.g., 'LAL', 'BOS')
            
        Returns:
            Dict with team totals: fga, fta, tov, pts
        """
        # Determine which team
        is_home = (team_tricode == self.game_info.home_team_tricode)
        players = self.home_players if is_home else self.away_players
        
        # Aggregate active player stats
        active = [p for p in players if p.status == 'ACTIVE']
        
        return {
            'fga': sum(p.fga for p in active),
            'fta': sum(p.fta for p in active),
            'tov': sum(p.tov for p in active),
            'pts': sum(p.pts for p in active),
            'fgm': sum(p.fgm for p in active),
            'ftm': sum(p.ftm for p in active),
        }
    
    def to_dict(self) -> Dict:
        return {
            'game_id': self.game_id,
            'game_info': self.game_info.to_dict(),
            'home_players': [p.to_dict() for p in self.home_players],
            'away_players': [p.to_dict() for p in self.away_players]
        }


# ============================================================================
# ADAPTER: Normalizes NBA API Responses
# ============================================================================

class NBAApiAdapter:
    """
    Adapter Pattern implementation for NBA API.
    
    All NBA API schema knowledge is contained HERE. If NBA changes their JSON
    structure, update the _extract_* methods below and no other files need changes.
    """
    
    # ========================================================================
    # NBA API FIELD MAPPINGS (Update these if NBA changes their schema)
    # ========================================================================
    
    # Scoreboard game fields
    GAME_ID_FIELD = 'gameId'
    GAME_STATUS_FIELD = 'gameStatus'  # 1, 2, 3
    GAME_STATUS_TEXT_FIELD = 'gameStatusText'
    PERIOD_FIELD = 'period'
    HOME_TEAM_FIELD = 'homeTeam'
    AWAY_TEAM_FIELD = 'awayTeam'
    TEAM_TRICODE_FIELD = 'teamTricode'
    TEAM_SCORE_FIELD = 'score'
    GAME_CLOCK_FIELD = 'gameClock'  # e.g., "PT05M30.00S"
    
    # Boxscore player stats fields
    PERSON_ID_FIELD = 'personId'
    PLAYER_NAME_FIELD = 'name'
    PLAYER_STATUS_FIELD = 'status'
    STATISTICS_FIELD = 'statistics'
    
    # Stats sub-fields (inside 'statistics' object)
    STATS_POINTS = 'points'
    STATS_FGM = 'fieldGoalsMade'
    STATS_FGA = 'fieldGoalsAttempted'
    STATS_FG3M = 'threePointersMade'
    STATS_FG3A = 'threePointersAttempted'
    STATS_FTM = 'freeThrowsMade'
    STATS_FTA = 'freeThrowsAttempted'
    STATS_OREB = 'reboundsOffensive'
    STATS_DREB = 'reboundsDefensive'
    STATS_REB = 'reboundsTotal'
    STATS_AST = 'assists'
    STATS_STL = 'steals'
    STATS_BLK = 'blocks'
    STATS_TOV = 'turnovers'
    STATS_PF = 'foulsPersonal'
    STATS_PLUS_MINUS = 'plusMinusPoints'
    STATS_MINUTES = 'minutes'
    
    # ========================================================================
    # NBA API ENDPOINTS (v2.0 - Direct HTTP)
    # ========================================================================
    
    # NBA Live Data API endpoints
    SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    BOXSCORE_URL_TEMPLATE = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
    
    # ========================================================================
    # STATUS CODE MAPPING
    # ========================================================================
    
    @staticmethod
    def _normalize_status(status_code: int) -> Literal['UPCOMING', 'LIVE', 'FINAL', 'UNKNOWN']:
        """Convert NBA API status code to canonical string."""
        return {1: 'UPCOMING', 2: 'LIVE', 3: 'FINAL'}.get(status_code, 'UNKNOWN')
    
    # ========================================================================
    # SCOREBOARD NORMALIZATION
    # ========================================================================
    
    def normalize_scoreboard(self, raw_data: Dict) -> List[NormalizedGameInfo]:
        """Normalize NBA API scoreboard response to list of NormalizedGameInfo."""
        games = []
        scoreboard = raw_data.get('scoreboard', {})
        
        for game in scoreboard.get('games', []):
            try:
                games.append(self._extract_game_info(game))
            except Exception as e:
                logger.warning(f"Failed to normalize game: {e}")
                continue
        
        return games
    
    def _extract_game_info(self, game: Dict) -> NormalizedGameInfo:
        """Extract normalized game info from raw game dict."""
        status_code = game.get(self.GAME_STATUS_FIELD, 1)
        home = game.get(self.HOME_TEAM_FIELD, {})
        away = game.get(self.AWAY_TEAM_FIELD, {})
        
        return NormalizedGameInfo(
            game_id=str(game.get(self.GAME_ID_FIELD, '')),
            status_code=status_code,
            status=self._normalize_status(status_code),
            home_team_tricode=home.get(self.TEAM_TRICODE_FIELD, '???'),
            away_team_tricode=away.get(self.TEAM_TRICODE_FIELD, '???'),
            home_score=home.get(self.TEAM_SCORE_FIELD, 0) or 0,
            away_score=away.get(self.TEAM_SCORE_FIELD, 0) or 0,
            period=game.get(self.PERIOD_FIELD, 0),
            clock=game.get(self.GAME_CLOCK_FIELD, ''),
            status_text=game.get(self.GAME_STATUS_TEXT_FIELD, ''),
            game_date=game.get('gameDate', '')  # Added gameDate
        )
    
    # ========================================================================
    # BOXSCORE NORMALIZATION
    # ========================================================================
    
    def normalize_boxscore(self, raw_data: Dict) -> NormalizedBoxScore:
        """Normalize NBA API boxscore response."""
        game = raw_data.get('game', {})
        game_id = str(game.get('gameId', ''))
        
        home_team = game.get('homeTeam', {})
        away_team = game.get('awayTeam', {})
        
        game_info = NormalizedGameInfo(
            game_id=game_id,
            status_code=game.get('gameStatus', 1),
            status=self._normalize_status(game.get('gameStatus', 1)),
            home_team_tricode=home_team.get('teamTricode', '???'),
            away_team_tricode=away_team.get('teamTricode', '???'),
            home_score=home_team.get('score', 0) or 0,
            away_score=away_team.get('score', 0) or 0,
            period=game.get('period', 0),
            clock=game.get(self.GAME_CLOCK_FIELD, ''),
            status_text=game.get('gameStatusText', '')
        )
        
        return NormalizedBoxScore(
            game_id=game_id,
            game_info=game_info,
            home_players=self._extract_team_players(home_team),
            away_players=self._extract_team_players(away_team)
        )
    
    def _extract_team_players(self, team: Dict) -> List[NormalizedPlayerStats]:
        """Extract normalized player stats from team dict."""
        players = []
        team_tricode = team.get(self.TEAM_TRICODE_FIELD, '???')
        
        for player in team.get('players', []):
            try:
                players.append(self._extract_player_stats(player, team_tricode))
            except Exception as e:
                logger.debug(f"Failed to extract player: {e}")
                continue
        
        return players
    
    def _extract_player_stats(self, player: Dict, team_tricode: str) -> NormalizedPlayerStats:
        """Extract normalized stats for a single player."""
        stats = player.get(self.STATISTICS_FIELD, {})
        
        minutes_raw = stats.get(self.STATS_MINUTES, 'PT0M0S')
        minutes_str = self._parse_iso_minutes(minutes_raw)
        
        raw_status = player.get(self.PLAYER_STATUS_FIELD, 'INACTIVE')
        status: Literal['ACTIVE', 'INACTIVE', 'DNP'] = 'INACTIVE'
        if raw_status == 'ACTIVE':
            status = 'ACTIVE'
        elif raw_status in ['DNP', 'DND']:
            status = 'DNP'
        
        return NormalizedPlayerStats(
            player_id=str(player.get(self.PERSON_ID_FIELD, '')),
            name=player.get(self.PLAYER_NAME_FIELD, 'Unknown'),
            team_tricode=team_tricode,
            status=status,
            pts=stats.get(self.STATS_POINTS, 0) or 0,
            fgm=stats.get(self.STATS_FGM, 0) or 0,
            fga=stats.get(self.STATS_FGA, 0) or 0,
            fg3m=stats.get(self.STATS_FG3M, 0) or 0,
            fg3a=stats.get(self.STATS_FG3A, 0) or 0,
            ftm=stats.get(self.STATS_FTM, 0) or 0,
            fta=stats.get(self.STATS_FTA, 0) or 0,
            oreb=stats.get(self.STATS_OREB, 0) or 0,
            dreb=stats.get(self.STATS_DREB, 0) or 0,
            reb=stats.get(self.STATS_REB, 0) or 0,
            ast=stats.get(self.STATS_AST, 0) or 0,
            stl=stats.get(self.STATS_STL, 0) or 0,
            blk=stats.get(self.STATS_BLK, 0) or 0,
            tov=stats.get(self.STATS_TOV, 0) or 0,
            pf=stats.get(self.STATS_PF, 0) or 0,
            plus_minus=stats.get(self.STATS_PLUS_MINUS, 0.0) or 0.0,
            minutes=minutes_str
        )
    
    @staticmethod
    def _parse_iso_minutes(iso_duration: str) -> str:
        """Parse ISO 8601 duration to MM:SS format."""
        if not iso_duration or not isinstance(iso_duration, str):
            return "0:00"
        
        # Handle already-formatted strings
        if ':' in iso_duration and not iso_duration.startswith('PT'):
            return iso_duration
        
        # Parse ISO 8601: PT{M}M{S}.{sub}S
        match = re.match(r'PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', iso_duration)
        if not match:
            return "0:00"
        
        minutes = int(match.group(1) or 0)
        seconds = int(float(match.group(2) or 0))
        
        return f"{minutes}:{seconds:02d}"
    
    @staticmethod
    def parse_clock_seconds(clock_str: str) -> float:
        """
        Parse game clock to seconds remaining in period.
        Used for garbage time detection.
        
        Args:
            clock_str: ISO 8601 format like "PT05M30.00S" or "5:30"
        
        Returns:
            Seconds remaining as float
        """
        if not clock_str:
            return 0.0
        
        # Handle ISO 8601: PT05M30.00S
        if clock_str.startswith('PT'):
            match = re.match(r'PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', clock_str)
            if match:
                mins = int(match.group(1) or 0)
                secs = float(match.group(2) or 0)
                return mins * 60 + secs
        
        # Handle MM:SS format
        if ':' in clock_str:
            parts = clock_str.split(':')
            try:
                mins = int(parts[0])
                secs = float(parts[1]) if len(parts) > 1 else 0
                return mins * 60 + secs
            except ValueError:
                pass
        
        return 0.0


# ============================================================================
# ASYNC ADAPTER (v2.0 - Native aiohttp)
# ============================================================================

class AsyncNBAApiAdapter(NBAApiAdapter):
    """
    Async version of NBA API Adapter using native aiohttp.
    
    v2.0: Pure async implementation - no ThreadPoolExecutor needed.
    Directly hits NBA CDN endpoints for minimal latency.
    """
    
    VERSION = "2.0.0"
    
    def __init__(self):
        self._session: Optional[Any] = None
        self._aiohttp_available = False
        
        try:
            import aiohttp
            self._aiohttp_available = True
        except ImportError:
            logger.warning("aiohttp not installed - falling back to ThreadPoolExecutor")
    
    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None and self._aiohttp_available:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def fetch_scoreboard_async(self) -> List[NormalizedGameInfo]:
        """
        Fetch today's scoreboard using native aiohttp.
        Falls back to nba_api library if aiohttp unavailable.
        """
        if self._aiohttp_available:
            return await self._fetch_scoreboard_native()
        else:
            return await self._fetch_scoreboard_fallback()
    
    async def _fetch_scoreboard_native(self) -> List[NormalizedGameInfo]:
        """Native aiohttp scoreboard fetch - fastest method."""
        try:
            session = await self._get_session()
            async with session.get(self.SCOREBOARD_URL) as response:
                if response.status == 200:
                    raw_data = await response.json(content_type=None)
                    return self.normalize_scoreboard(raw_data)
                else:
                    logger.warning(f"Scoreboard fetch returned {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Native scoreboard fetch failed: {e}")
            return await self._fetch_scoreboard_fallback()
    
    async def _fetch_scoreboard_fallback(self) -> List[NormalizedGameInfo]:
        """Fallback using nba_api with ThreadPoolExecutor."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        try:
            from nba_api.live.nba.endpoints import scoreboard
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                sb = await loop.run_in_executor(executor, scoreboard.ScoreBoard)
                raw_data = await loop.run_in_executor(executor, sb.get_dict)
            
            return self.normalize_scoreboard(raw_data)
        except ImportError:
            logger.warning("nba_api not available")
            return []
        except Exception as e:
            logger.error(f"Fallback scoreboard fetch failed: {e}")
            return []
    
    async def fetch_boxscore_async(self, game_id: str) -> Optional[NormalizedBoxScore]:
        """
        Fetch boxscore for a single game using native aiohttp.
        Falls back to nba_api library if aiohttp unavailable.
        """
        if self._aiohttp_available:
            return await self._fetch_boxscore_native(game_id)
        else:
            return await self._fetch_boxscore_fallback(game_id)
    
    async def _fetch_boxscore_native(self, game_id: str) -> Optional[NormalizedBoxScore]:
        """Native aiohttp boxscore fetch - fastest method."""
        try:
            url = self.BOXSCORE_URL_TEMPLATE.format(game_id=game_id)
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    raw_data = await response.json(content_type=None)
                    return self.normalize_boxscore(raw_data)
                else:
                    logger.debug(f"Boxscore {game_id} returned {response.status}")
                    return None
        except Exception as e:
            logger.debug(f"Native boxscore fetch failed for {game_id}: {e}")
            return await self._fetch_boxscore_fallback(game_id)
    
    async def _fetch_boxscore_fallback(self, game_id: str) -> Optional[NormalizedBoxScore]:
        """Fallback using nba_api with ThreadPoolExecutor."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        try:
            from nba_api.live.nba.endpoints import boxscore
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as executor:
                box = await loop.run_in_executor(
                    executor, 
                    lambda: boxscore.BoxScore(game_id=game_id)
                )
                raw_data = await loop.run_in_executor(executor, box.get_dict)
            
            return self.normalize_boxscore(raw_data)
        except Exception as e:
            logger.debug(f"Fallback boxscore fetch failed for {game_id}: {e}")
            return None
    
    async def fetch_all_live_boxscores_async(
        self, 
        game_ids: List[str]
    ) -> Dict[str, Optional[NormalizedBoxScore]]:
        """
        Fetch boxscores for multiple games CONCURRENTLY.
        
        This is the key optimization: instead of fetching one game at a time,
        we fire off all requests simultaneously using asyncio.gather().
        
        With native aiohttp, this is significantly faster than ThreadPoolExecutor.
        """
        import asyncio
        
        if not game_ids:
            return {}
        
        # Fire off all requests concurrently
        tasks = [self.fetch_boxscore_async(gid) for gid in game_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Map results back to game IDs
        boxscores = {}
        for game_id, result in zip(game_ids, results):
            if isinstance(result, Exception):
                logger.debug(f"Boxscore {game_id} failed: {result}")
                boxscores[game_id] = None
            else:
                boxscores[game_id] = result
        
        return boxscores


# ============================================================================
# GARBAGE TIME DETECTION (Enhanced Algorithm)
# ============================================================================

def calculate_garbage_time_factor(
    period: int,
    clock_seconds: float,
    score_margin: int
) -> float:
    """
    Calculate garbage time factor using margin + clock weighting.
    
    This dampens pulse activity during blowouts to prevent "fake" pulses
    when starters are benched and bench players pad stats.
    
    Algorithm:
    - Q4 with 20+ point lead and <5 min left = high garbage time
    - Q4 with 15+ point lead and <3 min left = moderate garbage time
    - OT periods = never garbage time (always competitive)
    
    Args:
        period: Current period (4 = Q4, 5+ = OT)
        clock_seconds: Seconds remaining in period
        score_margin: Absolute score difference
    
    Returns:
        Garbage time factor 0.0 (competitive) to 1.0 (full garbage time)
    """
    # Never garbage time in OT - those are always competitive
    if period > 4:
        return 0.0
    
    # Only applies in Q4
    if period < 4:
        return 0.0
    
    # Q4 garbage time logic
    minutes_remaining = clock_seconds / 60.0
    
    # Blowout: 25+ margin with 6+ minutes left
    if score_margin >= 25 and minutes_remaining > 6:
        return 0.9  # Very high garbage time
    
    # Large lead: 20+ margin with less than 5 minutes
    if score_margin >= 20 and minutes_remaining <= 5:
        return 0.8
    
    # Comfortable lead: 15+ margin with less than 3 minutes  
    if score_margin >= 15 and minutes_remaining <= 3:
        return 0.6
    
    # Moderate lead: 12+ margin with less than 2 minutes
    if score_margin >= 12 and minutes_remaining <= 2:
        return 0.4
    
    # 10+ margin in final minute
    if score_margin >= 10 and minutes_remaining <= 1:
        return 0.3
    
    return 0.0


def is_garbage_time(
    period: int,
    clock_str: str,
    home_score: int,
    away_score: int
) -> bool:
    """
    Simple boolean garbage time check for backward compatibility.
    
    Args:
        period: Current period
        clock_str: Game clock string (ISO or MM:SS)
        home_score: Home team score
        away_score: Away team score
    
    Returns:
        True if game is in garbage time
    """
    clock_seconds = NBAApiAdapter.parse_clock_seconds(clock_str)
    score_margin = abs(home_score - away_score)
    factor = calculate_garbage_time_factor(period, clock_seconds, score_margin)
    return factor >= 0.5


# ============================================================================
# SINGLETON ACCESSOR
# ============================================================================

_adapter_instance: Optional[AsyncNBAApiAdapter] = None


def get_nba_adapter() -> AsyncNBAApiAdapter:
    """Get singleton instance of the NBA API adapter."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = AsyncNBAApiAdapter()
    return _adapter_instance
