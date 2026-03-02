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
        Return a sorted (descending) list of all date strings that have at
        least one saved game log in Firestore.

        Scans the top-level `game_logs` collection for document IDs, which
        are YYYY-MM-DD strings written by GameLogPersister.

        Returns:
            List of date strings, e.g. ["2026-02-26", "2026-02-25", ...]
            Empty list if no data or Firebase unavailable.
        """
        if not self.enabled or not self.db:
            logger.warning("Firebase not enabled — get_game_dates returning []")
            return []

        try:
            # Each top-level document in game_logs is a date (YYYY-MM-DD)
            # We limit to 365 to avoid unbounded scans on large collections.
            docs = self.db.collection('game_logs').limit(365).stream()
            dates = [doc.id for doc in docs if doc.id]
            # Sort descending so most-recent date is first
            dates.sort(reverse=True)
            logger.info(f"✅ get_game_dates: found {len(dates)} date(s)")
            return dates
        except Exception as e:
            logger.error(f"❌ get_game_dates failed: {e}")
            return []

    def get_box_scores_for_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Return final team score summaries for all games saved on `date`.

        Only reads from persisted Firestore data (game_logs/{date}/games/*).
        Never calls the live NBA API.

        Score extraction priority:
          1. metadata.home_score / metadata.away_score (written by persister)
          2. Sum of pts across all players per team (fallback for older docs)

        Args:
            date: Game date string in YYYY-MM-DD format.

        Returns:
            List of game summary dicts, e.g.:
            [
                {
                    "game_id": "0022500641",
                    "matchup": "DEN @ DET",
                    "home_team": "DET",
                    "away_team": "DEN",
                    "home_score": 112,
                    "away_score": 98,
                    "status": "FINAL",
                    "winner": "DET"   # or "TIE" if scores equal
                }
            ]
        """
        if not self.enabled or not self.db:
            logger.warning("Firebase not enabled — get_box_scores_for_date returning []")
            return []

        try:
            game_refs = (
                self.db
                .collection('game_logs')
                .document(date)
                .collection('games')
                .stream()
            )

            results: List[Dict[str, Any]] = []

            for doc in game_refs:
                data = doc.to_dict()
                if not data:
                    continue

                game_id = doc.id

                # ── Team tricodes ──────────────────────────────────────────
                # Persister writes metadata.home_team / metadata.away_team
                metadata = data.get('metadata', {}) or {}
                home_team = metadata.get('home_team') or data.get('home_team', 'HOME')
                away_team = metadata.get('away_team') or data.get('away_team', 'AWAY')
                status    = metadata.get('status', 'FINAL')

                # ── Score extraction ───────────────────────────────────────
                # Priority 1: metadata fields written by the persister
                home_score: Optional[int] = metadata.get('home_score')
                away_score: Optional[int] = metadata.get('away_score')

                # Priority 2: sum pts from player sub-maps (fallback)
                if home_score is None or away_score is None:
                    teams_data = data.get('teams', {}) or {}
                    home_pts = 0
                    away_pts = 0

                    for team_code, team_data in teams_data.items():
                        players = team_data.get('players', {}) or {}
                        team_total = sum(
                            int(p.get('pts', 0) or 0)
                            for p in players.values()
                            if isinstance(p, dict)
                        )
                        if team_code == home_team:
                            home_pts = team_total
                        elif team_code == away_team:
                            away_pts = team_total

                    # Only use fallback if at least one team had player data
                    if home_pts > 0 or away_pts > 0:
                        home_score = home_pts
                        away_score = away_pts
                    else:
                        # No usable score data — skip this game
                        logger.warning(
                            f"No score data found for game_log {date}/{game_id} — skipping"
                        )
                        continue

                home_score = int(home_score)
                away_score = int(away_score)

                # ── Winner ────────────────────────────────────────────────
                if home_score > away_score:
                    winner = home_team
                elif away_score > home_score:
                    winner = away_team
                else:
                    winner = 'TIE'

                matchup = metadata.get('matchup') or f"{away_team} @ {home_team}"

                results.append({
                    "game_id":    game_id,
                    "matchup":    matchup,
                    "home_team":  home_team,
                    "away_team":  away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "status":     status,
                    "winner":     winner,
                })

            logger.info(f"✅ get_box_scores_for_date({date}): {len(results)} game(s)")
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
