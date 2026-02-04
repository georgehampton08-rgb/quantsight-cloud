"""
Matchup Orchestrator
====================
Team-Level Crucible Wrapper for the Matchup War Room.

Coordinates:
1. Roster validation for both teams
2. Batch archetype refresh for all players
3. Full-game Crucible simulation
4. Team-level offensive/defensive profile aggregation
"""
import asyncio
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


@dataclass
class PlayerProjection:
    """Individual player projection with matchup context"""
    player_id: str
    player_name: str
    team_id: str
    is_active: bool
    health_status: str  # green, yellow, red
    
    # Projections
    ev_points: float = 0.0
    ev_rebounds: float = 0.0
    ev_assists: float = 0.0
    
    # Matchup analysis
    archetype: str = ""
    matchup_advantage: str = "neutral"  # advantaged, countered, neutral
    friction_modifier: float = 0.0
    efficiency_grade: str = "C"
    
    # Usage context
    usage_boost: float = 0.0
    vacuum_beneficiary: bool = False


@dataclass
class TeamAnalysis:
    """Team-level analysis result"""
    team_id: str
    team_name: str
    offensive_archetype: str  # "Pace & Space", "Post Heavy", etc.
    defensive_profile: str    # "Rim Protection Heavy", "Perimeter Lock", etc.
    pace_rating: float = 100.0
    total_active_players: int = 0
    total_out_players: int = 0
    player_projections: List[PlayerProjection] = field(default_factory=list)


@dataclass 
class MatchupResult:
    """Complete matchup analysis result"""
    home_team: TeamAnalysis
    away_team: TeamAnalysis
    matchup_edge: str  # "home", "away", "neutral"
    edge_reason: str
    usage_vacuum_applied: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    game_date: str = ""


# Team archetype definitions
OFFENSIVE_ARCHETYPES = {
    'pace_and_space': {
        'name': 'Pace & Space',
        'criteria': {'playmaker_count': 2, 'sniper_count': 2},
        'description': 'High-tempo offense with floor spacing'
    },
    'post_heavy': {
        'name': 'Post Heavy',
        'criteria': {'glass_cleaner_count': 2, 'post_scorer_count': 1},
        'description': 'Inside-out offense through bigs'
    },
    'iso_dominant': {
        'name': 'ISO Dominant',
        'criteria': {'elite_scorer_count': 1, 'late_clock_iso_count': 1},
        'description': 'Relies on isolation plays from stars'
    },
    'balanced': {
        'name': 'Balanced Attack',
        'criteria': {},
        'description': 'No dominant offensive identity'
    }
}

DEFENSIVE_PROFILES = {
    'rim_protection': {
        'name': 'Rim Protection Heavy',
        'criteria': {'rim_protector_count': 2},
        'description': 'Strong interior defense, vulnerable on perimeter'
    },
    'perimeter_lock': {
        'name': 'Perimeter Lock',
        'criteria': {'ball_hawk_count': 2, 'two_way_count': 1},
        'description': 'Aggressive perimeter D, may give up paint points'
    },
    'switch_heavy': {
        'name': 'Switch Heavy',
        'criteria': {'two_way_count': 3},
        'description': 'Versatile defenders who switch everything'
    },
    'standard': {
        'name': 'Standard Defense',
        'criteria': {},
        'description': 'No dominant defensive identity'
    }
}


