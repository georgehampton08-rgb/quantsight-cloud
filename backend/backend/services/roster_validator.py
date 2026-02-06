"""
Active Roster Validator
=======================
Pre-Flight Roster Check for Matchup War Room.

Features:
1. Cross-references roster against injuries_current table
2. Triggers UsageVacuum when high-usage players (>25%) are OUT
3. Provides "Health Light" indicators for UI (green/yellow/red)
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RosterValidationResult:
    """Result of roster validation check"""
    team_id: str
    team_name: str
    active_players: List[Dict] = field(default_factory=list)
    out_players: List[Dict] = field(default_factory=list)
    questionable_players: List[Dict] = field(default_factory=list)
    health_lights: Dict[str, str] = field(default_factory=dict)  # player_id -> green/yellow/red
    vacuum_triggered: bool = False
    vacuum_targets: List[str] = field(default_factory=list)  # High-usage OUT player IDs
    validation_time: str = ""


class ActiveRosterValidator:
    """
    Pre-Flight Roster Check: Filters active roster and triggers 
    usage redistribution when key players are OUT.
    
    Usage Vacuum Trigger: If a player with Usage > 25% is flagged as OUT,
    the engine automatically redistributes their shots to active players.
    """
    
    USAGE_THRESHOLD = 0.25  # 25% usage triggers vacuum
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def validate_team_roster(self, team_id: str) -> RosterValidationResult:
        """
        Validate a team's roster against injury reports.
        
        Returns:
            RosterValidationResult with categorized players
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # NBA team ID mapping for abbreviations
        nba_team_map = {
            'ATL': '1610612737', 'BOS': '1610612738', 'BKN': '1610612751', 'CHA': '1610612766',
            'CHI': '1610612741', 'CLE': '1610612739', 'DAL': '1610612742', 'DEN': '1610612743',
            'DET': '1610612765', 'GSW': '1610612744', 'HOU': '1610612745', 'IND': '1610612754',
            'LAC': '1610612746', 'LAL': '1610612747', 'MEM': '1610612763', 'MIA': '1610612748',
            'MIL': '1610612749', 'MIN': '1610612750', 'NOP': '1610612740', 'NYK': '1610612752',
            'OKC': '1610612760', 'ORL': '1610612753', 'PHI': '1610612755', 'PHX': '1610612756',
            'POR': '1610612757', 'SAC': '1610612758', 'SAS': '1610612759', 'TOR': '1610612761',
            'UTA': '1610612762', 'WAS': '1610612764'
        }
        
        # Build list of possible team IDs
        target_team_ids = [team_id]
        if team_id in nba_team_map:
            target_team_ids.append(nba_team_map[team_id])
        # Also check reverse mapping
        for abbr, tid in nba_team_map.items():
            if tid == team_id:
                target_team_ids.append(abbr)
                break
        
        # Get team info
        cursor.execute("""
            SELECT team_id, name, abbreviation 
            FROM teams 
            WHERE team_id = ? OR abbreviation = ?
        """, (team_id, team_id))
        team_row = cursor.fetchone()
        team_name = team_row['name'] if team_row else team_id
        team_abbr = team_row['abbreviation'] if team_row else team_id
        
        # Get all players on the roster
        placeholders = ','.join(['?'] * len(target_team_ids))
        cursor.execute(f"""
            SELECT p.player_id, p.name, p.position, p.jersey_number
            FROM players p
            WHERE p.team_id IN ({placeholders})
            ORDER BY p.name
        """, tuple(target_team_ids))
        roster = [dict(row) for row in cursor.fetchall()]
        
        # Get injury status for each player
        active = []
        out = []
        questionable = []
        health_lights = {}
        vacuum_targets = []
        
        for player in roster:
            player_id = str(player['player_id'])
            
            # Check injury status
            cursor.execute("""
                SELECT status, injury_desc, return_date
                FROM injuries_current
                WHERE player_id = ?
            """, (player_id,))
            injury_row = cursor.fetchone()
            
            if injury_row:
                status = injury_row['status'].upper()
                player['injury_status'] = status
                player['injury_desc'] = injury_row['injury_desc'] or ''
                player['return_date'] = injury_row['return_date']
                
                if status == 'OUT':
                    out.append(player)
                    health_lights[player_id] = 'red'
                    
                    # Usage vacuum trigger disabled (no usage data in DB)
                    # TODO: Re-enable when usg_pct data is available
                    pass
                        
                elif status == 'DOUBTFUL':
                    out.append(player)  # Treat doubtful as out for projections
                    health_lights[player_id] = 'red'
                    
                elif status in ('QUESTIONABLE', 'PROBABLE'):
                    questionable.append(player)
                    health_lights[player_id] = 'yellow'
                else:
                    active.append(player)
                    health_lights[player_id] = 'green'
            else:
                # No injury record = healthy
                player['injury_status'] = 'AVAILABLE'
                player['injury_desc'] = ''
                active.append(player)
                health_lights[player_id] = 'green'
        
        conn.close()
        
        result = RosterValidationResult(
            team_id=team_id,
            team_name=team_name,
            active_players=active,
            out_players=out,
            questionable_players=questionable,
            health_lights=health_lights,
            vacuum_triggered=len(vacuum_targets) > 0,
            vacuum_targets=vacuum_targets,
            validation_time=datetime.now().isoformat()
        )
        
        logger.info(f"✅ Roster validated: {team_name} - {len(active)} active, {len(out)} out, {len(questionable)} GTD")
        
        return result
    
    def get_health_lights(self, team_id: str) -> Dict[str, str]:
        """
        Get health light indicators for all players on a team.
        
        Returns:
            Dict mapping player_id -> "green" | "yellow" | "red"
        """
        result = self.validate_team_roster(team_id)
        return result.health_lights
    
    def get_vacuum_redistribution(self, team_id: str) -> Dict[str, float]:
        """
        Calculate usage redistribution for remaining players when key players are OUT.
        
        Returns:
            Dict mapping player_id -> usage_boost (0.0 to 0.15 typically)
        """
        from engines.usage_vacuum import get_usage_vacuum
        
        result = self.validate_team_roster(team_id)
        
        if not result.vacuum_triggered:
            return {}
        
        vacuum = get_usage_vacuum()
        total_boosts = {}
        
        # Get active teammate info for redistribution
        teammates = [
            {'player_id': p['player_id'], 'name': p['name'], 'usg_pct': 0.20}  # Default usage
            for p in result.active_players
        ]
        
        # Calculate redistribution for each OUT high-usage player
        for injured_id in result.vacuum_targets:
            redistribution = vacuum.calculate_redistribution(injured_id, teammates)
            for player_id, info in redistribution.items():
                if player_id not in total_boosts:
                    total_boosts[player_id] = 0.0
                total_boosts[player_id] += info['usage_boost']
        
        return total_boosts
    
    def validate_both_teams(
        self, 
        home_team_id: str, 
        away_team_id: str
    ) -> Tuple[RosterValidationResult, RosterValidationResult]:
        """
        Validate rosters for both teams in a matchup.
        
        Returns:
            Tuple of (home_result, away_result)
        """
        home_result = self.validate_team_roster(home_team_id)
        away_result = self.validate_team_roster(away_team_id)
        
        return home_result, away_result


