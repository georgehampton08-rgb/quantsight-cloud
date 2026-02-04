"""
Live Pulse Cache - Cloud Edition with VPC-Enabled NBA API Access
=================================================================
Ported from desktop implementation for Cloud Run with VPC connectivity.

Single producer updates cache every 10s via NBA API (through VPC connector).
All SSE clients stream from cache - no per-client NBA API hits.

Usage:
    # Start producer (once at server startup)
    pulse_cache = get_pulse_cache()
    pulse_cache.start_producer()
    
    # In SSE endpoint (all clients share this)
    @router.get("/live/stream")
    async def live_stream():
        async def generator():
            while True:
                yield pulse_cache.get_latest()
                await asyncio.sleep(1)
        return EventSourceResponse(generator())
"""
import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict

# Import shared_core for calculations (Source of Truth)
import sys
from pathlib import Path

# Ensure shared_core is importable
_backend_path = Path(__file__).parent.parent
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

try:
    from shared_core.engines.pie_calculator import calculate_live_pie
    from shared_core.calculators.advanced_stats import calculate_true_shooting, calculate_effective_fg
    SHARED_CORE_AVAILABLE = True
except ImportError:
    SHARED_CORE_AVAILABLE = False
    # Fallback inline
    def calculate_live_pie(pts=0, fgm=0, fga=0, ftm=0, fta=0, oreb=0, dreb=0, ast=0, stl=0, blk=0, pf=0, tov=0):
        """Fallback PIE calculation"""
        if fga == 0:
            return 0.0
        return min(1.0, (pts + fgm + ftm + oreb * 2 + dreb + ast + stl + blk - (fga - fgm) - (fta - ftm) - tov) / 100.0)
    
    def calculate_true_shooting(pts, fga, fta):
        return pts / (2 * (fga + 0.44 * fta)) if (fga + 0.44 * fta) > 0 else 0.0
    
    def calculate_effective_fg(fgm, fg3m, fga):
        return (fgm + 0.5 * fg3m) / fga if fga > 0 else 0.0

logger = logging.getLogger(__name__)


def _parse_iso_minutes(iso_duration: str) -> str:
    """
    Parse ISO 8601 duration to MM:SS format.
    Converts 'PT25M30.00S' -> '25:30'
    """
    import re
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


@dataclass
class LivePlayerStat:
    """In-game player statistics with semantic insight enrichment."""
    player_id: str
    name: str
    team: str
    pts: int = 0
    reb: int = 0
    ast: int = 0
    stl: int = 0
    blk: int = 0
    min: str = "0:00"
    pie: float = 0.0
    plus_minus: float = 0.0
    ts_pct: float = 0.0
    efg_pct: float = 0.0
    heat_status: Literal['hot', 'cold', 'steady'] = 'steady'
    efficiency_trend: Literal['surging', 'steady', 'dipping'] = 'steady'
    
    @classmethod
    def from_nba_api(cls, player_data: Dict, team_tricode: str) -> 'LivePlayerStat':
        """Convert NBA API player data to LivePlayerStat with True PIE."""
        stats = player_data.get('statistics', {})
        
        # Extract counting stats
        pts = stats.get('points', 0) or 0
        fgm = stats.get('fieldGoalsMade', 0) or 0
        fga = stats.get('fieldGoalsAttempted', 0) or 0
        ftm = stats.get('freeThrowsMade', 0) or 0
        fta = stats.get('freeThrowsAttempted', 0) or 0
        oreb = stats.get('reboundsOffensive', 0) or 0
        dreb = stats.get('reboundsDefensive', 0) or 0
        reb = stats.get('reboundsTotal', 0) or 0
        ast = stats.get('assists', 0) or 0
        stl = stats.get('steals', 0) or 0
        blk = stats.get('blocks', 0) or 0
        tov = stats.get('turnovers', 0) or 0
        pf = stats.get('foulsPersonal', 0) or 0
        plus_minus = stats.get('plusMinusPoints', 0.0) or 0.0
        fg3m = stats.get('threePointersMade', 0) or 0
        
        # Use shared_core for calculations
        pie = calculate_live_pie(
            pts=pts, fgm=fgm, fga=fga, ftm=ftm, fta=fta,
            oreb=oreb, dreb=dreb, ast=ast, stl=stl, blk=blk,
            pf=pf, tov=tov
        )
        
        ts_pct = round(calculate_true_shooting(pts, fga, fta), 4)
        efg_pct = round(calculate_effective_fg(fgm, fg3m, fga), 4)
        minutes_str = _parse_iso_minutes(stats.get('minutes', 'PT0M0S'))
        
        # Determine heat status
        heat_status: Literal['hot', 'cold', 'steady'] = 'steady'
        if pie >= 0.25:
            heat_status = 'hot'
        elif pie < 0.05:
            heat_status = 'cold'
        
        efficiency_trend: Literal['surging', 'steady', 'dipping'] = 'steady'
        if ts_pct >= 0.65:
            efficiency_trend = 'surging'
        elif ts_pct < 0.45 and fga >= 5:
            efficiency_trend = 'dipping'
        
        return cls(
            player_id=str(player_data.get('personId', '')),
            name=player_data.get('name', 'Unknown'),
            team=team_tricode,
            pts=pts,
            reb=reb,
            ast=ast,
            stl=stl,
            blk=blk,
            min=minutes_str,
            pie=pie,
            plus_minus=plus_minus,
            ts_pct=ts_pct,
            efg_pct=efg_pct,
            heat_status=heat_status,
            efficiency_trend=efficiency_trend
        )


