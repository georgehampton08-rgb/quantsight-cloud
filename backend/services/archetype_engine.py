"""
Archetype Engine v2.0
Classifies player styles using TRACKING DATA and generates Friction Multiplier Matrix.
Integrated with TrackingDataFetcher for real DFG%, Hustle, and Shot Clock metrics.
"""
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Import tracking fetcher
try:
    from .tracking_data_fetcher import get_tracking_fetcher
    HAS_TRACKING = True
except ImportError:
    HAS_TRACKING = False
    logger.warning("TrackingDataFetcher not available")


# ============================================================================
# ARCHETYPE DEFINITIONS v2.0 - Now with Tracking Criteria
# ============================================================================
ARCHETYPES = {
    'elite_scorer': {
        'description': 'High-volume scorer with efficiency',
        'criteria': {'ppg': 22, 'fg_pct': 0.45, 'usg_pct': 0.28},
    },
    'playmaker': {
        'description': 'Primary ball handler and distributor',
        'criteria': {'apg': 6, 'ast_to_ratio': 2.5, 'ast_ratio': 20},
    },
    'glass_cleaner': {
        'description': 'Dominant rebounder',
        'criteria': {'rpg': 10, 'reb_pct': 0.15},
    },
    'sniper': {
        'description': '3-point specialist with efficient shot selection',
        'criteria': {
            'fg3m': 2.5,
            'fg3_pct': 0.38,
            # TRACKING CRITERIA
            'fga_frequency': 0.30,        # >30% of shots from 3PT
            'contested_shots_3pt': -2.0,  # <2.0 contested 3s (negative = max threshold)
        },
    },
    'rim_protector': {
        'description': 'Shot blocker and interior defender',
        'criteria': {
            'bpg': 1.5,
            # TRACKING CRITERIA
            'd_fg_pct_rim': -0.50,  # <50% DFG% at rim (negative = max threshold)
        },
    },
    'ball_hawk': {
        'description': 'Active hands, disruptive defender',
        'criteria': {
            'spg': 1.2,
            # TRACKING CRITERIA
            'deflections': 1.5,      # >1.5 deflections per game
            'loose_balls': 0.8,      # >0.8 loose balls recovered
        },
    },
    'two_way': {
        'description': 'Elite on both ends',
        'criteria': {
            'ppg': 15, 
            'stocks': 2.5,  # STL + BLK
            # TRACKING CRITERIA
            'pct_plusminus': -0.03,  # DFG impact <-3% (negative = max)
        },
    },
    'stretch_big': {
        'description': 'Big man with 3-point range',
        'criteria': {
            'height_inches': 80,  # 6'8"+
            'fg3m': 1.5,
            'fga_frequency': 0.20,  # >20% from 3
        },
    },
    'slasher': {
        'description': 'Attacks the rim aggressively',
        'criteria': {
            'drive_pct': 0.4, 
            'fta': 5,
            # TRACKING CRITERIA
            'contested_shots_2pt': 4.0,  # High contested 2PT attempts
        },
    },
    'floor_general': {
        'description': 'Controls tempo and minimizes turnovers',
        'criteria': {
            'apg': 5, 
            'ast_to_ratio': 3.0,
            'screen_assists': 1.5,  # TRACKING: sets good screens
        },
    },
    'hustle_player': {
        'description': 'High-energy player, does the dirty work',
        'criteria': {
            'deflections': 1.2,
            'contested_shots': 4.0,
            'loose_balls': 1.0,
            'charges_drawn': 0.15,
        },
    },
    'late_clock_iso': {
        'description': 'Goes ISO heavy in late shot clock',
        'criteria': {
            'late_clock_freq': 0.15,  # >15% of shots in 0-4s range
            'ppg': 18,
        },
    },
}

