"""
Pydantic Data Schemas for Aegis Integrity Enforcement
Validates all data before database insertion
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from datetime import date


class PlayerStatsSchema(BaseModel):
    """Strict schema for player statistics - enforced on all data"""
    
    model_config = ConfigDict(extra='forbid')  # Reject unknown fields
    
    player_id: str = Field(..., min_length=1, description="NBA Player ID")
    name: str = Field(..., min_length=2)
    season: str = Field(..., pattern=r'^\d{4}-\d{2}$')
    
    # Core stats
    games: int = Field(ge=0, le=82, description="Games played")
    points_avg: float = Field(ge=0, le=50, description="Points per game")
    rebounds_avg: float = Field(ge=0, le=30)
    assists_avg: float = Field(ge=0, le=20)
    
    # Percentages (0-1 range)
    fg_pct: Optional[float] = Field(None, ge=0, le=1)
    three_p_pct: Optional[float] = Field(None, ge=0, le=1)
    ft_pct: Optional[float] = Field(None, ge=0, le=1)
    
    # Optional advanced stats
    steals_avg: Optional[float] = Field(None, ge=0)
    blocks_avg: Optional[float] = Field(None, ge=0)
    turnovers_avg: Optional[float] = Field(None, ge=0)
    
    @field_validator('season')
    @classmethod
    def validate_season_range(cls, v):
        start_year = int(v.split('-')[0])
        if start_year < 2010 or start_year > 2026:
            raise ValueError('Season must be between 2010-2026')
        return v
    
    @field_validator('points_avg', 'rebounds_avg', 'assists_avg')
    @classmethod
    def validate_reasonable_averages(cls, v):
        # Sanity check: detect clearly corrupted data
        if v > 100:  # No player averages 100+ in any stat
            raise ValueError(f'Value appears corrupted: {v}')
        return v


class TeamStatsSchema(BaseModel):
    """Strict schema for team statistics"""
    
    model_config = ConfigDict(extra='forbid')
    
    team_id: str = Field(..., min_length=1)
    name: str
    season: str
    wins: int = Field(ge=0, le=82)
    losses: int = Field(ge=0, le=82)
    
    # Ratings
    offensive_rating: Optional[float] = Field(None, ge=80, le=130)
    defensive_rating: Optional[float] = Field(None, ge=80, le=130)
    net_rating: Optional[float] = Field(None, ge=-30, le=30)
    pace: Optional[float] = Field(None, ge=85, le=115)


class PlayerProfileSchema(BaseModel):
    """Schema for player profile data"""
    
    model_config = ConfigDict(extra='allow')  # Allow additional fields
    
    player_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=2)
    position: Optional[str] = Field(None, pattern=r'^(PG|SG|SF|PF|C|G|F)$')
    team_id: Optional[str] = None
    jersey_number: Optional[int] = Field(None, ge=0, le=99)
    status: Optional[str] = Field(None, pattern=r'^(Active|Inactive|Injured)$')
    
    # Physical attributes
    height: Optional[str] = None
    weight: Optional[int] = Field(None, ge=150, le=400)
    
    # Background
    college: Optional[str] = None
    draft_year: Optional[int] = Field(None, ge=1950, le=2026)
    draft_round: Optional[int] = Field(None, ge=1, le=2)
    draft_number: Optional[int] = Field(None, ge=1, le=60)


class ScheduleGameSchema(BaseModel):
    """Schema for schedule game data"""
    
    game_id: str
    home_team: str
    away_team: str  
    game_time: str
    status: str = Field(..., pattern=r'^(UPCOMING|LIVE|FINAL)$')
    
    # Optional scores
    home_score: Optional[int] = Field(None, ge=0)
    away_score: Optional[int] = Field(None, ge=0)


class InjuryReportSchema(BaseModel):
    """Schema for injury reports"""
    
    player_id: str
    player_name: str
    team: str
    status: str = Field(..., pattern=r'^(Out|Doubtful|Questionable|Probable|Day-to-Day)$')
    injury_type: str
    last_updated: str


class SchemaEnforcer:
    """
    Logic funnel that validates all data before database insertion.
    Rejects invalid/corrupted data early.
    """
    
    SCHEMAS = {
        'player_stats': PlayerStatsSchema,
        'team_stats': TeamStatsSchema,
        'player_profile': PlayerProfileSchema,
        'schedule_game': ScheduleGameSchema,
        'injury_report': InjuryReportSchema
    }
    
    def validate(self, data: dict, entity_type: str) -> tuple[bool, dict]:
        """
        Validate data against schema.
        
        Args:
            data: Raw data dictionary
            entity_type: Type of entity ('player_stats', 'team_stats', etc.)
            
        Returns:
            (is_valid, validated_data or errors)
        """
        schema_class = self.SCHEMAS.get(entity_type)
        
        if not schema_class:
            # No schema defined, pass through with warning
            return True, data
        
        try:
            validated = schema_class(**data)
            return True, validated.dict()
        except Exception as e:
            # Validation failed
            errors = {
                'valid': False,
                'entity_type': entity_type,
                'error': str(e),
                'data': data
            }
            return False, errors
    
    def validate_batch(self, data_list: List[dict], entity_type: str) -> dict:
        """
        Validate a batch of data items.
        
        Returns:
            {
                'valid': [...],
                'invalid': [...],
                'stats': {...}
            }
        """
        valid_items = []
        invalid_items = []
        
        for item in data_list:
            is_valid, result = self.validate(item, entity_type)
            if is_valid:
                valid_items.append(result)
            else:
                invalid_items.append(result)
        
        return {
            'valid': valid_items,
            'invalid': invalid_items,
            'stats': {
                'total': len(data_list),
                'valid_count': len(valid_items),
                'invalid_count': len(invalid_items),
                'validation_rate': len(valid_items) / len(data_list) if data_list else 0
            }
        }
