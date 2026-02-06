"""
Pydantic Response Models for QuantSight Cloud API
==================================================
Canonical schemas that enforce data contracts between backend and frontend.

Key Features:
- Field aliasing: snake_case (DB) → camelCase (frontend)
- Null safety: None → "" or [] for optional fields
- Type coercion: Consistent types (e.g., jersey_number always str)
- Validation: Reject malformed data at response boundary

Usage:
    @router.get("/player/{player_id}", response_model=PlayerProfileResponse)
    async def get_player(...):
        return firestore_data  # Pydantic auto-validates and transforms
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class PlayerProfileResponse(BaseModel):
    """
    Player profile for frontend consumption.
    Maps Firestore snake_case to frontend camelCase.
    """
    id: str = Field(..., alias="player_id", description="NBA Player ID")
    name: str = Field(..., description="Player full name")
    team: str = Field(..., alias="team_abbreviation", description="Team tricode (e.g., LAL)")
    position: Optional[str] = Field(None, description="Position (PG, SG, SF, PF, C)")
    avatar: str = Field(default="", alias="headshot_url", description="Player headshot URL")
    jersey_number: str = Field(default="", description="Jersey number (as string)")
    height: Optional[str] = None
    weight: Optional[int] = None
    status: str = Field(default="active", description="Player status (active, inactive, injured)")
    is_active: bool = Field(default=True)
    
    class Config:
        populate_by_name = True  # Accept both 'id' and 'player_id'
        json_encoders = {
            type(None): lambda v: ""  # Convert None → ""
        }
    
    @field_validator('jersey_number', mode='before')
    @classmethod
    def coerce_jersey_to_string(cls, v):
        """Ensure jersey_number is always string type"""
        if v is None:
            return ""
        return str(v)


class TeamInfo(BaseModel):
    """Team information for schedule/games"""
    tricode: str = Field(..., description="3-letter team code")
    score: int = Field(default=0)
    wins: int = Field(default=0)
    losses: int = Field(default=0)


class ScheduleGameResponse(BaseModel):
    """
    Clean schedule game response (no duplicate flat fields).
    Frontend MUST use nested structure (game.home_team.tricode).
    """
    gameId: str = Field(..., alias="game_id")
    home_team: TeamInfo
    away_team: TeamInfo
    status: str
    period: int = Field(default=0)
    game_time_utc: Optional[str] = None
    arena: Optional[str] = None
    
    class Config:
        populate_by_name = True


class ScheduleResponse(BaseModel):
    """Schedule endpoint response"""
    games: List[ScheduleGameResponse]
    date: str
    total: int
    source: str = "nba_cdn"


class LiveStats(BaseModel):
    """Live game statistics for a player"""
    pts: int = 0
    reb: int = 0
    ast: int = 0
    fg3m: int = 0
    fga: int = 0
    min: int = 0
    pie: float = 0.0
    ts_pct: float = 0.0
    efg_pct: float = 0.0


class SeasonAverages(BaseModel):
    """Season averages for a player"""
    pts: float = 0.0
    reb: float = 0.0
    ast: float = 0.0
    fg3m: float = 0.0
    fga: float = 0.0
    min: float = 0.0
    ts_pct: float = 0.0


class RosterPlayerResponse(BaseModel):
    """
    Enriched roster player for Matchup Lab.
    Includes live stats if in-game, season averages otherwise.
    """
    player_id: str
    name: str
    team: str
    position: str = ""
    jersey_number: str = ""  # Always string
    avatar: str = ""
    is_active: bool = True
    status: str = "active"
    is_in_game: bool = False
    live_stats: Optional[LiveStats] = None
    season_averages: Optional[SeasonAverages] = None
    
    @field_validator('jersey_number', mode='before')
    @classmethod
    def coerce_jersey(cls, v):
        if v is None:
            return ""
        return str(v)


class RosterResponse(BaseModel):
    """Roster endpoint response"""
    team: str
    game_id: Optional[str] = None
    roster: List[RosterPlayerResponse]
    count: int
    has_live_stats: bool = False


class PlayerSummary(BaseModel):
    """Aggregated player stats for boxscore"""
    player_id: str
    name: str
    team: str
    position: str = ""
    jersey_number: str = ""
    pts: int = 0
    reb: int = 0
    ast: int = 0
    min: int = 0
    fgm: int = 0
    fga: int = 0
    fg_pct: float = 0.0
    fg3m: int = 0
    fg3a: int = 0
    fg3_pct: float = 0.0
    ftm: int = 0
    fta: int = 0
    ft_pct: float = 0.0
    stl: int = 0
    blk: int = 0
    tov: int = 0
    pf: int = 0
    plus_minus: int = 0


class TeamBoxscore(BaseModel):
    """Team boxscore with aggregated player stats"""
    abbreviation: str
    players: List[PlayerSummary]
    team_totals: Optional[Dict[str, Any]] = None


class BoxscoreResponse(BaseModel):
    """Boxscore endpoint response with aggregated stats"""
    game_id: str
    home_team: TeamBoxscore
    away_team: TeamBoxscore
    total_players: int


class GameLogEntry(BaseModel):
    """Individual game log (for non-aggregated endpoints)"""
    id: str
    player_id: str
    game_id: str
    game_date: str
    team: str
    opponent: str
    pts: int = 0
    reb: int = 0
    ast: int = 0
    min: int = 0
    # ... add more fields as needed


class GameLogsResponse(BaseModel):
    """Game logs endpoint response"""
    logs: List[GameLogEntry]
    count: int
    filters_applied: Dict[str, Any]


class MatchupAnalysisResponse(BaseModel):
    """Matchup analysis response (for when engine is available)"""
    success: bool
    game_id: Optional[str] = None
    game: str
    generated_at: Optional[str] = None
    matchup_context: Dict[str, Any] = {}
    projections: List[Dict[str, Any]] = []
    insights: Dict[str, Any] = {}
    ai_powered: bool = False
    fallback: bool = False
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str
    error_code: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