# ============================================================================
# FRICTION MATRIX - Player-Specific DFG% Integration
# ============================================================================
FRICTION_MATRIX = {
    'glass_cleaner': {
        'vs_perimeter_scorer': {'reb': 1.05, 'reason': 'More long rebounds from perimeter shots'},
        'vs_post_scorer': {'reb': 0.92, 'reason': 'Contested boards near rim'},
        'vs_sniper': {'reb': 1.08, 'reason': 'Long rebounds from 3-point misses'},
    },
    'rim_protector': {
        'vs_slasher': {'opp_fg_rim': 0.88, 'blk': 1.15, 'reason': 'Presence deters drives'},
        'vs_sniper': {'blk': 0.85, 'reason': 'Fewer block opportunities'},
        'vs_post_scorer': {'blk': 1.10, 'reason': 'More shot-blocking chances'},
    },
    'ball_hawk': {
        'vs_playmaker': {'stl': 1.12, 'opp_ast': 0.90, 'reason': 'Disrupts passing lanes'},
        'vs_floor_general': {'stl': 1.08, 'reason': 'More ball-handling to attack'},
    },
    'sniper': {
        'vs_rim_protector': {'fg3a': 1.10, 'reason': 'Pulls defender out, more open 3s'},
        'vs_ball_hawk': {'fg3_pct': 0.95, 'reason': 'Closeout pressure'},
        'vs_hustle_player': {'fg3_pct': 0.93, 'reason': 'Heavy contest on catch-and-shoot'},
    },
    'playmaker': {
        'vs_ball_hawk': {'ast': 0.90, 'tov': 1.15, 'reason': 'Pressure causes turnovers'},
        'vs_rim_protector': {'ast': 1.05, 'reason': 'Kickouts from collapsed defense'},
    },
    'slasher': {
        'vs_rim_protector': {'pts_paint': 0.85, 'fta': 1.10, 'reason': 'Contested at rim but draws fouls'},
        'vs_sniper': {'pts': 1.05, 'reason': 'Space to attack closeouts'},
    },
    'elite_scorer': {
        'vs_two_way': {'pts': 0.92, 'fg_pct': 0.95, 'reason': 'Elite defender limits efficiency'},
        'vs_glass_cleaner': {'pts': 1.02, 'reason': 'Mismatch on perimeter'},
    },
    'late_clock_iso': {
        'vs_ball_hawk': {'pts': 0.88, 'tov': 1.20, 'reason': 'ISO vulnerable to active hands'},
        'vs_rim_protector': {'pts': 0.90, 'reason': 'Rim protection limits finishing'},
    },
}


