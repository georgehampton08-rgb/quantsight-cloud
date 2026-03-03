import logging
import requests
import datetime
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- UNIFIED DATA MODELS ---

class PlayEvent(BaseModel):
    playId: str
    sequenceNumber: int
    eventType: str
    description: str
    period: int
    clock: str
    homeScore: int
    awayScore: int
    teamId: Optional[str] = None
    teamTricode: Optional[str] = None
    
    # Participant Data
    primaryPlayerId: Optional[str] = None
    primaryPlayerName: Optional[str] = None
    secondaryPlayerId: Optional[str] = None
    secondaryPlayerName: Optional[str] = None
    involvedPlayers: List[str] = Field(default_factory=list)
    
    # Shot/Action Data
    isScoringPlay: bool = False
    isShootingPlay: bool = False
    pointsValue: int = 0
    shotDistance: Optional[float] = None
    shotArea: Optional[str] = None
    shotResult: Optional[str] = None  # "Made" or "Missed"
    
    # Spatial Data
    coordinateX: Optional[float] = None
    coordinateY: Optional[float] = None
    
    # Raw Data for debugging/fallback
    rawData: Dict[str, Any] = Field(default_factory=dict)
    source: str

# --- MAPPERS ---

def map_espn_to_unified(espn_play: Dict[str, Any]) -> PlayEvent:
    play_id = str(espn_play.get("id", ""))
    seq_num = int(espn_play.get("sequenceNumber", 0))
    event_type = espn_play.get("type", {}).get("text", "Unknown")
    description = espn_play.get("text", "")
    period = espn_play.get("period", {}).get("number", 0)
    clock = espn_play.get("clock", {}).get("displayValue", "0:00")
    home_score = espn_play.get("homeScore", 0)
    away_score = espn_play.get("awayScore", 0)
    team_id = str(espn_play.get("team", {}).get("id", ""))
    
    is_scoring = espn_play.get("scoringPlay", False)
    is_shooting = espn_play.get("shootingPlay", False)
    points_val = espn_play.get("scoreValue", 0)
    
    coord_x = espn_play.get("coordinate", {}).get("x", None)
    coord_y = espn_play.get("coordinate", {}).get("y", None)
    
    # Fix ESPN coordinates: they are sometimes wildly large (e.g. -214748340) for non-shot plays.
    # We should only trust them if x and y are within reasonable basketball court bounds (0 to 100 roughly).
    # ESPN court mapping usually scales X 0-50, Y 0-94. Let's just nullify crazy values.
    if coord_x is not None and (coord_x < -100 or coord_x > 200): coord_x = None
    if coord_y is not None and (coord_y < -100 or coord_y > 200): coord_y = None

    participants = espn_play.get("participants", [])
    primary_id = None
    secondary_id = None
    involved = []
    
    if len(participants) > 0:
        primary_id = str(participants[0].get("athlete", {}).get("id", ""))
        involved.append(primary_id)
    if len(participants) > 1:
        secondary_id = str(participants[1].get("athlete", {}).get("id", ""))
        involved.append(secondary_id)
    for p in participants[2:]:
        involved.append(str(p.get("athlete", {}).get("id", "")))
        
    shot_result = None
    if is_shooting:
        shot_result = "Made" if is_scoring else "Missed"

    return PlayEvent(
        playId=play_id,
        sequenceNumber=seq_num,
        eventType=event_type,
        description=description,
        period=period,
        clock=clock,
        homeScore=home_score,
        awayScore=away_score,
        teamId=team_id,
        primaryPlayerId=primary_id,
        secondaryPlayerId=secondary_id,
        involvedPlayers=involved,
        isScoringPlay=is_scoring,
        isShootingPlay=is_shooting,
        pointsValue=points_val,
        shotResult=shot_result,
        coordinateX=coord_x,
        coordinateY=coord_y,
        rawData=espn_play,
        source="espn"
    )

