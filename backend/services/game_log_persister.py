"""
Game Log Persister - Saves final game stats to Firestore
==========================================================
Persists complete player stats when games end.

Hierarchy: game_logs/{date}/{game_id}/teams/{team}/players/{player_id}
"""
import logging
from typing import Dict, List, Any
from datetime import datetime
from services.firebase_admin_service import get_firebase_service

logger = logging.getLogger(__name__)


class GameLogPersister:
    """Saves complete game stats to Firestore when games finish."""
    
    def __init__(self):
        self._firebase = get_firebase_service()
        self._saved_games: set = set()  # Track which games we've already saved
        
    def save_game_log(self, game_data: Dict[str, Any], boxscore: Any):
        """
        Save complete game log data to Firestore.
        
        Args:
            game_data: Game metadata (game_id, teams, scores, etc.)
            boxscore: NormalizedBoxScore with all player stats
        """
        game_id = game_data.get('game_id')
        if not game_id or game_id in self._saved_games:
            return
        
        try:
            # Get game date (YYYYMMDD format)
            game_date = game_id[:8]  # e.g., "00222400001" -> "00222400"
            
            # Format: YYYY-MM-DD
            formatted_date = f"{game_date[:4]}-{game_date[4:6]}-{game_date[6:8]}"
            
            # Build hierarchical structure
            game_log_data = {
                'game_id': game_id,
                'date': formatted_date,
                'home_team': game_data.get('home_team'),
                'away_team': game_data.get('away_team'),
                'home_score': game_data.get('home_score'),
                'away_score': game_data.get('away_score'),
                'final_period': game_data.get('period'),
                'status': 'FINAL',
                'saved_at': datetime.utcnow().isoformat(),
                'teams': {}
            }
            
            # Extract all players (not just top 10)
            for player in boxscore.all_active_players():
                team = player.team_tricode
                
                if team not in game_log_data['teams']:
                    game_log_data['teams'][team] = {'players': {}}
                
                # Save complete player stats
                player_stats = {
                    'player_id': player.player_id,
                    'name': f"{player.first_name} {player.family_name}",
                    'team': team,
                    'position': player.position,
                    'starter': player.starter,
                    'stats': {
                        'min': player.min,
                        'pts': player.pts,
                        'fgm': player.fgm,
                        'fga': player.fga,
                        'fg_pct': round(player.fgm / player.fga * 100, 1) if player.fga > 0 else 0.0,
                        'fg3m': player.fg3m,
                        'fg3a': player.fg3a,
                        'fg3_pct': round(player.fg3m / player.fg3a * 100, 1) if player.fg3a > 0 else 0.0,
                        'ftm': player.ftm,
                        'fta': player.fta,
                        'ft_pct': round(player.ftm / player.fta * 100, 1) if player.fta > 0 else 0.0,
                        'oreb': player.oreb,
                        'dreb': player.dreb,
                        'reb': player.reb,
                        'ast': player.ast,
                        'stl': player.stl,
                        'blk': player.blk,
                        'tov': player.tov,
                        'pf': player.pf,
                        'plus_minus': player.plus_minus
                    }
                }
                
                game_log_data['teams'][team]['players'][str(player.player_id)] = player_stats
            
            # Save to Firestore: game_logs/{date}/{game_id}
            self._firebase.save_game_log(formatted_date, game_id, game_log_data)
            
            self._saved_games.add(game_id)
            logger.info(f"✅ Saved game log for {game_id} ({len(boxscore.all_active_players())} players)")
            
        except Exception as e:
            logger.error(f"❌ Failed to save game log for {game_id}: {e}", exc_info=True)
