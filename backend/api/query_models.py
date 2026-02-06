"""
Pydantic Query Models for QuantSight Cloud API
===============================================
Input validation for query parameters and path variables.

Key Features:
- Pattern validation: regex for IDs, dates, team codes
- Range validation: min/max lengths, numeric bounds
- Cross-field validation: date ranges, dependent params
- Helpful error messages: 422 responses with specific issues

Usage:
    from fastapi import Depends
    from api.query_models import GameLogsQuery
    
    @router.get("/game-logs")
    async def get_game_logs(query: GameLogsQuery = Depends()):
        # query.player_id is guaranteed valid or None
        # query.team_id matches ^[A-Z]{3}$ or is None
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date as date_type


class PlayerSearchQuery(BaseModel):
    """Query parameters for player search"""
    q: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Search query string (1-50 characters)"
    )
    is_active: bool = Field(
        default=True,
        description="Filter for active players only"
    )
    
    @field_validator('q')
    @classmethod
    def validate_query(cls, v):
        if v is not None and v.strip() == "":
            raise ValueError("Query string cannot be empty or whitespace")
        return v.strip() if v else None


class GameLogsQuery(BaseModel):
    """Query parameters for game logs endpoint"""
    player_id: Optional[str] = Field(
        None,
        pattern=r'^\d+$',
        min_length=1,
        max_length=20,
        description="NBA Player ID (numeric string)"
    )
    team_id: Optional[str] = Field(
        None,
        pattern=r'^[A-Z]{3}$',
        description="Team abbreviation (3 uppercase letters, e.g., LAL)"
    )
    start_date: Optional[str] = Field(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Start date in YYYY-MM-DD format"
    )
    end_date: Optional[str] = Field(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="End date in YYYY-MM-DD format"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of logs to return (1-100)"
    )
    
    @model_validator(mode='after')
    def validate_date_range(self):
        """Ensure end_date is after start_date"""
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be greater than or equal to start_date")
        return self


class ScheduleQuery(BaseModel):
    """Query parameters for schedule endpoint"""
    date: Optional[str] = Field(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Date in YYYY-MM-DD format (default: today)"
    )
    force_refresh: bool = Field(
        default=False,
        description="Force fresh data, bypass cache"
    )


class MatchupAnalysisQuery(BaseModel):
    """Query parameters for matchup analysis"""
    game_id: Optional[str] = Field(None, description="Game ID (optional)")
    home_team: str = Field(
        ...,
        pattern=r'^[A-Z]{3}$',
        description="Home team abbreviation (required)"
    )
    away_team: str = Field(
        ...,
        pattern=r'^[A-Z]{3}$',
        description="Away team abbreviation (required)"
    )
    
    @model_validator(mode='after')
    def validate_teams_differ(self):
        """Ensure home and away teams are different"""
        if self.home_team == self.away_team:
            raise ValueError("home_team and away_team must be different")
        return self


class RosterQuery(BaseModel):
    """Query parameters for roster endpoints"""
    active_only: bool = Field(
        default=False,
        description="Only return players currently in game (for Matchup Lab)"
    )
    game_id: Optional[str] = Field(
        None,
        description="Optional game_id to filter live stats"
    )


class TeamIdPath(BaseModel):
    """Path parameter validation for team_id"""
    team_id: str = Field(
        ...,
        pattern=r'^[A-Z]{3}$',
        description="3-letter team abbreviation (uppercase)"
    )


class PlayerIdPath(BaseModel):
    """Path parameter validation for player_id"""
    player_id: str = Field(
        ...,
        pattern=r'^\d+$',
        min_length=1,
        max_length=20,
        description="NBA Player ID (numeric string)"
    )


class GameIdPath(BaseModel):
    """Path parameter validation for game_id"""
    game_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="NBA Game ID"
    )


class DateRangeQuery(BaseModel):
    """Reusable date range validation"""
    start_date: Optional[str] = Field(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$'
    )
    end_date: Optional[str] = Field(
        None,
        pattern=r'^\d{4}-\d{2}-\d{2}$'
    )
    
    @model_validator(mode='after')
    def validate_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self
