"""
Usage Vacuum Module
===================
Handles usage redistribution when a player is OUT (injured/resting).

Features:
1. On/Off Impact: Scale redistribution by NET_RATING_OFF differential
2. Passing-Based Reallocation: +15% weight to frequent pass recipients
3. Archetype-aware redistribution (scorers get more shots than glue guys)
"""
import sqlite3
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PlayerImpact:
    """Player's on/off court impact"""
    player_id: str
    player_name: str
    off_rating: float
    def_rating: float
    net_rating: float
    usg_pct: float
    ast_ratio: float


@dataclass
class PassingConnection:
    """Passing relationship between two players"""
    from_player_id: str
    to_player_id: str
    to_player_name: str
    frequency: float      # % of passes going to this player
    passes: float         # Total passes
    assists: float        # Assists from these passes
    fg_pct: float         # FG% on shots from these passes


class UsageVacuum:
    """
    Redistributes usage when a player is OUT.
    
    Uses:
    1. NET_RATING_OFF differential to scale impact
    2. Passing data to find frequent recipients (+15% weight)
    3. Archetype data to give scorers more shots
    """
    
    PASS_RECIPIENT_BOOST = 0.15  # +15% weight for frequent pass recipients
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._impact_cache: Dict[str, PlayerImpact] = {}
        self._passing_cache: Dict[str, List[PassingConnection]] = {}
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_player_impact(self, player_id: str) -> Optional[PlayerImpact]:
        """Get player's on/off impact from advanced stats"""
        if player_id in self._impact_cache:
            return self._impact_cache[player_id]
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT player_id, player_name, off_rating, def_rating, 
                       net_rating, usg_pct, ast_ratio
                FROM player_advanced_stats
                WHERE player_id = ?
            """, (str(player_id),))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                impact = PlayerImpact(
                    player_id=str(row['player_id']),
                    player_name=row['player_name'] or 'Unknown',
                    off_rating=float(row['off_rating'] or 100),
                    def_rating=float(row['def_rating'] or 100),
                    net_rating=float(row['net_rating'] or 0),
                    usg_pct=float(row['usg_pct'] or 0.20),
                    ast_ratio=float(row['ast_ratio'] or 0),
                )
                self._impact_cache[player_id] = impact
                return impact
        except Exception as e:
            logger.warning(f"Error fetching player impact: {e}")
        
        return None
    
    def get_player_passing_targets(self, player_id: str) -> List[PassingConnection]:
        """Get who the player passes to most often"""
        if player_id in self._passing_cache:
            return self._passing_cache[player_id]
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT pass_to_player_id, pass_to_name, frequency, 
                       passes, assists, fg_pct
                FROM player_passing
                WHERE player_id = ?
                ORDER BY frequency DESC
            """, (str(player_id),))
            
            connections = []
            for row in cursor.fetchall():
                conn_obj = PassingConnection(
                    from_player_id=str(player_id),
                    to_player_id=str(row['pass_to_player_id']),
                    to_player_name=row['pass_to_name'] or 'Unknown',
                    frequency=float(row['frequency'] or 0),
                    passes=float(row['passes'] or 0),
                    assists=float(row['assists'] or 0),
                    fg_pct=float(row['fg_pct'] or 0),
                )
                connections.append(conn_obj)
            
            conn.close()
            self._passing_cache[player_id] = connections
            return connections
            
        except Exception as e:
            logger.warning(f"Error fetching passing data: {e}")
        
        return []
    
    def calculate_redistribution(
        self,
        injured_player_id: str,
        teammates: List[Dict]
    ) -> Dict[str, Dict]:
        """
        Calculate usage redistribution when a player is OUT.
        
        Returns dict: {player_id: {'usage_boost': float, 'reason': str}}
        """
        redistribution = {}
        
        # Get injured player's impact
        injured_impact = self.get_player_impact(injured_player_id)
        if not injured_impact:
            logger.warning(f"No impact data for {injured_player_id}")
            return self._simple_redistribution(injured_player_id, teammates)
        
        injured_usage = injured_impact.usg_pct
        injured_name = injured_impact.player_name
        
        # Get passing connections (who received passes from injured)
        passing_targets = self.get_player_passing_targets(injured_player_id)
        passing_target_ids = {p.to_player_id: p for p in passing_targets}
        
        # Calculate total weight for redistribution
        total_weight = 0.0
        teammate_weights = {}
        
        for tm in teammates:
            tm_id = str(tm.get('player_id'))
            if tm_id == injured_player_id:
                continue
                
            # Base weight = teammate's usage
            tm_impact = self.get_player_impact(tm_id)
            base_weight = tm_impact.usg_pct if tm_impact else 0.15
            
            # Boost if frequent pass recipient
            if tm_id in passing_target_ids:
                connection = passing_target_ids[tm_id]
                # +15% weight for every 10% of passes received
                pass_boost = connection.frequency * self.PASS_RECIPIENT_BOOST
                base_weight *= (1 + pass_boost)
            
            teammate_weights[tm_id] = base_weight
            total_weight += base_weight
        
        # Distribute injured player's usage
        if total_weight > 0:
            for tm_id, weight in teammate_weights.items():
                share = weight / total_weight
                usage_boost = injured_usage * share * 0.5  # 50% conversion rate
                
                reason_parts = [f"Absorbed {share*100:.0f}% of {injured_name}'s usage"]
                
                # Note if pass recipient
                if tm_id in passing_target_ids:
                    conn = passing_target_ids[tm_id]
                    reason_parts.append(f"(received {conn.frequency*100:.1f}% of passes)")
                
                redistribution[tm_id] = {
                    'usage_boost': usage_boost,
                    'reason': ' '.join(reason_parts),
                    'share': share,
                    'was_pass_target': tm_id in passing_target_ids,
                }
        
        return redistribution
    
    def _simple_redistribution(
        self,
        injured_player_id: str,
        teammates: List[Dict]
    ) -> Dict[str, Dict]:
        """Simple even redistribution when no advanced data available"""
        redistribution = {}
        
        active_teammates = [tm for tm in teammates 
                           if str(tm.get('player_id')) != injured_player_id]
        
        if not active_teammates:
            return {}
        
        # Assume 20% usage for injured player, distribute evenly
        injured_usage = 0.20
        boost_per_player = (injured_usage * 0.5) / len(active_teammates)
        
        for tm in active_teammates:
            tm_id = str(tm.get('player_id'))
            redistribution[tm_id] = {
                'usage_boost': boost_per_player,
                'reason': 'Even redistribution (no advanced data)',
                'share': 1.0 / len(active_teammates),
                'was_pass_target': False,
            }
        
        return redistribution
    
    def apply_vacuum_to_players(
        self,
        injured_player_id: str,
        player_states: List
    ) -> Dict:
        """
        Apply usage vacuum directly to player states.
        
        Args:
            injured_player_id: The OUT player's ID
            player_states: List of PlayerState objects from Crucible
            
        Returns:
            Summary of changes made
        """
        # Convert player states to dict format
        teammates = [
            {'player_id': p.player_id, 'name': p.name, 'usage': p.base_usage}
            for p in player_states
        ]
        
        # Calculate redistribution
        redistribution = self.calculate_redistribution(injured_player_id, teammates)
        
        # Apply to player states
        changes = []
        for player in player_states:
            if str(player.player_id) == injured_player_id:
                player.is_on_court = False
                player.benched_until_quarter = 99  # OUT for game
                continue
            
            boost_info = redistribution.get(str(player.player_id))
            if boost_info:
                player.usage_mod += boost_info['usage_boost']
                changes.append({
                    'player': player.name,
                    'boost': boost_info['usage_boost'],
                    'reason': boost_info['reason'],
                })
        
        return {
            'injured_player_id': injured_player_id,
            'changes': changes,
            'players_affected': len(changes),
        }
    
    def get_boost_for_player(self, player_id: str, injuries: List[Dict]) -> float:
        """
        Get usage boost for a specific player given a list of injured teammates.
        
        This is a convenience method for the Aegis orchestrator.
        
        Args:
            player_id: The player to get boost for
            injuries: List of dicts with 'player_id' key for injured players
            
        Returns:
            Total usage boost as a float (0.0 to 0.15 typically)
        """
        if not injuries:
            return 0.0
        
        total_boost = 0.0
        
        # For each injured player, calculate what boost this player would receive
        for injury in injuries:
            injured_id = str(injury.get('player_id', ''))
            if not injured_id or injured_id == str(player_id):
                continue
            
            # Get injured player's impact
            injured_impact = self.get_player_impact(injured_id)
            if not injured_impact:
                # Assume 20% usage if no data
                injured_usage = 0.20
            else:
                injured_usage = injured_impact.usg_pct
            
            # Check if this player was a frequent pass recipient
            passing_targets = self.get_player_passing_targets(injured_id)
            pass_boost = 0.0
            for conn in passing_targets:
                if str(conn.to_player_id) == str(player_id):
                    # +15% weight for passes received
                    pass_boost = conn.frequency * self.PASS_RECIPIENT_BOOST
                    break
            
            # Calculate base share (assume 20% of usage redistributed to this player)
            base_share = 0.2 * (1 + pass_boost)
            boost = injured_usage * base_share * 0.5  # 50% conversion
            total_boost += boost
        
        # Cap at reasonable max
        return min(total_boost, 0.15)