# Singleton
_validator = None

def get_roster_validator() -> ActiveRosterValidator:
    global _validator
    if _validator is None:
        _validator = ActiveRosterValidator()
    return _validator


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    validator = get_roster_validator()
    
    print("="*60)
    print("ROSTER VALIDATOR TEST")
    print("="*60)
    
    # Test Cleveland Cavaliers
    print("\n1. Validating Cleveland Cavaliers roster...")
    result = validator.validate_team_roster("1610612739")
    
    print(f"\n   Team: {result.team_name}")
    print(f"   Active Players: {len(result.active_players)}")
    for p in result.active_players[:5]:
        print(f"      🟢 {p['name']} ({p.get('position', 'N/A')})")
    
    print(f"\n   Out Players: {len(result.out_players)}")
    for p in result.out_players:
        print(f"      🔴 {p['name']}: {p.get('injury_desc', 'N/A')}")
    
    print(f"\n   Questionable: {len(result.questionable_players)}")
    for p in result.questionable_players:
        print(f"      🟡 {p['name']}: {p.get('injury_desc', 'N/A')}")
    
    print(f"\n   Vacuum Triggered: {result.vacuum_triggered}")
    if result.vacuum_targets:
        print(f"   Vacuum Targets: {result.vacuum_targets}")
    
    # Test usage redistribution
    print("\n2. Testing usage redistribution...")
    boosts = validator.get_vacuum_redistribution("1610612739")
    if boosts:
        print("   Usage Boosts:")
        for pid, boost in sorted(boosts.items(), key=lambda x: -x[1])[:5]:
            print(f"      {pid}: +{boost*100:.1f}%")
    else:
        print("   No vacuum redistribution needed")