@dataclass
class LiveGameState:
    """Live game state for streaming."""
    game_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    clock: str
    period: int
    status: str  # 'LIVE', 'FINAL', 'UPCOMING'
    leaders: List[Dict]
    last_updated: str
    is_garbage_time: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)


class LivePulseCache:
    """
    Hot cache for live game data (Cloud Edition with VPC).
    Single producer updates cache from NBA API via VPC connector.
    Multiple SSE consumers read from cache.
    """
    
    VERSION = "2.0.0-cloud"
    POLL_INTERVAL_SECONDS = 10
    PIE_DELTA_THRESHOLD = 0.01
    PULSE_COOLDOWN_SECONDS = 3
    
    def __init__(self):
        self._cache: Dict[str, LiveGameState] = {}
        self._cache_lock = threading.RLock()
        self._running = False
        self._producer_thread: Optional[threading.Thread] = None
        self._last_update: Optional[datetime] = None
        self._update_count = 0
        
        # Track stat changes for gold pulse effect
        self._previous_stats: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._stat_changes: Dict[str, List[str]] = defaultdict(list)
        self._pulse_cooldowns: Dict[str, datetime] = {}
        
        logger.info(f"🔥 LivePulseCache v{self.VERSION} initialized (VPC-enabled)")
    
    def get_latest(self) -> Dict[str, Any]:
        """Get current cache state (thread-safe)."""
        with self._cache_lock:
            games = [g.to_dict() for g in self._cache.values()]
            return {
                "games": games,
                "meta": {
                    "timestamp": datetime.now().isoformat(),
                    "game_count": len(games),
                    "update_cycle": self._update_count,
                    "live_count": sum(1 for g in games if g['status'] == 'LIVE')
                },
                "changes": dict(self._stat_changes)
            }
    
    def get_leaders(self, limit: int = 10) -> List[Dict]:
        """Get top players across all live games by PIE."""
        with self._cache_lock:
            all_leaders = []
            for game in self._cache.values():
                if game.status == 'LIVE':
                    all_leaders.extend(game.leaders)
            
            all_leaders.sort(key=lambda x: x.get('pie', 0), reverse=True)
            return all_leaders[:limit]
    
    def _detect_stat_changes(self, game_id: str, new_leaders: List[Dict]):
        """Detect which players had stat changes for gold pulse effect."""
        now = datetime.now()
        changes = []
        
        for player in new_leaders:
            pid = player.get('player_id')
            if not pid:
                continue
            
            # Check cooldown
            if pid in self._pulse_cooldowns:
                if now < self._pulse_cooldowns[pid]:
                    continue
            
            prev = self._previous_stats[game_id].get(pid, {})
            new_pie = player.get('pie', 0)
            old_pie = prev.get('pie', 0)
            
            # Only pulse if PIE increased by threshold
            if new_pie - old_pie >= self.PIE_DELTA_THRESHOLD:
                changes.append(pid)
                self._pulse_cooldowns[pid] = now + timedelta(seconds=self.PULSE_COOLDOWN_SECONDS)
            
            # Update previous stats
            self._previous_stats[game_id][pid] = {'pie': new_pie}
        
        self._stat_changes[game_id] = changes
        
        # Clean up expired cooldowns
        expired = [pid for pid, end_time in self._pulse_cooldowns.items() if now >= end_time]
        for pid in expired:
            del self._pulse_cooldowns[pid]
    
    def _update_cache(self):
        """Fetch latest data from NBA API and update cache."""
        try:
            # NBA API call via VPC connector
            from nba_api.live.nba.endpoints import scoreboard, boxscore
            
            # Rate limit
            time.sleep(0.6)
            
            sb = scoreboard.ScoreBoard()
            sb_data = sb.get_dict()
            games = sb_data.get('scoreboard', {}).get('games', [])
            
            with self._cache_lock:
                for game in games:
                    game_id = game.get('gameId')
                    status_code = game.get('gameStatus', 1)
                    
                    # Normalize status
                    if status_code == 1:
                        status = 'UPCOMING'
                    elif status_code == 2:
                        status = 'LIVE'
                    else:
                        status = 'FINAL'
                    
                    home = game.get('homeTeam', {})
                    away = game.get('awayTeam', {})
                    
                    # For LIVE games, fetch detailed box score
                    leaders = []
                    if status == 'LIVE':
                        try:
                            time.sleep(0.6)  # Rate limit
                            box = boxscore.BoxScore(game_id=game_id)
                            box_data = box.get_dict()
                            leaders = self._extract_leaders(box_data)
                        except Exception as e:
                            logger.debug(f"Box score fetch failed for {game_id}: {e}")
                    
                    # Detect stat changes
                    self._detect_stat_changes(game_id, leaders)
                    
                    # Garbage time detection
                    home_score = home.get('score', 0)
                    away_score = away.get('score', 0)
                    period = game.get('period', 0)
                    score_margin = abs(home_score - away_score)
                    is_garbage_time = period >= 4 and score_margin > 20
                    
                    self._cache[game_id] = LiveGameState(
                        game_id=game_id,
                        home_team=home.get('teamTricode', '???'),
                        away_team=away.get('teamTricode', '???'),
                        home_score=home_score,
                        away_score=away_score,
                        clock=game.get('gameStatusText', 'TBD'),
                        period=period,
                        status=status,
                        leaders=leaders[:10],
                        last_updated=datetime.now().isoformat(),
                        is_garbage_time=is_garbage_time
                    )
                
                self._last_update = datetime.now()
                self._update_count += 1
                
                live_count = sum(1 for g in self._cache.values() if g.status == 'LIVE')
                if self._update_count % 6 == 0:  # Log every minute
                    logger.info(f"🔄 VPC Pulse #{self._update_count}: {len(self._cache)} games, {live_count} live")
                    
        except Exception as e:
            logger.error(f"❌ Cache update failed: {e}")
    
    def _extract_leaders(self, box_data: Dict) -> List[Dict]:
        """Extract top players from box score data."""
        leaders = []
        game = box_data.get('game', {})
        
        for team in [game.get('homeTeam', {}), game.get('awayTeam', {})]:
            team_tricode = team.get('teamTricode', '???')
            
            for player in team.get('players', []):
                if player.get('status') != 'ACTIVE':
                    continue
                
                stat = LivePlayerStat.from_nba_api(player, team_tricode)
                leaders.append({
                    'player_id': stat.player_id,
                    'name': stat.name,
                    'team': stat.team,
                    'pie': stat.pie,
                    'plus_minus': stat.plus_minus,
                    'ts_pct': stat.ts_pct,
                    'efg_pct': stat.efg_pct,
                    'heat_status': stat.heat_status,
                    'efficiency_trend': stat.efficiency_trend,
                    'stats': {
                        'pts': stat.pts,
                        'reb': stat.reb,
                        'ast': stat.ast,
                        'stl': stat.stl,
                        'blk': stat.blk
                    },
                    'min': stat.min
                })
        
        # Sort by PIE
        leaders.sort(key=lambda x: x['pie'], reverse=True)
        return leaders
    
    def _producer_loop(self):
        """Background producer loop."""
        logger.info("🚀 VPC Pulse producer started")
        
        while self._running:
            self._update_cache()
            time.sleep(self.POLL_INTERVAL_SECONDS)
        
        logger.info("🛑 VPC Pulse producer stopped")
    
    def start_producer(self) -> threading.Thread:
        """Start the background producer thread."""
        if self._running:
            logger.warning("Producer already running")
            return self._producer_thread
        
        self._running = True
        self._producer_thread = threading.Thread(
            target=self._producer_loop,
            daemon=True,
            name="LivePulseProducerCloud"
        )
        self._producer_thread.start()
        return self._producer_thread
    
    def stop_producer(self):
        """Stop the producer thread."""
        self._running = False
        if self._producer_thread:
            self._producer_thread.join(timeout=15)
    
    def get_status(self) -> Dict:
        """Get cache status for health checks."""
        return {
            "running": self._running,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "update_count": self._update_count,
            "cache_size": len(self._cache),
            "live_games": sum(1 for g in self._cache.values() if g.status == 'LIVE'),
            "poll_interval_seconds": self.POLL_INTERVAL_SECONDS,
            "version": self.VERSION
        }


# Singleton instance
_pulse_cache: Optional[LivePulseCache] = None


def get_pulse_cache() -> LivePulseCache:
    """Get or create the global pulse cache singleton."""
    global _pulse_cache
    if _pulse_cache is None:
        _pulse_cache = LivePulseCache()
    return _pulse_cache