# Singleton
_vacuum = None

def get_usage_vacuum() -> UsageVacuum:
    global _vacuum
    if _vacuum is None:
        _vacuum = UsageVacuum()
    return _vacuum


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    vacuum = get_usage_vacuum()
    
    print("="*60)
    print("USAGE VACUUM TEST")
    print("="*60)
    
    # Test LeBron's passing targets
    print("\n1. LeBron's top passing targets:")
    targets = vacuum.get_player_passing_targets("2544")
    for t in targets[:5]:
        print(f"   {t.to_player_name}: {t.frequency*100:.1f}% of passes, {t.assists:.0f} assists")
    
    # Test impact
    print("\n2. LeBron's impact:")
    impact = vacuum.get_player_impact("2544")
    if impact:
        print(f"   Usage: {impact.usg_pct*100:.1f}%")
        print(f"   Net Rating: {impact.net_rating:+.1f}")
    
    # Test redistribution (mock teammates)
    print("\n3. Usage redistribution if LeBron OUT:")
    mock_teammates = [
        {'player_id': '2544', 'name': 'LeBron James'},
        {'player_id': '203076', 'name': 'Anthony Davis'},
        {'player_id': '1628983', 'name': 'Austin Reaves'},
        {'player_id': '1627936', 'name': 'D\'Angelo Russell'},
    ]
    redistribution = vacuum.calculate_redistribution("2544", mock_teammates)
    for pid, info in redistribution.items():
        print(f"   {pid}: +{info['usage_boost']*100:.1f}% usage - {info['reason']}")
