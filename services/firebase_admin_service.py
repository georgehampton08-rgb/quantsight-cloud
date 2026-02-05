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



def get_firebase_service() -> Optional[FirebaseAdminService]:
    """Get global Firebase service instance (singleton pattern)."""
    global _firebase_service_instance
    if _firebase_service_instance is None:
        _firebase_service_instance = FirebaseAdminService()
    return _firebase_service_instance if _firebase_service_instance.enabled else None