class MatchupOrchestrator:
    """
    Team-Level Matchup Analyzer.
    
    Orchestrates:
    1. Pre-flight roster validation for both teams
    2. Batch archetype classification refresh
    3. Crucible simulation for each player
    4. Team-level archetype aggregation
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
    
    async def run_matchup(
        self,
        home_team_id: str,
        away_team_id: str,
        game_date: Optional[date] = None
    ) -> MatchupResult:
        """
        Run complete team-to-team matchup analysis.
        
        Steps:
        1. Validate both rosters
        2. Refresh archetypes for all players
        3. Run projections with matchup friction
        4. Aggregate team-level profiles
        """
        start_time = time.time()
        
        if game_date is None:
            game_date = date.today()
        
        # Import services
        from services.roster_validator import get_roster_validator
        from services.archetype_engine import ArchetypeEngine
        from engines.usage_vacuum import get_usage_vacuum
        
        validator = get_roster_validator()
        archetype_engine = ArchetypeEngine(db_path=self.db_path)
        vacuum = get_usage_vacuum()
        
        # Step 1: Validate both rosters
        logger.info(f"🔍 Validating rosters for {home_team_id} vs {away_team_id}")
        home_validation, away_validation = validator.validate_both_teams(
            home_team_id, away_team_id
        )
        
        # Step 2: Collect all players for batch processing
        all_home_players = (
            home_validation.active_players + 
            home_validation.questionable_players
        )
        all_away_players = (
            away_validation.active_players + 
            away_validation.questionable_players
        )
        
        # Step 3: Get usage boosts if vacuum triggered
        vacuum_applied = []
        home_boosts = {}
        away_boosts = {}
        
        if home_validation.vacuum_triggered:
            home_boosts = validator.get_vacuum_redistribution(home_team_id)
            vacuum_applied.extend(home_validation.vacuum_targets)
            logger.info(f"   ⚡ Usage vacuum applied for {len(home_validation.vacuum_targets)} home players")
        
        if away_validation.vacuum_triggered:
            away_boosts = validator.get_vacuum_redistribution(away_team_id)
            vacuum_applied.extend(away_validation.vacuum_targets)
            logger.info(f"   ⚡ Usage vacuum applied for {len(away_validation.vacuum_targets)} away players")
        
        # Step 4: Batch archetype refresh and projections
        home_projections = await self._process_team_players(
            all_home_players, 
            home_team_id,
            home_validation.health_lights,
            home_boosts,
            away_team_id,  # opponent
            archetype_engine,
            game_date
        )
        
        away_projections = await self._process_team_players(
            all_away_players,
            away_team_id,
            away_validation.health_lights,
            away_boosts,
            home_team_id,  # opponent
            archetype_engine,
            game_date
        )
        
        # Step 5: Aggregate team archetypes
        home_offensive = self._aggregate_team_archetype(home_projections, 'offensive')
        home_defensive = self._aggregate_team_archetype(home_projections, 'defensive')
        away_offensive = self._aggregate_team_archetype(away_projections, 'offensive')
        away_defensive = self._aggregate_team_archetype(away_projections, 'defensive')
        
        # Step 6: Build team analysis objects
        home_analysis = TeamAnalysis(
            team_id=home_team_id,
            team_name=home_validation.team_name,
            offensive_archetype=home_offensive,
            defensive_profile=home_defensive,
            total_active_players=len(home_validation.active_players),
            total_out_players=len(home_validation.out_players),
            player_projections=home_projections
        )
        
        away_analysis = TeamAnalysis(
            team_id=away_team_id,
            team_name=away_validation.team_name,
            offensive_archetype=away_offensive,
            defensive_profile=away_defensive,
            total_active_players=len(away_validation.active_players),
            total_out_players=len(away_validation.out_players),
            player_projections=away_projections
        )
        
        # Step 7: Determine matchup edge
        edge, edge_reason = self._calculate_matchup_edge(home_analysis, away_analysis)
        
        execution_time = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Matchup analysis complete in {execution_time:.0f}ms")
        
        return MatchupResult(
            home_team=home_analysis,
            away_team=away_analysis,
            matchup_edge=edge,
            edge_reason=edge_reason,
            usage_vacuum_applied=vacuum_applied,
            execution_time_ms=execution_time,
            game_date=game_date.isoformat()
        )
    
    async def _process_team_players(
        self,
        players: List[Dict],
        team_id: str,
        health_lights: Dict[str, str],
        usage_boosts: Dict[str, float],
        opponent_id: str,
        archetype_engine,
        game_date: date
    ) -> List[PlayerProjection]:
        """Process all players for a team, generating projections."""
        projections = []
        
        for player in players:
            player_id = str(player['player_id'])
            
            # Get/refresh archetype
            archetype_data = archetype_engine.classify_player(player_id)
            archetype = archetype_data.get('primary', 'unknown') if archetype_data else 'unknown'
            
            # Get base projection (simplified - in production, call Crucible)
            base_projection = await self._get_player_projection(
                player_id, opponent_id, game_date
            )
            
            # Apply usage boost if applicable
            usage_boost = usage_boosts.get(player_id, 0.0)
            
            # Calculate matchup advantage
            matchup_advantage = self._calculate_matchup_advantage(
                archetype, opponent_id, archetype_engine
            )
            
            # Calculate friction modifier
            friction = archetype_data.get('friction', {}) if archetype_data else {}
            friction_mod = sum(friction.values()) / len(friction) if friction else 0.0
            
            # Apply boosts to projection
            adjusted_pts = base_projection['points'] * (1 + usage_boost + friction_mod * 0.1)
            adjusted_reb = base_projection['rebounds'] * (1 + friction_mod * 0.05)
            adjusted_ast = base_projection['assists'] * (1 + usage_boost * 0.5)
            
            # Calculate efficiency grade
            grade = self._calculate_efficiency_grade(
                adjusted_pts, matchup_advantage, friction_mod
            )
            
            projections.append(PlayerProjection(
                player_id=player_id,
                player_name=player.get('name', 'Unknown'),
                team_id=team_id,
                is_active=health_lights.get(player_id) != 'red',
                health_status=health_lights.get(player_id, 'green'),
                ev_points=round(adjusted_pts, 1),
                ev_rebounds=round(adjusted_reb, 1),
                ev_assists=round(adjusted_ast, 1),
                archetype=archetype,
                matchup_advantage=matchup_advantage,
                friction_modifier=round(friction_mod, 3),
                efficiency_grade=grade,
                usage_boost=round(usage_boost, 3),
                vacuum_beneficiary=usage_boost > 0
            ))
        
        # Sort by EV points descending
        projections.sort(key=lambda x: x.ev_points, reverse=True)
        
        return projections
    
    async def _get_player_projection(
        self, 
        player_id: str, 
        opponent_id: str,
        game_date: date
    ) -> Dict[str, float]:
        """Get base projection for a player (simplified version)."""
        try:
            from aegis.orchestrator import AegisOrchestrator, OrchestratorConfig
            
            config = OrchestratorConfig(
                n_simulations=10_000,  # Fewer sims for batch speed
                cache_enabled=True
            )
            orchestrator = AegisOrchestrator(config)
            
            result = await orchestrator.run_simulation(
                player_id=player_id,
                opponent_id=opponent_id,
                game_date=game_date
            )
            
            return {
                'points': result.expected_value.get('points', 15.0),
                'rebounds': result.expected_value.get('rebounds', 5.0),
                'assists': result.expected_value.get('assists', 3.0)
            }
        except Exception as e:
            logger.warning(f"Projection fallback for {player_id}: {e}")
            # Fallback to database averages
            return self._get_db_averages(player_id)
    
    def _get_db_averages(self, player_id: str) -> Dict[str, float]:
        """Get season averages from database as fallback."""
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT points_avg, rebounds_avg, assists_avg
                FROM player_stats
                WHERE player_id = ?
                ORDER BY season DESC
                LIMIT 1
            """, (player_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'points': row['points_avg'] or 10.0,
                    'rebounds': row['rebounds_avg'] or 4.0,
                    'assists': row['assists_avg'] or 2.0
                }
        except Exception as e:
            logger.error(f"DB fallback error: {e}")
        
        return {'points': 10.0, 'rebounds': 4.0, 'assists': 2.0}
    
    def _calculate_matchup_advantage(
        self, 
        archetype: str, 
        opponent_id: str,
        archetype_engine
    ) -> str:
        """Determine if player archetype has advantage vs opponent."""
        # Simplified matchup advantage logic
        # In production, would analyze opponent's defensive personnel
        
        advantaged_matchups = {
            'elite_scorer': ['rim_protector'],  # Can shoot over
            'sniper': ['rim_protector', 'glass_cleaner'],  # Space the floor
            'slasher': ['sniper'],  # Attack closeouts
            'playmaker': ['rim_protector'],  # Kick out for 3s
        }
        
        countered_matchups = {
            'slasher': ['rim_protector'],
            'post_scorer': ['rim_protector'],
            'playmaker': ['ball_hawk'],
        }
        
        # For now, return neutral (would need opponent roster analysis)
        if archetype in advantaged_matchups:
            return 'advantaged'
        elif archetype in countered_matchups:
            return 'countered'
        
        return 'neutral'
    
    def _calculate_efficiency_grade(
        self,
        ev_points: float,
        matchup: str,
        friction: float
    ) -> str:
        """Calculate A-F efficiency grade."""
        score = ev_points
        
        # Adjust for matchup
        if matchup == 'advantaged':
            score += 3
        elif matchup == 'countered':
            score -= 3
        
        # Adjust for friction
        score += friction * 10
        
        if score >= 25:
            return 'A'
        elif score >= 20:
            return 'B+'
        elif score >= 16:
            return 'B'
        elif score >= 12:
            return 'C+'
        elif score >= 8:
            return 'C'
        elif score >= 5:
            return 'D'
        else:
            return 'F'
    
    def _aggregate_team_archetype(
        self, 
        projections: List[PlayerProjection],
        profile_type: str  # 'offensive' or 'defensive'
    ) -> str:
        """Aggregate player archetypes into team-level profile."""
        archetype_counts = {}
        
        for proj in projections:
            if proj.is_active:
                arch = proj.archetype
                archetype_counts[arch] = archetype_counts.get(arch, 0) + 1
        
        # Check offensive archetypes
        if profile_type == 'offensive':
            for key, profile in OFFENSIVE_ARCHETYPES.items():
                if key == 'balanced':
                    continue
                criteria = profile['criteria']
                matches = all(
                    archetype_counts.get(arch.replace('_count', ''), 0) >= count
                    for arch, count in criteria.items()
                )
                if matches:
                    return profile['name']
            return OFFENSIVE_ARCHETYPES['balanced']['name']
        
        # Check defensive profiles
        else:
            for key, profile in DEFENSIVE_PROFILES.items():
                if key == 'standard':
                    continue
                criteria = profile['criteria']
                matches = all(
                    archetype_counts.get(arch.replace('_count', ''), 0) >= count
                    for arch, count in criteria.items()
                )
                if matches:
                    return profile['name']
            return DEFENSIVE_PROFILES['standard']['name']
    
    def _calculate_matchup_edge(
        self, 
        home: TeamAnalysis, 
        away: TeamAnalysis
    ) -> Tuple[str, str]:
        """Determine which team has the matchup edge."""
        home_score = 0
        away_score = 0
        reasons = []
        
        # Compare player counts
        if home.total_active_players > away.total_active_players:
            home_score += 1
            reasons.append(f"{home.team_name} has more active players")
        elif away.total_active_players > home.total_active_players:
            away_score += 1
            reasons.append(f"{away.team_name} has more active players")
        
        # Compare injuries
        if home.total_out_players < away.total_out_players:
            home_score += 1
            reasons.append(f"{home.team_name} is healthier")
        elif away.total_out_players < home.total_out_players:
            away_score += 1
            reasons.append(f"{away.team_name} is healthier")
        
        # Compare top player EV
        home_top = home.player_projections[0].ev_points if home.player_projections else 0
        away_top = away.player_projections[0].ev_points if away.player_projections else 0
        
        if home_top > away_top + 3:
            home_score += 1
            reasons.append(f"{home.team_name} has higher star EV")
        elif away_top > home_top + 3:
            away_score += 1
            reasons.append(f"{away.team_name} has higher star EV")
        
        if home_score > away_score:
            return "home", "; ".join(reasons) if reasons else "Home team favored"
        elif away_score > home_score:
            return "away", "; ".join(reasons) if reasons else "Away team favored"
        else:
            return "neutral", "Even matchup"


