"""Public API response models — typed schemas for player, team, and game endpoints."""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict


# ── Team Models ────────────────────────────────────────────────────────────

class TeamRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    name: str = ""
    abbreviation: str = ""


class Division(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    teams: List[TeamRef] = []


class Conference(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    divisions: List[Division] = []


class TeamsResponse(BaseModel):
    """Response model for GET /teams."""
    model_config = ConfigDict(extra="ignore")

    conferences: List[Conference] = []


# ── Player Models ──────────────────────────────────────────────────────────

class PlayerStats(BaseModel):
    model_config = ConfigDict(extra="allow")

    ppg: float = 0.0
    rpg: float = 0.0
    apg: float = 0.0
    confidence: Optional[float] = None
    trend: Optional[List[float]] = None


class PlayerProfile(BaseModel):
    """Response model for GET /players/{player_id}."""
    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    team: str = ""
    position: str = ""
    avatar: str = ""
    height: Optional[str] = None
    weight: Optional[str] = None
    experience: Optional[str] = None
    stats: Optional[PlayerStats] = None
    narrative: Optional[str] = None
    hitProbability: Optional[float] = None
    impliedOdds: Optional[Any] = None


class PlayerSearchResult(BaseModel):
    """Single player result for GET /players/search."""
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    name: str = ""
    team: str = ""
    position: str = ""
    avatar: str = ""


# ── Schedule Models ────────────────────────────────────────────────────────

class ScheduleTeam(BaseModel):
    model_config = ConfigDict(extra="allow")

    tricode: str = ""
    score: int = 0
    wins: int = 0
    losses: int = 0


class ScheduleGame(BaseModel):
    model_config = ConfigDict(extra="allow")

    gameId: Optional[str] = None
    game_code: Optional[str] = None
    home: str = ""
    away: str = ""
    home_score: int = 0
    away_score: int = 0
    status: str = "SCHEDULED"
    time: Optional[str] = None
    period: int = 0
    started: bool = False
    game_time_utc: Optional[str] = None
    home_team: Optional[ScheduleTeam] = None
    away_team: Optional[ScheduleTeam] = None


class ScheduleResponse(BaseModel):
    """Response model for GET /schedule."""
    model_config = ConfigDict(extra="ignore")

    games: List[ScheduleGame] = []
    date: str = ""
    total: int = 0


# ── Matchup Models ─────────────────────────────────────────────────────────

class MatchupInsights(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: Optional[str] = None
    top_plays: Optional[List[Any]] = None
    fade_plays: Optional[List[Any]] = None
    ai_powered: bool = False


class MatchupAnalyzeResponse(BaseModel):
    """Response model for GET /matchup/analyze."""
    model_config = ConfigDict(extra="allow")

    success: bool = False
    game_id: Optional[str] = None
    game: Optional[str] = None
    generated_at: Optional[str] = None
    matchup_context: Optional[Dict[str, Any]] = None
    projections: List[Any] = []
    insights: Optional[MatchupInsights] = None
    ai_powered: bool = False
    fallback: Optional[bool] = None
    error: Optional[str] = None
