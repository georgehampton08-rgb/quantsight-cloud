import logging
from typing import List, Dict, Any, Optional
from google.cloud.firestore_v1.base_query import FieldFilter
from services.nba_pbp_service import PlayEvent

logger = logging.getLogger(__name__)

# To prevent cyclical import or redefining initialization, we import the singleton getter
from firestore_db import get_firestore_db

class FirebasePBPService:
    @staticmethod
    def get_db():
        return get_firestore_db()

    @staticmethod
    def save_game_metadata(game_id: str, metadata: Dict[str, Any]):
        """Save high-level metadata for a live game."""
        db = FirebasePBPService.get_db()
        doc_ref = db.collection('live_games').document(str(game_id))
        doc_ref.set(metadata, merge=True)
        # logger.info(f"Saved metadata for game {game_id}")

    @staticmethod
    def save_plays_batch(game_id: str, plays: List[PlayEvent]):
        """
        Idempotent batch write for plays.
        Uses play.playId as the document ID directly, preventing duplication.
        """
        if not plays:
            return

        db = FirebasePBPService.get_db()
        plays_ref = db.collection('live_games').document(str(game_id)).collection('plays')
        
        # Firestore limits batches to 500
        batch_size = 450
        for i in range(0, len(plays), batch_size):
            batch = db.batch()
            batch_plays = plays[i:i + batch_size]
            for play in batch_plays:
                doc_ref = plays_ref.document(str(play.playId))
                batch.set(doc_ref, play.model_dump(), merge=True)
            batch.commit()
            
        logger.info(f"Successfully batch-wrote {len(plays)} plays for game {game_id}")

    @staticmethod
    def get_cached_plays(game_id: str, limit: int = 1500) -> List[Dict[str, Any]]:
        """Fetch cached plays sorted by sequence number."""
        db = FirebasePBPService.get_db()
        plays_ref = db.collection('live_games').document(str(game_id)).collection('plays')
        
        # We order by sequence number ascending so frontend receives them in chronological order
        query = plays_ref.order_by("sequenceNumber").limit(limit)
        docs = query.stream()
        
        return [doc.to_dict() for doc in docs]

    @staticmethod
    def update_cache_snapshot(game_id: str, plays_count: int, last_polled: str):
        """Update the fast-read cache snapshot document."""
        db = FirebasePBPService.get_db()
        doc_ref = db.collection('game_cache').document(str(game_id))
        doc_ref.set({
            "playsCount": plays_count,
            "lastPolled": last_polled
        }, merge=True)

firebase_pbp_service = FirebasePBPService()