# Singleton
_orchestrator = None

def get_matchup_orchestrator() -> MatchupOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MatchupOrchestrator()
    return _orchestrator


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    
    async def test():
        orchestrator = get_matchup_orchestrator()
        
        print("="*60)
        print("MATCHUP ORCHESTRATOR TEST")
        print("="*60)
        
        # Test CLE vs BOS
        print("\n Running: Cleveland Cavaliers vs Boston Celtics")
        result = await orchestrator.run_matchup("1610612739", "1610612738")
        
        print(f"\n📊 MATCHUP RESULT")
        print(f"   Execution Time: {result.execution_time_ms:.0f}ms")
        print(f"   Edge: {result.matchup_edge} - {result.edge_reason}")
        
        print(f"\n🏠 HOME: {result.home_team.team_name}")
        print(f"   Offensive: {result.home_team.offensive_archetype}")
        print(f"   Defensive: {result.home_team.defensive_profile}")
        print(f"   Active: {result.home_team.total_active_players}, Out: {result.home_team.total_out_players}")
        print(f"\n   Top 5 Projections:")
        for p in result.home_team.player_projections[:5]:
            status = "🟢" if p.health_status == "green" else "🟡" if p.health_status == "yellow" else "🔴"
            print(f"      {status} {p.player_name}: {p.ev_points}pts ({p.archetype}) - Grade: {p.efficiency_grade}")
        
        print(f"\n🚗 AWAY: {result.away_team.team_name}")
        print(f"   Offensive: {result.away_team.offensive_archetype}")
        print(f"   Defensive: {result.away_team.defensive_profile}")
        print(f"\n   Top 5 Projections:")
        for p in result.away_team.player_projections[:5]:
            status = "🟢" if p.health_status == "green" else "🟡" if p.health_status == "yellow" else "🔴"
            print(f"      {status} {p.player_name}: {p.ev_points}pts ({p.archetype}) - Grade: {p.efficiency_grade}")
    
    asyncio.run(test())