def map_nba_cdn_to_unified(cdn_play: Dict[str, Any]) -> PlayEvent:
    seq_num = cdn_play.get("actionNumber", 0)
    play_id = str(seq_num)  # CDN doesn't have a unique ID string, use seq num
    
    action_type = cdn_play.get("actionType", "")
    sub_type = cdn_play.get("subType", "")
    event_type = f"{action_type} {sub_type}".strip()
    
    # CDN Clock is like PT12M00.00S
    raw_clock = cdn_play.get("clock", "")
    clock_cleaned = raw_clock.replace("PT", "").replace("M", ":").replace(".00S", "").replace("S", "")
    if ":" in clock_cleaned:
        parts = clock_cleaned.split(":")
        if len(parts) == 2 and "." in parts[1]:
            parts[1] = parts[1].split(".")[0] # remove decimals
        clock = f"{parts[0]}:{parts[1].zfill(2)}"
    else:
        clock = clock_cleaned

    period = cdn_play.get("period", 0)
    description = cdn_play.get("description", "")
    home_score = int(cdn_play.get("scoreHome", 0) or 0)
    away_score = int(cdn_play.get("scoreAway", 0) or 0)
    
    team_tricode = cdn_play.get("teamTricode", None)
    
    is_scoring = cdn_play.get("isFieldGoal", 0) == 1 and cdn_play.get("shotResult") == "Made"
    is_shooting = cdn_play.get("actionType") in ["2pt", "3pt", "freethrow"]
    points_val = cdn_play.get("pointsTotal", 0)
    
    shot_distance = cdn_play.get("shotDistance", None)
    shot_area = cdn_play.get("area", None)
    shot_result = cdn_play.get("shotResult", None)
    
    coord_x = cdn_play.get("x", None)
    coord_y = cdn_play.get("y", None)
    
    primary_id = str(cdn_play.get("personId", "")) if cdn_play.get("personId") else None
    primary_name = cdn_play.get("playerNameI", None)
    
    secondary_id = str(cdn_play.get("assistPersonId", "")) if cdn_play.get("assistPersonId") else None
    secondary_name = cdn_play.get("assistPlayerNameInitial", None)
    
    involved = []
    if cdn_play.get("personIdsFilter"):
        involved = [str(pid) for pid in cdn_play.get("personIdsFilter", [])]
        
    return PlayEvent(
        playId=play_id,
        sequenceNumber=seq_num,
        eventType=event_type,
        description=description,
        period=period,
        clock=clock,
        homeScore=home_score,
        awayScore=away_score,
        teamTricode=team_tricode,
        primaryPlayerId=primary_id,
        primaryPlayerName=primary_name,
        secondaryPlayerId=secondary_id,
        secondaryPlayerName=secondary_name,
        involvedPlayers=involved,
        isScoringPlay=is_scoring,
        isShootingPlay=is_shooting,
        pointsValue=points_val,
        shotDistance=shot_distance,
        shotArea=shot_area,
        shotResult=shot_result,
        coordinateX=coord_x,
        coordinateY=coord_y,
        rawData=cdn_play,
        source="nba_cdn"
    )

# --- API CLIENTS ---

class NBAPlayByPlayClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        })
        
    def fetch_live_game_ids(self) -> List[Dict[str, Any]]:
        """Returns a list of dicts with 'game_id', 'status', 'home', 'away' from ESPN"""
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        try:
            res = self.session.get(url, timeout=5)
            res.raise_for_status()
            events = res.json().get("events", [])
            live_games = []
            for event in events:
                is_live_or_recent = event.get("status", {}).get("type", {}).get("state") in ["in", "post", "pre"]
                if is_live_or_recent: # Tracking active, finished, and upcoming games
                    live_games.append({
                        "game_id": event["id"],
                        "name": event["name"],
                        "status": event.get("status", {}).get("type", {}).get("description"),
                        "state": event.get("status", {}).get("type", {}).get("state")  # 'in', 'post', 'pre'
                    })
            return live_games
        except Exception as e:
            logger.error(f"Failed to fetch ESPN schedule: {e}")
            return []

    def fetch_espn_plays(self, espn_game_id: str) -> List[PlayEvent]:
        """Fetch plays from ESPN and map to unified schema"""
        url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espn_game_id}"
        res = self.session.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()
        plays_raw = data.get("plays", [])
        
        unified_plays = []
        for p in plays_raw:
            try:
                unified_plays.append(map_espn_to_unified(p))
            except Exception as e:
                logger.error(f"Error mapping ESPN play {p.get('id')}: {e}")
                
        # Return sorted by sequence number
        return sorted(unified_plays, key=lambda x: x.sequenceNumber)

    def fetch_nba_cdn_plays(self, nba_game_id: str) -> List[PlayEvent]:
        """Fallback: Fetch from CDN and map to unified schema"""
        url = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{nba_game_id}.json"
        res = self.session.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()
        actions = data.get("game", {}).get("actions", [])
        
        unified_plays = []
        for a in actions:
            try:
                unified_plays.append(map_nba_cdn_to_unified(a))
            except Exception as e:
                logger.error(f"Error mapping NBA CDN action {a.get('actionNumber')}: {e}")
                
        return sorted(unified_plays, key=lambda x: x.sequenceNumber)

pbp_client = NBAPlayByPlayClient()
