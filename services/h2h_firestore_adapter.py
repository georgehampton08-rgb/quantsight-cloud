"""
H2H Firestore Adapter
=====================
Adapter for storing and retrieving H2H (head-to-head) matchup data from Firestore.
Enables auto-population and self-updating when new data is discovered from NBA API.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import firebase_admin
    from firebase_admin import firestore
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False
    firestore = None

logger = logging.getLogger(__name__)

# Default TTL for H2H data freshness (72 hours)
H2H_TTL_HOURS = 72


class H2HFirestoreAdapter:
    """
    Firestore adapter for H2H matchup data.
    
    Collections:
    - player_h2h/{player_id}_{opponent} - Aggregate H2H stats
    - player_h2h_games/{doc_id} - Individual game records
    """
    
    def __init__(self):
        """Initialize Firestore client."""
        if not HAS_FIREBASE:
            logger.warning("Firebase not available. H2H adapter running in degraded mode.")
            self.db = None
            self.enabled = False
            return
        
        try:
            # Use existing Firebase app if initialized
            if firebase_admin._apps:
                self.db = firestore.client()
                self.enabled = True
                logger.info("✅ H2H Firestore Adapter initialized")
            else:
                logger.warning("Firebase not initialized. Call firebase_admin.initialize_app() first.")
                self.db = None
                self.enabled = False
        except Exception as e:
            logger.error(f"H2H Firestore Adapter init failed: {e}")
            self.db = None
            self.enabled = False
    
    def _get_doc_id(self, player_id: str, opponent: str) -> str:
        """Generate document ID for player_h2h collection."""
        return f"{player_id}_{opponent.upper()}"
    
    def get_h2h_stats(self, player_id: str, opponent: str) -> Optional[Dict]:
        """
        Get H2H aggregate stats from Firestore.
        
        Args:
            player_id: NBA player ID
            opponent: Team abbreviation (e.g., 'BOS')
            
        Returns:
            Dict with pts, reb, ast, 3pm, games, updated_at or None if not found
        """
        if not self.enabled or not self.db:
            return None
        
        try:
            doc_id = self._get_doc_id(player_id, opponent)
            doc = self.db.collection('player_h2h').document(doc_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                logger.debug(f"✓ H2H stats found for {player_id} vs {opponent}")
                return data
            else:
                logger.debug(f"No H2H data for {player_id} vs {opponent}")
                return None
                
        except Exception as e:
            logger.error(f"Firestore H2H read failed: {e}")
            return None
    
    def save_h2h_stats(self, player_id: str, opponent: str, stats: Dict) -> bool:
        """
        Save H2H aggregate stats to Firestore.
        
        Args:
            player_id: NBA player ID
            opponent: Team abbreviation
            stats: Dict with pts, reb, ast, 3pm, games
            
        Returns:
            True if successful
        """
        if not self.enabled or not self.db:
            logger.warning("Firestore not enabled, skipping H2H save")
            return False
        
        try:
            doc_id = self._get_doc_id(player_id, opponent)
            
            # Add metadata
            stats['player_id'] = str(player_id)
            stats['opponent'] = opponent.upper()
            stats['updated_at'] = firestore.SERVER_TIMESTAMP
            
            # Upsert
            self.db.collection('player_h2h').document(doc_id).set(
                stats,
                merge=True
            )
            
            logger.info(f"✓ H2H stats saved for {player_id} vs {opponent}")
            return True
            
        except Exception as e:
            logger.error(f"Firestore H2H save failed: {e}")
            return False
    
    def save_h2h_games(self, player_id: str, opponent: str, games: List[Dict]) -> bool:
        """
        Save individual H2H game records to Firestore.
        
        Args:
            player_id: NBA player ID
            opponent: Team abbreviation
            games: List of game dicts with date, pts, reb, ast, fg3m, etc.
            
        Returns:
            True if successful
        """
        if not self.enabled or not self.db:
            return False
        
        if not games:
            return True
        
        try:
            batch = self.db.batch()
            
            for game in games:
                # Create unique doc ID from player + game date
                game_date = game.get('game_date', 'unknown')
                doc_id = f"{player_id}_{opponent.upper()}_{game_date}"
                
                # Add metadata
                game['player_id'] = str(player_id)
                game['opponent'] = opponent.upper()
                game['updated_at'] = firestore.SERVER_TIMESTAMP
                
                doc_ref = self.db.collection('player_h2h_games').document(doc_id)
                batch.set(doc_ref, game, merge=True)
            
            batch.commit()
            logger.info(f"✓ {len(games)} H2H games saved for {player_id} vs {opponent}")
            return True
            
        except Exception as e:
            logger.error(f"Firestore H2H games save failed: {e}")
            return False
    
    def check_freshness(self, player_id: str, opponent: str, ttl_hours: int = H2H_TTL_HOURS) -> bool:
        """
        Check if H2H data is fresh (within TTL).
        
        Args:
            player_id: NBA player ID
            opponent: Team abbreviation
            ttl_hours: Hours before data is considered stale (default 72)
            
        Returns:
            True if data is fresh, False if stale or missing
        """
        if not self.enabled or not self.db:
            return False
        
        try:
            doc_id = self._get_doc_id(player_id, opponent)
            doc = self.db.collection('player_h2h').document(doc_id).get()
            
            if not doc.exists:
                return False
            
            data = doc.to_dict()
            updated_at = data.get('updated_at')
            
            if not updated_at:
                return False
            
            # Convert Firestore timestamp to datetime
            if hasattr(updated_at, 'timestamp'):
                updated_dt = datetime.fromtimestamp(updated_at.timestamp())
            else:
                updated_dt = updated_at
            
            # Check if within TTL
            cutoff = datetime.now() - timedelta(hours=ttl_hours)
            is_fresh = updated_dt > cutoff
            
            logger.debug(f"H2H freshness for {player_id} vs {opponent}: {is_fresh}")
            return is_fresh
            
        except Exception as e:
            logger.error(f"Freshness check failed: {e}")
            return False
    
    def get_h2h_games(self, player_id: str, opponent: str, limit: int = 10) -> List[Dict]:
        """
        Get individual H2H game records from Firestore.
        
        Args:
            player_id: NBA player ID
            opponent: Team abbreviation
            limit: Max games to return
            
        Returns:
            List of game dicts sorted by date descending
        """
        if not self.enabled or not self.db:
            return []
        
        try:
            query = (
                self.db.collection('player_h2h_games')
                .where('player_id', '==', str(player_id))
                .where('opponent', '==', opponent.upper())
                .order_by('game_date', direction=firestore.Query.DESCENDING)
                .limit(limit)
            )
            
            docs = query.stream()
            games = [doc.to_dict() for doc in docs]
            logger.debug(f"✓ Retrieved {len(games)} H2H games for {player_id} vs {opponent}")
            return games
            
        except Exception as e:
            logger.error(f"Firestore H2H games read failed: {e}")
            return []
    
    def batch_upsert_h2h(self, records: List[Dict]) -> bool:
        """
        Batch upsert multiple H2H stats records.
        
        Args:
            records: List of dicts with player_id, opponent, pts, reb, ast, 3pm, games
            
        Returns:
            True if all successful
        """
        if not self.enabled or not self.db:
            return False
        
        if not records:
            return True
        
        try:
            batch = self.db.batch()
            
            for record in records:
                player_id = record.get('player_id')
                opponent = record.get('opponent')
                
                if not player_id or not opponent:
                    continue
                
                doc_id = self._get_doc_id(player_id, opponent)
                record['updated_at'] = firestore.SERVER_TIMESTAMP
                
                doc_ref = self.db.collection('player_h2h').document(doc_id)
                batch.set(doc_ref, record, merge=True)
            
            batch.commit()
            logger.info(f"✓ Batch upserted {len(records)} H2H records")
            return True
            
        except Exception as e:
            logger.error(f"Batch H2H upsert failed: {e}")
            return False
    
    def delete_stale_data(self, ttl_hours: int = H2H_TTL_HOURS * 2) -> int:
        """
        Delete H2H data older than TTL (maintenance operation).
        
        Args:
            ttl_hours: Hours threshold for deletion
            
        Returns:
            Number of documents deleted
        """
        if not self.enabled or not self.db:
            return 0
        
        try:
            cutoff = datetime.now() - timedelta(hours=ttl_hours)
            
            # Query stale documents
            query = self.db.collection('player_h2h').where('updated_at', '<', cutoff)
            docs = query.stream()
            
            deleted = 0
            batch = self.db.batch()
            
            for doc in docs:
                batch.delete(doc.reference)
                deleted += 1
                
                # Commit in batches of 500 (Firestore limit)
                if deleted % 500 == 0:
                    batch.commit()
                    batch = self.db.batch()
            
            if deleted % 500 != 0:
                batch.commit()
            
            logger.info(f"✓ Deleted {deleted} stale H2H records")
            return deleted
            
        except Exception as e:
            logger.error(f"Stale data cleanup failed: {e}")
            return 0


# Singleton instance
_adapter_instance = None


def get_h2h_adapter() -> Optional[H2HFirestoreAdapter]:
    """Get global H2H Firestore adapter instance."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = H2HFirestoreAdapter()
    return _adapter_instance if _adapter_instance.enabled else None


# Quick test
if __name__ == '__main__':
    print("Testing H2H Firestore Adapter")
    print("=" * 40)
    
    adapter = H2HFirestoreAdapter()
    
    if adapter.enabled:
        # Test save
        test_stats = {
            'pts': 27.5,
            'reb': 8.2,
            'ast': 7.1,
            '3pm': 2.3,
            'games': 12
        }
        adapter.save_h2h_stats('2544', 'BOS', test_stats)
        
        # Test read
        stats = adapter.get_h2h_stats('2544', 'BOS')
        print(f"H2H Stats: {stats}")
        
        # Test freshness
        is_fresh = adapter.check_freshness('2544', 'BOS')
        print(f"Is fresh: {is_fresh}")
    else:
        print("❌ Adapter not enabled (Firebase not initialized)")
