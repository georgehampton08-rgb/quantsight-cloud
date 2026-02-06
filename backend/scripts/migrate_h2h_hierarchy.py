import os
import sys
import logging
import json
from datetime import datetime
from typing import Dict, List, Any

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    print("Error: firebase-admin not installed. Run 'pip install firebase-admin'")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class H2HMigrator:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.db = None
        self._init_firebase()
        
    def _init_firebase(self):
        try:
            if not firebase_admin._apps:
                # Assuming credentials are automatically picked up by secondary app or ADC
                firebase_admin.initialize_app()
            self.db = firestore.client()
            logger.info("✅ Firebase initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            sys.exit(1)

    def migrate_aggregates(self):
        """Migrate player_h2h (flat) to players/{id}/h2h_stats/{opponent} (hierarchical)"""
        logger.info("--- Migrating Aggregates ---")
        source_coll = self.db.collection('player_h2h')
        docs = source_coll.stream()
        
        count = 0
        for doc in docs:
            data = doc.to_dict()
            player_id = data.get('player_id')
            opponent = data.get('opponent')
            
            if not player_id or not opponent:
                logger.warning(f"Skipping doc {doc.id}: Missing player_id or opponent")
                continue
            
            # Target path: players/{player_id}/h2h_stats/{opponent}
            target_ref = self.db.collection('players').document(str(player_id)) \
                                .collection('h2h_stats').document(opponent.upper())
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would move agg: {doc.id} -> {target_ref.path}")
            else:
                target_ref.set(data, merge=True)
                logger.info(f"Migrated agg: {doc.id} -> {target_ref.path}")
            
            count += 1
            
        logger.info(f"Aggregate migration completed: {count} docs processed")

    def migrate_games(self, limit=None):
        """Migrate player_h2h_games (flat) to players/{id}/h2h_games/{opponent}/games/{game_id}"""
        logger.info("--- Migrating Individual Games ---")
        source_coll = self.db.collection('player_h2h_games')
        
        if limit:
            docs = source_coll.limit(limit).stream()
        else:
            docs = source_coll.stream()
            
        count = 0
        batch = self.db.batch()
        batch_count = 0
        
        for doc in docs:
            data = doc.to_dict()
            player_id = data.get('player_id')
            opponent = data.get('opponent')
            game_id = data.get('game_id')
            
            if not player_id or not opponent:
                logger.warning(f"Skipping game {doc.id}: Missing player_id or opponent")
                continue

            # Target game_id or fallback to doc.id
            actual_game_id = game_id or doc.id
            
            # Target path: players/{player_id}/h2h_games/{opponent}/games/{game_id}
            target_ref = self.db.collection('players').document(str(player_id)) \
                                .collection('h2h_games').document(opponent.upper()) \
                                .collection('games').document(str(actual_game_id))
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would move game: {doc.id} -> {target_ref.path}")
            else:
                batch.set(target_ref, data, merge=True)
                batch_count += 1
                
                if batch_count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    logger.info(f"Committed batch of {batch_count} games")
                    batch_count = 0
            
            count += 1
            
        if not self.dry_run and batch_count > 0:
            batch.commit()
            logger.info(f"Committed final batch of {batch_count} games")
            
        logger.info(f"Game migration completed: {count} docs processed")

if __name__ == "__main__":
    # Check for actual run flag
    is_dry_run = "--run" not in sys.argv
    migration_limit = None
    
    # Check for limit
    for arg in sys.argv:
        if arg.startswith("--limit="):
            migration_limit = int(arg.split("=")[1])

    migrator = H2HMigrator(dry_run=is_dry_run)
    
    if is_dry_run:
        logger.info("🚀 STARTING DRY RUN MIGRATION")
    else:
        logger.warning("⚠️ STARTING ACTUAL MIGRATION (DATA WILL BE WRITTEN)")
        
    migrator.migrate_aggregates()
    migrator.migrate_games(limit=migration_limit)
    
    if is_dry_run:
        logger.info("🏁 DRY RUN COMPLETED. Use '--run' to execute.")
    else:
        logger.info("🏁 MIGRATION COMPLETED.")
