"""
Firebase Admin Service - Cloud Backend
=======================================
Handles all Firestore writes for live game data.
Replaces the desktop LivePulseCache with Firebase real-time database.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False
    firestore = None

logger = logging.getLogger(__name__)

# Global Firebase service instance
_firebase_service_instance = None


class FirebaseAdminService:
    """
    Firebase Admin SDK service for writing live game data to Firestore.
    Used by AsyncPulseProducer in cloud mode.
    """
    
    def __init__(self):
        """Initialize Firebase Admin SDK with service account credentials."""
        if not HAS_FIREBASE:
            logger.warning("Firebase Admin SDK not installed. Running in degraded mode.")
            self.db = None
            self.enabled = False
            return
        
        try:
            # Check if already initialized
            if not firebase_admin._apps:
                # Try to get credentials from environment
                cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    logger.info(f"✅ Firebase initialized with credentials: {cred_path}")
                else:
                    # Use Application Default Credentials (works in Cloud Run)
                    firebase_admin.initialize_app()
                    logger.info("✅ Firebase initialized with ADC")
            
            self.db = firestore.client()
            self.enabled = True
            logger.info("✅ Firestore client ready")
            
        except Exception as e:
            logger.error(f"❌ Firebase initialization failed: {e}")
            self.db = None
            self.enabled = False
    
    async def upsert_game_state(self, game_data: Dict[str, Any]) -> bool:
        """
        Update or insert a single game state in Firestore.
        
        Args:
            game_data: Dictionary with game_id, scores, clock, period, status
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.db:
            logger.warning("Firebase not enabled, skipping game state write")
            return False
        
        try:
            game_id = game_data.get('game_id')
            if not game_id:
                logger.error("Game data missing game_id")
                return False
            
            # Add timestamp
            game_data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            # Write to live_games collection
            self.db.collection('live_games').document(game_id).set(
                game_data,
                merge=True  # Update existing or create new
            )
            
            logger.debug(f"✓ Game {game_id} written to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Firestore game write failed: {e}")
            return False
    
    async def upsert_live_leaders(self, leaders_data: List[Dict[str, Any]]) -> bool:
        """
        Update live alpha leaderboard in Firestore.
        
        Args:
            leaders_data: List of player stat dictionaries (top 10 by PIE)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.db:
            logger.warning("Firebase not enabled, skipping leaders write")
            return False
        
        try:
            # Write as batch to ensure atomicity
            batch = self.db.batch()
            
            for idx, player in enumerate(leaders_data):
                player_id = player.get('player_id')
                if not player_id:
                    continue
                    
                # Add metadata
                player['rank'] = idx + 1
                player['updated_at'] = firestore.SERVER_TIMESTAMP
                
                # Reference document
                doc_ref = self.db.collection('live_leaders').document(player_id)
                batch.set(doc_ref, player, merge=True)
            
            # Commit batch
            batch.commit()
            logger.debug(f"✓ {len(leaders_data)} leaders written to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Firestore leaders write failed: {e}")
            return False
    
    async def push_live_games(self, games: List[Dict[str, Any]]) -> bool:
        """
        Batch write multiple games to Firestore.
        
        Args:
            games: List of game state dictionaries
            
        Returns:
            True if all successful, False otherwise
        """
        if not self.enabled or not self.db:
            return False
        
        try:
            batch = self.db.batch()
            
            for game in games:
                game_id = game.get('game_id')
                if not game_id:
                    continue
                
                game['updated_at'] = firestore.SERVER_TIMESTAMP
                doc_ref = self.db.collection('live_games').document(game_id)
                batch.set(doc_ref, game, merge=True)
            
            batch.commit()
            logger.debug(f"✓ {len(games)} games batch written to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Firestore batch write failed: {e}")
            return False
    
    def get_live_games(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Read live games from Firestore (for health checks).
        
        Args:
            limit: Maximum number of games to return
            
        Returns:
            List of game dictionaries
        """
        if not self.enabled or not self.db:
            return []
        
        try:
            docs = self.db.collection('live_games').limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Firestore read failed: {e}")
            return []
    
    async def save_game_log(self, date: str, game_id: str, game_log_data: Dict[str, Any]) -> bool:
        """
        Save final game log data to Firestore with hierarchical structure.
        
        Hierarchy: game_logs/{date}/{game_id}
        
        Args:
            date: Game date (YYYY-MM-DD format)
            game_id: Game ID
            game_log_data: Complete game log with all player stats
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.db:
            logger.warning("Firebase not enabled, skipping game log save")
            return False
        
        try:
            # Write to game_logs/{date}/{game_id}
            doc_ref = self.db.collection('game_logs').document(date).collection('games').document(game_id)
            doc_ref.set(game_log_data)
            
            logger.info(f"✅ Game log saved: {date}/{game_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save game log: {e}")
            return False
    
    async def set_document_nested(
        self, 
        path: str, 
        data: Dict[str, Any], 
        merge: bool = False
    ) -> bool:
        """
        Write to nested Firestore path like "pulse_stats/2026-02-04/games/001/quarters/Q1".
        
        Args:
            path: Slash-separated path (collection/doc/collection/doc/...)
            data: Data to write
            merge: If True, merge with existing data instead of overwriting
            
        Returns:
            True if successful
        """
        if not self.enabled or not self.db:
            return False
        
        try:
            parts = path.strip("/").split("/")
            if len(parts) < 2:
                logger.error(f"Invalid path: {path}")
                return False
            
            # Build reference: alternating collection/document
            ref = self.db.collection(parts[0]).document(parts[1])
            
            for i in range(2, len(parts), 2):
                if i + 1 < len(parts):
                    ref = ref.collection(parts[i]).document(parts[i + 1])
            
            if merge:
                ref.set(data, merge=True)
            else:
                ref.set(data)
            
            logger.debug(f"✅ Nested doc written: {path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Nested write failed: {e}")
            return False
    
    async def get_document_nested(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Read from nested Firestore path.
        
        Args:
            path: Slash-separated path
            
        Returns:
            Document data or None
        """
        if not self.enabled or not self.db:
            return None
        
        try:
            parts = path.strip("/").split("/")
            if len(parts) < 2:
                return None
            
            ref = self.db.collection(parts[0]).document(parts[1])
            
            for i in range(2, len(parts), 2):
                if i + 1 < len(parts):
                    ref = ref.collection(parts[i]).document(parts[i + 1])
            
            doc = ref.get()
            return doc.to_dict() if doc.exists else None
            
        except Exception as e:
            logger.error(f"❌ Nested read failed: {e}")
            return None


    def get_game_dates(self) -> List[str]:
        """
        Return sorted (descending) list of YYYY-MM-DD date strings that have
        at least one saved game in pulse_stats.

        Source: pulse_stats/{YYYY-MM-DD}  (top-level docs are calendar dates)
        """
        import re as _re
        _date_re = _re.compile(r'^20\d{2}-(0[1-9]|1[0-2])-\d{2}$')

        if not self.enabled or not self.db:
            logger.warning("Firebase not enabled — get_game_dates returning []")
            return []

        try:
            top_docs = self.db.collection('pulse_stats').stream()
            dates = [doc.id for doc in top_docs if _date_re.match(doc.id)]
            sorted_dates = sorted(dates, reverse=True)
            logger.info(f"✅ get_game_dates: {len(sorted_dates)} date(s) from pulse_stats")
            return sorted_dates
        except Exception as e:
            logger.error(f"❌ get_game_dates failed: {e}")
            return []

    def get_box_scores_for_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Return final team score summaries for all games on `date`.

        Source: pulse_stats/{date}/games/{game_id}/quarters/
          - Prefers FINAL quarter (cumulative game totals, home_score, away_score)
          - Falls back to most recent quarter if FINAL not yet archived
            (handles pre-2026-02-28 partial data gracefully)
        """
        if not self.enabled or not self.db:
            logger.warning("Firebase not enabled — get_box_scores_for_date returning []")
            return []

        try:
            games_ref = self.db.collection('pulse_stats').document(date).collection('games').stream()
            results: List[Dict[str, Any]] = []

            for game_doc in games_ref:
                gdata = game_doc.to_dict() or {}
                game_id   = gdata.get('game_id', game_doc.id)
                home_team = gdata.get('home_team', 'HOME')
                away_team = gdata.get('away_team', 'AWAY')

                # Fetch all quarter docs
                quarters_ref = (
                    self.db
                    .collection('pulse_stats')
                    .document(date)
                    .collection('games')
                    .document(game_doc.id)
                    .collection('quarters')
                    .stream()
                )
                quarters: Dict[str, Any] = {q.id: q.to_dict() or {} for q in quarters_ref}

                if not quarters:
                    continue

                # Priority: FINAL > latest quarter by label sort
                if 'FINAL' in quarters:
                    best_q = quarters['FINAL']
                else:
                    # Sort: Q1 < Q2 < Q3 < Q4 < OT1 < OT2 < FINAL
                    def _q_sort_key(label: str) -> int:
                        if label == 'FINAL':  return 99
                        if label.startswith('OT'): return 10 + int(label[2:] or 1)
                        if label.startswith('Q'):  return int(label[1:] or 0)
                        return 0
                    best_label = max(quarters.keys(), key=_q_sort_key)
                    best_q = quarters[best_label]

                home_score = int(best_q.get('home_score', 0) or 0)
                away_score = int(best_q.get('away_score', 0) or 0)

                if home_score == 0 and away_score == 0:
                    logger.warning(f"No score data for {date}/{game_id} — skipping")
                    continue

                is_final = 'FINAL' in quarters
                winner = (
                    home_team if home_score > away_score
                    else away_team if away_score > home_score
                    else 'TIE'
                )

                results.append({
                    "game_id":    game_id,
                    "matchup":    f"{away_team} @ {home_team}",
                    "home_team":  home_team,
                    "away_team":  away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "status":     "FINAL" if is_final else "IN PROGRESS",
                    "winner":     winner if is_final else "",
                    "has_final":  is_final,
                })

            logger.info(f"✅ get_box_scores_for_date({date}): {len(results)} game(s) from pulse_stats")
            return results

        except Exception as e:
            logger.error(f"❌ get_box_scores_for_date({date}) failed: {e}")
            return []


def get_firebase_service() -> Optional[FirebaseAdminService]:
    """Get global Firebase service instance (singleton pattern)."""
    global _firebase_service_instance
    if _firebase_service_instance is None:
        _firebase_service_instance = FirebaseAdminService()
    return _firebase_service_instance if _firebase_service_instance.enabled else None
