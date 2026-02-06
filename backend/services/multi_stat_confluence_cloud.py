"""
Multi-Stat Confluence Engine (Firestore Cloud Version)
========================================================
Cloud-compatible version using Firestore instead of SQLite.
Calculates projections for multiple stats: PTS, REB, AST, 3PM
Now with H2H auto-fetch capability for on-demand data population.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

# Import Firestore helpers with fallback for different path configurations
try:
    # Try absolute import first (when running as service)
    from firestore_db import (
        get_firestore_db,
        get_players_by_team,
        get_player_by_id
    )
    HAS_FIRESTORE = True
except ImportError:
    try:
        # Fallback for module-based imports
        from backend.firestore_db import (
            get_firestore_db,
            get_players_by_team,
            get_player_by_id
        )
        HAS_FIRESTORE = True
    except ImportError:
        HAS_FIRESTORE = False

# Import H2H adapter for auto-population
try:
    from services.h2h_firestore_adapter import get_h2h_adapter
    from services.h2h_fetcher import get_h2h_fetcher
    HAS_H2H_ADAPTER = True
except ImportError:
    HAS_H2H_ADAPTER = False
    get_h2h_adapter = None
    get_h2h_fetcher = None

logger = logging.getLogger(__name__)

# League averages for reference
LEAGUE_AVG = {
    'pace': 99.5,
    'pts': 115.0,
    'reb': 44.0,
    'ast': 26.0,
    '3pm': 13.0,
}

class MultiStatConfluenceCloud:
    """
    Multi-stat projection engine using Firestore.
    Cloud-compatible version that doesn't rely on SQLite.
    Features H2H auto-fetch for on-demand data population.
    """
    
    def __init__(self):
        if not HAS_FIRESTORE:
            raise Exception("Firestore not available")
        self.db = get_firestore_db()
        
        # Initialize H2H adapter for cloud persistence
        self.h2h_adapter = None
        self.h2h_fetcher = None
        if HAS_H2H_ADAPTER:
            try:
                self.h2h_adapter = get_h2h_adapter() if get_h2h_adapter else None
                self.h2h_fetcher = get_h2h_fetcher() if get_h2h_fetcher else None
                if self.h2h_adapter:
                    logger.info("✅ H2H adapter integrated into Confluence")
            except Exception as e:
                logger.warning(f"H2H adapter init failed: {e}")
        
        logger.info("MultiStatConfluenceCloud initialized with Firestore")
    
    def get_team_defense(self, team: str) -> Dict:
        """Get team defensive profile from Firestore team_defense collection"""
        try:
            doc = self.db.collection('team_defense').document(team.upper()).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    'def_rating': data.get('def_rating', 110),
                    'opp_pts': data.get('opp_pts', 115),
                    'opp_reb': data.get('opp_reb', 44),
                    'opp_ast': data.get('opp_ast', 26),
                    'opp_fg3_pct': data.get('opp_fg3_pct', 0.36),
                    'pace': data.get('pace', 99.5),
                }
        except Exception as e:
            logger.error(f"Error getting team defense: {e}")
        
        return {
            'def_rating': 110, 'opp_pts': 115, 'opp_reb': 44,
            'opp_ast': 26, 'opp_fg3_pct': 0.36, 'pace': 99.5
        }
    
    def get_player_stats(self, player_id: str) -> Optional[Dict]:
        """Get player's season averages from Firestore"""
        try:
            # Get player data
            player = get_player_by_id(str(player_id))
            if not player:
                return None
            
            # Get stats from player document or player_stats collection
            stats_doc = self.db.collection('player_stats').document(str(player_id)).get()
            
            if stats_doc.exists:
                stats = stats_doc.to_dict()
                return {
                    'name': player.get('name', 'Unknown'),
                    'team': player.get('team', ''),
                    'position': player.get('position', ''),
                    'pts': stats.get('avg_points', stats.get('points_avg', 0)),
                    'reb': stats.get('avg_rebounds', stats.get('rebounds_avg', 0)),
                    'ast': stats.get('avg_assists', stats.get('assists_avg', 0)),
                    '3pm': stats.get('avg_fg3m', stats.get('fg3m_avg', 0)),
                    'trend': stats.get('trend', 'stable'),
                    'hot': stats.get('hot', False),
                    'cold': stats.get('cold', False),
                }
            else:
                # Use stats from player document
                return {
                    'name': player.get('name', 'Unknown'),
                    'team': player.get('team', ''),
                    'position': player.get('position', ''),
                    'pts': player.get('avg_points', player.get('points_avg', 0)),
                    'reb': player.get('avg_rebounds', player.get('rebounds_avg', 0)),
                    'ast': player.get('avg_assists', player.get('assists_avg', 0)),
                    '3pm': player.get('avg_fg3m', player.get('fg3m_avg', 0)),
                    'trend': 'stable',
                    'hot': False,
                    'cold': False,
                }
        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
        return None
    
    def get_h2h_history(self, player_id: str, opponent: str) -> Optional[Dict]:
        """
        Get player's head-to-head stats vs opponent from Firestore.
        Uses shadow-fetch pattern: returns cached data immediately,
        triggers background fetch if data is stale or missing.
        """
        h2h_data = None
        
        # Try H2H adapter first (preferred for cloud)
        if self.h2h_adapter:
            try:
                h2h_data = self.h2h_adapter.get_h2h_stats(player_id, opponent)
                
                # Check freshness - if stale, trigger background refresh
                if h2h_data:
                    is_fresh = self.h2h_adapter.check_freshness(player_id, opponent)
                    if not is_fresh and self.h2h_fetcher:
                        # Trigger async refresh (shadow-fetch)
                        logger.info(f"Triggering H2H refresh for {player_id} vs {opponent}")
                        try:
                            asyncio.create_task(self._async_h2h_fetch(player_id, opponent))
                        except RuntimeError:
                            # No event loop, sync fetch in background thread
                            import threading
                            threading.Thread(
                                target=self._sync_h2h_fetch,
                                args=(player_id, opponent),
                                daemon=True
                            ).start()
                
                if h2h_data and h2h_data.get('games', 0) > 0:
                    return {
                        'pts': h2h_data.get('pts', 0),
                        'reb': h2h_data.get('reb', 0),
                        'ast': h2h_data.get('ast', 0),
                        '3pm': h2h_data.get('3pm', 0),
                        'games': h2h_data.get('games', 0),
                    }
            except Exception as e:
                logger.warning(f"H2H adapter lookup failed: {e}")
        
        # Fallback to direct Firestore lookup (legacy collection)
        try:
            doc_id = f"{player_id}_{opponent.upper()}"
            doc = self.db.collection('player_h2h').document(doc_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                games = data.get('games', 0)
                if games > 0:
                    return {
                        'pts': data.get('pts', data.get('avg_pts', 0)),
                        'reb': data.get('reb', data.get('avg_reb', 0)),
                        'ast': data.get('ast', data.get('avg_ast', 0)),
                        '3pm': data.get('3pm', data.get('avg_fg3m', 0)),
                        'games': games,
                    }
            else:
                # No data exists - trigger fetch if available
                if self.h2h_fetcher:
                    logger.info(f"No H2H data for {player_id} vs {opponent}, triggering fetch")
                    try:
                        asyncio.create_task(self._async_h2h_fetch(player_id, opponent))
                    except RuntimeError:
                        import threading
                        threading.Thread(
                            target=self._sync_h2h_fetch,
                            args=(player_id, opponent),
                            daemon=True
                        ).start()
        except Exception as e:
            logger.error(f"Error getting H2H history: {e}")
        
        return None
    
    async def _async_h2h_fetch(self, player_id: str, opponent: str):
        """Async H2H fetch for shadow-fetch pattern"""
        if self.h2h_fetcher:
            try:
                result = self.h2h_fetcher.fetch_h2h(player_id, opponent)
                logger.info(f"Background H2H fetch complete: {result}")
            except Exception as e:
                logger.warning(f"Background H2H fetch failed: {e}")
    
    def _sync_h2h_fetch(self, player_id: str, opponent: str):
        """Sync H2H fetch for background thread"""
        if self.h2h_fetcher:
            try:
                result = self.h2h_fetcher.fetch_h2h(player_id, opponent)
                logger.info(f"Background H2H fetch complete: {result}")
            except Exception as e:
                logger.warning(f"Background H2H fetch failed: {e}")
    
    def calculate_form_adjustment(self, player_stats: Dict) -> Dict:
        """Calculate form-based adjustments"""
        adjustments = {'pts': 0, 'reb': 0, 'ast': 0, '3pm': 0}
        
        if player_stats.get('hot'):
            adjustments = {'pts': 0.12, 'reb': 0.08, 'ast': 0.10, '3pm': 0.15}
            label = 'HOT'
        elif player_stats.get('cold'):
            adjustments = {'pts': -0.12, 'reb': -0.06, 'ast': -0.08, '3pm': -0.18}
            label = 'COLD'
        elif player_stats.get('trend') == 'up':
            adjustments = {'pts': 0.06, 'reb': 0.04, 'ast': 0.05, '3pm': 0.08}
            label = 'RISING'
        elif player_stats.get('trend') == 'down':
            adjustments = {'pts': -0.06, 'reb': -0.04, 'ast': -0.05, '3pm': -0.10}
            label = 'COOLING'
        else:
            label = 'STEADY'
        
        return {'adjustments': adjustments, 'label': label}
    
    def calculate_defense_adjustment(self, opponent_defense: Dict, stat: str) -> float:
        """Calculate defensive impact on a specific stat"""
        mappings = {
            'pts': ('opp_pts', LEAGUE_AVG['pts']),
            'reb': ('opp_reb', LEAGUE_AVG['reb']),
            'ast': ('opp_ast', LEAGUE_AVG['ast']),
            '3pm': ('opp_fg3_pct', 0.36),
        }
        
        if stat not in mappings:
            return 0
        
        key, avg = mappings[stat]
        opp_value = opponent_defense.get(key, avg)
        
        pct_diff = (opp_value - avg) / avg
        
        if stat == '3pm':
            return pct_diff * 1.0
        elif stat == 'pts':
            return pct_diff * 0.8
        elif stat == 'reb':
            return pct_diff * 0.7
        else:
            return pct_diff * 0.8
    
    def calculate_pace_multiplier(self, home_defense: Dict, away_defense: Dict) -> float:
        """Calculate pace impact on scoring"""
        pace1 = home_defense.get('pace', LEAGUE_AVG['pace'])
        pace2 = away_defense.get('pace', LEAGUE_AVG['pace'])
        avg_pace = (pace1 + pace2) / 2
        
        return 1 + ((avg_pace - LEAGUE_AVG['pace']) / LEAGUE_AVG['pace'])
    
    def calculate_grade(self, projected: float, baseline: float, h2h_avg: float = None) -> tuple:
        """Calculate matchup grade based on projection delta"""
        if baseline == 0:
            return 'C', 'NEUTRAL'
        
        delta_pct = ((projected - baseline) / baseline) * 100
        
        # Add H2H bonus
        h2h_bonus = 0
        if h2h_avg and baseline > 0:
            h2h_delta = (h2h_avg - baseline) / baseline * 100
            if h2h_delta > 10:
                h2h_bonus = 1
            elif h2h_delta > 5:
                h2h_bonus = 0.5
        
        adjusted_delta = delta_pct + h2h_bonus
        
        if adjusted_delta >= 8:
            return 'A', 'SMASH'
        elif adjusted_delta >= 5:
            return 'B', 'GOOD'
        elif adjusted_delta >= 2:
            return 'B-', 'SLIGHT BOOST'
        elif adjusted_delta >= -2:
            return 'C', 'NEUTRAL'
        elif adjusted_delta >= -5:
            return 'D', 'TOUGH'
        elif adjusted_delta >= -8:
            return 'D-', 'AVOID'
        else:
            return 'F', 'FADE'
    
    def calculate_classification(self, delta: float, baseline: float) -> str:
        """Determine TARGET/FADE/NEUTRAL classification"""
        if baseline == 0:
            return 'NEUTRAL'
        
        delta_pct = (delta / baseline) * 100
        
        if delta_pct >= 3:
            return 'TARGET'
        elif delta_pct <= -2:
            return 'FADE'
        else:
            return 'NEUTRAL'
    
    def project_player(self, player_id: str, opponent: str, opponent_defense: Dict, 
                       pace_mult: float) -> Optional[Dict]:
        """Generate multi-stat projection for a player"""
        stats = self.get_player_stats(player_id)
        if not stats:
            return None
        
        h2h = self.get_h2h_history(player_id, opponent)
        form = self.calculate_form_adjustment(stats)
        
        projections = {}
        
        for stat in ['pts', 'reb', 'ast', '3pm']:
            baseline = stats.get(stat, 0)
            
            # Form adjustment
            form_adj = baseline * form['adjustments'].get(stat, 0)
            
            # H2H contribution
            if h2h and h2h.get('games', 0) >= 1:
                h2h_avg = h2h.get(stat, baseline)
                h2h_weight = min(h2h['games'] / 8, 0.35)
                h2h_contrib = (h2h_avg - baseline) * h2h_weight
            else:
                h2h_avg = None
                h2h_contrib = 0
            
            # Defense adjustment
            def_adj = baseline * self.calculate_defense_adjustment(opponent_defense, stat)
            
            # Pace adjustment
            if stat in ['pts', 'ast']:
                pace_adj = pace_mult
            else:
                pace_adj = 1.0 + (pace_mult - 1.0) * 0.5
            
            # Final projection
            raw = baseline + form_adj + h2h_contrib + def_adj
            final = raw * pace_adj
            
            # Calculate delta
            delta = final - baseline
            
            # Grade
            grade, grade_label = self.calculate_grade(final, baseline, h2h_avg)
            
            # Classification
            classification = self.calculate_classification(delta, baseline)
            
            # Confidence score
            confidence = 60
            if h2h and h2h.get('games', 0) >= 2:
                confidence += 20
            if form['label'] in ['HOT', 'COLD']:
                confidence += 10
            confidence += 10
            
            projections[stat] = {
                'baseline': round(baseline, 1),
                'projected': round(max(0, final), 1),
                'delta': round(delta, 1),
                'h2h_avg': round(h2h_avg, 1) if h2h_avg else None,
                'h2h_games': h2h['games'] if h2h else 0,
                'grade': grade,
                'grade_label': grade_label,
                'form': form['label'],
                'confidence': min(confidence, 100),
                'classification': classification,
            }
        
        # Overall classification
        weights = {'pts': 0.40, 'reb': 0.20, 'ast': 0.20, '3pm': 0.20}
        total_score = 0
        best_grade = 'C'
        grade_order = ['A', 'B', 'B-', 'C', 'D', 'D-', 'F']
        
        for stat, weight in weights.items():
            if stat in projections:
                proj = projections[stat]
                baseline = proj['baseline']
                delta = proj['delta']
                if baseline > 0:
                    pct = (delta / baseline) * 100
                    total_score += pct * weight
                stat_grade = proj.get('grade', 'C')
                if grade_order.index(stat_grade) < grade_order.index(best_grade):
                    best_grade = stat_grade
        
        if total_score >= 3:
            overall_class = 'TARGET'
        elif total_score <= -3:
            overall_class = 'FADE'
        else:
            overall_class = 'NEUTRAL'
        
        return {
            'player_id': player_id,
            'player_name': stats['name'],
            'team': stats.get('team', ''),
            'position': stats.get('position', ''),
            'opponent': opponent,
            'projections': projections,
            'form_label': form['label'],
            'classification': overall_class,
            'overall_grade': best_grade,
            'aggregate_score': round(total_score, 1),
        }
    
    def analyze_game(self, home_team: str, away_team: str) -> Dict:
        """Full game analysis with all player projections"""
        home_defense = self.get_team_defense(home_team)
        away_defense = self.get_team_defense(away_team)
        pace_mult = self.calculate_pace_multiplier(home_defense, away_defense)
        
        result = {
            'game': f"{away_team} @ {home_team}",
            'generated_at': datetime.now().isoformat(),
            'matchup_context': {
                'home_team': home_team,
                'away_team': away_team,
                'home_defense': home_defense,
                'away_defense': away_defense,
                'pace_multiplier': round(pace_mult, 3),
                'projected_pace': round((home_defense['pace'] + away_defense['pace']) / 2, 1),
            },
            'projections': [],
        }
        
        # Get players for both teams
        for team, opponent, opp_def in [(away_team, home_team, home_defense), 
                                         (home_team, away_team, away_defense)]:
            try:
                players = get_players_by_team(team.upper(), active_only=True)
                
                # Sort by avg_points if available
                players_sorted = sorted(
                    players, 
                    key=lambda p: p.get('avg_points', p.get('points_avg', 0)), 
                    reverse=True
                )[:10]  # Top 10 players
                
                for player in players_sorted:
                    player_id = player.get('player_id', player.get('id'))
                    if player_id:
                        proj = self.project_player(str(player_id), opponent, opp_def, pace_mult)
                        if proj:
                            proj['team'] = team
                            result['projections'].append(proj)
                            
            except Exception as e:
                logger.error(f"Error getting players for {team}: {e}")
        
        return result