class ArchetypeEngine:
    """
    v2.0: Classifies player archetypes using TRACKING DATA.
    Integrates with TrackingDataFetcher for real DFG%, Hustle, and Shot Clock metrics.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._ensure_table()
        
        # Get tracking fetcher
        self.tracking = get_tracking_fetcher() if HAS_TRACKING else None
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn
    
    def _ensure_table(self):
        """Create archetype table if not exists"""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_archetypes (
                player_id TEXT PRIMARY KEY,
                player_name TEXT,
                primary_archetype TEXT,
                secondary_archetype TEXT,
                archetype_scores TEXT,
                friction_matrix TEXT,
                tracking_data_used INTEGER DEFAULT 0,
                updated_at TIMESTAMP
            )
        """)
        
        # Add tracking_data_used column if it doesn't exist (for existing tables)
        try:
            conn.execute("""
                ALTER TABLE player_archetypes 
                ADD COLUMN tracking_data_used INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            # Column already exists, ignore
            pass
        
        conn.commit()
        conn.close()
    
    def classify_player(self, player_id: str) -> Dict:
        """
        Analyze player stats + TRACKING DATA to assign archetypes.
        Returns primary and secondary archetype with confidence scores.
        """
        stats = self._get_player_stats(player_id)
        if not stats:
            return {'primary': None, 'secondary': None, 'scores': {}}
        
        # Merge tracking data if available
        tracking_used = False
        if self.tracking:
            tracking_profile = self.tracking.get_player_full_profile(player_id)
            if tracking_profile:
                self._merge_tracking_data(stats, tracking_profile)
                tracking_used = True
        
        scores = {}
        
        # Calculate score for each archetype
        for archetype, config in ARCHETYPES.items():
            score = self._calculate_archetype_score(stats, config['criteria'])
            scores[archetype] = round(score, 3)
        
        # Sort by score
        sorted_archetypes = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        primary = sorted_archetypes[0][0] if sorted_archetypes[0][1] > 0.5 else None
        secondary = sorted_archetypes[1][0] if len(sorted_archetypes) > 1 and sorted_archetypes[1][1] > 0.4 else None
        
        # Generate friction matrix for this player
        friction = self._generate_player_friction(primary, secondary, stats)
        
        # Save to database
        self._save_archetype(player_id, stats.get('name', 'Unknown'), primary, 
                            secondary, scores, friction, tracking_used)
        
        return {
            'player_id': player_id,
            'name': stats.get('name', 'Unknown'),
            'primary': primary,
            'secondary': secondary,
            'scores': scores,
            'friction_matrix': friction,
            'tracking_data_used': tracking_used,
        }
    
    def _merge_tracking_data(self, stats: Dict, tracking: Dict):
        """Merge tracking data into stats dict for archetype scoring"""
        # Hustle data
        if tracking.get('hustle'):
            hustle = tracking['hustle']
            stats['contested_shots'] = hustle.get('contested_shots', 0)
            stats['contested_shots_2pt'] = hustle.get('contested_shots_2pt', 0)
            stats['contested_shots_3pt'] = hustle.get('contested_shots_3pt', 0)
            stats['deflections'] = hustle.get('deflections', 0)
            stats['charges_drawn'] = hustle.get('charges_drawn', 0)
            stats['screen_assists'] = hustle.get('screen_assists', 0)
            stats['loose_balls'] = hustle.get('loose_balls_recovered', 0)
        
        # Defense tracking
        if tracking.get('defense'):
            defense = tracking['defense']
            stats['d_fg_pct'] = defense.get('d_fg_pct', 0)
            stats['pct_plusminus'] = defense.get('pct_plusminus', 0)
        
        # Advanced stats
        if tracking.get('advanced'):
            adv = tracking['advanced']
            stats['off_rating'] = adv.get('off_rating', 0)
            stats['def_rating'] = adv.get('def_rating', 0)
            stats['net_rating'] = adv.get('net_rating', 0)
            stats['usg_pct'] = adv.get('usg_pct', 0)
            stats['ast_ratio'] = adv.get('ast_ratio', 0)
            stats['reb_pct'] = adv.get('reb_pct', 0)
            stats['ts_pct'] = adv.get('ts_pct', 0)
            stats['pace'] = adv.get('pace', 0)
    
    def _calculate_archetype_score(self, stats: Dict, criteria: Dict) -> float:
        """
        Calculate how well a player matches an archetype (0-1).
        Supports both minimum thresholds and maximum thresholds (negative values).
        """
        if not criteria:
            return 0
        
        total_score = 0
        criteria_count = 0
        
        for stat, threshold in criteria.items():
            player_value = stats.get(stat, 0) or 0
            
            # Handle max thresholds (negative values mean "less than")
            if threshold < 0:
                max_threshold = abs(threshold)
                if player_value <= max_threshold:
                    # Score higher if well below threshold
                    ratio = 1 - (player_value / max_threshold) if max_threshold > 0 else 1
                    score = min(ratio + 0.5, 1.0)
                else:
                    score = 0.3  # Penalty for exceeding max threshold
            else:
                # Normal min threshold
                if threshold > 0:
                    ratio = min(player_value / threshold, 2.0)
                    score = min(ratio / 2, 1.0)
                else:
                    score = 0.5
            
            total_score += score
            criteria_count += 1
        
        return total_score / criteria_count if criteria_count > 0 else 0
    
    def _generate_player_friction(self, primary: str, secondary: str, stats: Dict) -> Dict:
        """
        Generate friction multipliers based on player's archetypes.
        NOW uses actual DFG% data for more precise friction.
        """
        friction = {}
        
        # Add player-specific DFG% friction
        d_fg_pct = stats.get('d_fg_pct', 0)
        pct_plusminus = stats.get('pct_plusminus', 0)
        
        if pct_plusminus != 0:
            friction['individual_defense'] = {
                'd_fg_pct': d_fg_pct,
                'pct_plusminus': pct_plusminus,
                'friction_multiplier': 1 + pct_plusminus,  # e.g., -0.05 = 0.95x
                'reason': f'DFG% Impact: {pct_plusminus*100:+.1f}% vs league average',
            }
        
        # Add archetype-based friction
        for archetype in [primary, secondary]:
            if archetype and archetype in FRICTION_MATRIX:
                archetype_friction = FRICTION_MATRIX[archetype]
                for matchup, adjustments in archetype_friction.items():
                    if matchup not in friction:
                        friction[matchup] = {}
                    for stat, value in adjustments.items():
                        if stat != 'reason':
                            current = friction[matchup].get(stat, 1.0)
                            friction[matchup][stat] = round(current * value, 3)
                    friction[matchup]['reason'] = adjustments.get('reason', '')
        
        return friction
    
    def _get_player_stats(self, player_id: str) -> Optional[Dict]:
        """Get player's stats for archetype classification"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Try rolling averages first
        cursor.execute("""
            SELECT pra.*, pb.player_name as name, pb.height
            FROM player_rolling_averages pra
            LEFT JOIN player_bio pb ON pra.player_id = pb.player_id
            WHERE pra.player_id = ?
        """, (str(player_id),))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # Parse height to inches
        height_inches = 0
        height_str = row['height'] if 'height' in row.keys() else ''
        if height_str and '-' in str(height_str):
            try:
                feet, inches = str(height_str).split('-')
                height_inches = int(feet) * 12 + int(inches)
            except:
                pass
        
        return {
            'name': row['name'] if 'name' in row.keys() else '',
            'ppg': row['avg_points'] or 0,
            'rpg': row['avg_rebounds'] or 0,
            'apg': row['avg_assists'] or 0,
            'spg': 0,
            'bpg': 0,
            'fg_pct': 0.45,
            'fg3m': 0,
            'fg3_pct': 0.35,
            'fta': 0,
            'stocks': 0,
            'height_inches': height_inches,
            'ast_to_ratio': 2.0,
            # Tracking data placeholders (will be merged)
            'deflections': 0,
            'contested_shots': 0,
            'contested_shots_3pt': 0,
            'd_fg_pct': 0,
            'pct_plusminus': 0,
        }
    
    def _save_archetype(self, player_id: str, name: str, primary: str, 
                        secondary: str, scores: Dict, friction: Dict, tracking_used: bool):
        """Save archetype classification to database"""
        conn = self._get_connection()
        
        conn.execute("""
            INSERT OR REPLACE INTO player_archetypes
            (player_id, player_name, primary_archetype, secondary_archetype,
             archetype_scores, friction_matrix, tracking_data_used, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(player_id), name, primary, secondary,
            json.dumps(scores), json.dumps(friction), 1 if tracking_used else 0,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_archetype(self, player_id: str) -> Optional[Dict]:
        """Get cached archetype for player"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM player_archetypes WHERE player_id = ?
        """, (str(player_id),))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'player_id': row['player_id'],
                'name': row['player_name'],
                'primary': row['primary_archetype'],
                'secondary': row['secondary_archetype'],
                'scores': json.loads(row['archetype_scores']) if row['archetype_scores'] else {},
                'friction_matrix': json.loads(row['friction_matrix']) if row['friction_matrix'] else {},
                'tracking_data_used': bool(row['tracking_data_used']) if 'tracking_data_used' in row.keys() else False,
                'updated_at': row['updated_at'],
            }
        return None
    
    def get_dfg_friction(self, defender_id: str) -> Tuple[float, str]:
        """
        Get individual DFG% friction for a specific defender.
        Returns (multiplier, reason).
        """
        if not self.tracking:
            return 1.0, 'No tracking data'
        
        defense = self.tracking.get_player_defense(defender_id)
        if not defense:
            return 1.0, 'No defense data'
        
        pct_plusminus = defense.get('pct_plusminus', 0)
        d_fg_pct = defense.get('d_fg_pct', 0)
        
        # Convert to friction multiplier
        # If defender is -5% vs average, opponent shoots 5% worse = 0.95 multiplier
        multiplier = 1 + pct_plusminus
        
        player_name = defense.get('player_name', 'Unknown')
        reason = f"{player_name} DFG%: {d_fg_pct*100:.1f}% ({pct_plusminus*100:+.1f}% vs avg)"
        
        return round(multiplier, 3), reason
    
    def get_friction_multiplier(self, player_archetype: str, opponent_archetype: str, 
                                 stat: str) -> Tuple[float, str]:
        """Get friction multiplier for a specific stat based on archetype matchup."""
        if not player_archetype or not opponent_archetype:
            return 1.0, 'No archetype data'
        
        matchup_key = f'vs_{opponent_archetype}'
        
        if player_archetype in FRICTION_MATRIX:
            matchup = FRICTION_MATRIX[player_archetype].get(matchup_key, {})
            multiplier = matchup.get(stat, 1.0)
            reason = matchup.get('reason', '')
            return multiplier, reason
        
        return 1.0, 'No friction data for matchup'
    
    def apply_friction_to_projection(self, projection: float, player_id: str,
                                      opponent_player_ids: List[str], stat: str) -> Dict:
        """
        Apply friction adjustments using BOTH archetype AND individual DFG%.
        Returns adjusted projection with detailed explanations.
        """
        player_arch = self.get_archetype(player_id)
        if not player_arch:
            return {'projection': projection, 'adjusted': projection, 'friction': 1.0, 'reasons': []}
        
        total_friction = 1.0
        reasons = []
        primary_defender = None
        
        for i, opp_id in enumerate(opponent_player_ids[:5]):
            # Get archetype-based friction
            opp_arch = self.get_archetype(opp_id)
            if opp_arch and opp_arch.get('primary'):
                mult, reason = self.get_friction_multiplier(
                    player_arch.get('primary'),
                    opp_arch.get('primary'),
                    stat
                )
                if mult != 1.0:
                    total_friction *= mult
                    reasons.append(f"{opp_arch.get('name', 'Opponent')}: {reason} ({mult:.2f}x)")
            
            # Get individual DFG% friction for primary defender
            if i == 0:  # First opponent is primary defender
                dfg_mult, dfg_reason = self.get_dfg_friction(opp_id)
                if dfg_mult != 1.0:
                    total_friction *= dfg_mult
                    reasons.append(dfg_reason)
                    primary_defender = {
                        'id': opp_id,
                        'name': opp_arch.get('name') if opp_arch else 'Unknown',
                        'dfg_multiplier': dfg_mult,
                        'reason': dfg_reason,
                    }
        
        adjusted = projection * total_friction
        
        return {
            'projection': projection,
            'adjusted': round(adjusted, 1),
            'friction': round(total_friction, 3),
            'reasons': reasons,
            'primary_defender': primary_defender,
        }


# Singleton
_engine = None

def get_archetype_engine() -> ArchetypeEngine:
    global _engine
    if _engine is None:
        _engine = ArchetypeEngine()
    return _engine


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    engine = get_archetype_engine()
    
    print("Testing Archetype Engine v2.0")
    print("=" * 50)
    
    # Classify LeBron
    result = engine.classify_player("2544")
    print(f"\nLeBron Classification:")
    print(f"  Primary: {result.get('primary')}")
    print(f"  Secondary: {result.get('secondary')}")
    print(f"  Tracking Used: {result.get('tracking_data_used')}")
    print(f"  Top Scores: {dict(sorted(result.get('scores', {}).items(), key=lambda x: x[1], reverse=True)[:3])}")
    
    # Test DFG friction
    dfg_mult, dfg_reason = engine.get_dfg_friction("201142")  # Kevin Durant
    print(f"\nKD DFG Friction: {dfg_mult}x - {dfg_reason}")
