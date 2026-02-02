"""
Firebase Admin Service for QuantSight Live Pulse
=================================================
Async integration layer for "Shadow Writes" to Firebase Firestore.
Designed to integrate with AsyncPulseProducer without blocking the sub-1s SSE cycle.

Architecture:
  AsyncPulseProducer → FirebaseAdminService → Firestore (non-blocking)
                    ↘ LivePulseCache → SSE (existing, unaffected)

Features:
- Batch writes (game + 10 players + alpha spikes in 1 network call)
- Async fire-and-forget (doesn't block producer loop)
- Selective alpha spike updates (blazing/vacuum only for cost optimization)
- TTL-based spike expiration (5-minute auto-cleanup)
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import asdict

logger = logging.getLogger(__name__)

# Firebase Admin SDK import with fallback
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False
    SERVER_TIMESTAMP = None
    logger.warning("Firebase Admin SDK not installed. Run: pip install firebase-admin google-cloud-firestore")


class FirebaseAdminService:
    """
    Async Firebase Admin SDK integration for LivePulseProducer.
    Writes live game data to Firestore for mobile/web consumption.
    
    Usage:
        service = FirebaseAdminService()
        await service.upsert_game_state(game_state)  # Non-blocking
    """
    
    VERSION = "1.0.0"
    ALPHA_SPIKE_TTL_SECONDS = 300  # 5 minutes
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Firebase Admin SDK.
        
        Args:
            credentials_path: Path to Firebase service account JSON
                             Defaults to ~/.gemini/firebase_credentials.json
        """
        self.db = None
        self.enabled = False
        self._executor = None
        
        if not HAS_FIREBASE:
            logger.error("❌ Firebase Admin SDK not available - shadow writes disabled")
            return
        
        # Resolve credentials path
        if credentials_path is None:
            credentials_path = str(Path.home() / '.gemini' / 'firebase_credentials.json')
        
        cred_path = Path(credentials_path).expanduser()
        
        if not cred_path.exists():
            logger.warning(f"⚠️ Firebase credentials not found: {cred_path}")
            logger.warning("   Shadow writes disabled. Create credentials to enable.")
            return
        
        try:
            cred = credentials.Certificate(str(cred_path))
            
            # Check if already initialized (prevents duplicate app error)
            try:
                firebase_admin.get_app()
                logger.info("🔥 Using existing Firebase app instance")
            except ValueError:
                firebase_admin.initialize_app(cred)
                logger.info("🔥 Firebase Admin SDK initialized")
            
            self.db = firestore.client()
            self.enabled = True
            
            logger.info(f"✅ FirebaseAdminService v{self.VERSION} ready")
            logger.info(f"   ├─ Alpha Spike TTL: {self.ALPHA_SPIKE_TTL_SECONDS}s")
            logger.info(f"   └─ Batch Writes: Enabled")
            
        except Exception as e:
            logger.error(f"❌ Firebase initialization failed: {e}")
            self.enabled = False
    
    async def upsert_game_state(self, game_state: Any) -> bool:
        """
        Upsert live game state to Firestore using a Write Batch.
        Performs all operations in a single network round-trip.
        
        Operations per batch:
          1. Set/Update game metadata document
          2. Set/Update top 10 leaders in players subcollection
          3. Create/Update alpha spikes (blazing/vacuum only)
        
        Args:
            game_state: LiveGameState object from AsyncPulseProducer
            
        Returns:
            True if write succeeded, False otherwise
        """
        if not self.enabled or not self.db:
            return False
        
        try:
            # Create batch for atomic writes
            batch = self.db.batch()
            
            game_id = game_state.game_id
            game_ref = self.db.collection('live_games').document(game_id)
            
            # === 1. Game Metadata ===
            game_data = {
                'home_team': game_state.home_team,
                'away_team': game_state.away_team,
                'home_score': game_state.home_score,
                'away_score': game_state.away_score,
                'clock': game_state.clock,
                'period': game_state.period,
                'status': game_state.status,
                'is_garbage_time': game_state.is_garbage_time,
                'last_updated': SERVER_TIMESTAMP
            }
            batch.set(game_ref, game_data, merge=True)
            
            # === 2. Top 10 Leaders ===
            leaders = game_state.leaders[:10] if game_state.leaders else []
            
            for idx, leader in enumerate(leaders):
                player_id = leader.get('player_id', str(idx))
                player_ref = game_ref.collection('players').document(player_id)
                
                player_data = {
                    'player_id': player_id,
                    'name': leader.get('name', 'Unknown'),
                    'team': leader.get('team', ''),
                    'rank': idx + 1,
                    'pie': leader.get('pie', 0.0),
                    'plus_minus': leader.get('plus_minus', 0.0),
                    'ts_pct': leader.get('ts_pct', 0.0),
                    'efg_pct': leader.get('efg_pct', 0.0),
                    'heat_status': leader.get('heat_status', 'steady'),
                    'efficiency_trend': leader.get('efficiency_trend', 'steady'),
                    'matchup_difficulty': leader.get('matchup_difficulty'),
                    'opponent_team': leader.get('opponent_team'),
                    'opponent_def_rating': leader.get('opponent_def_rating'),
                    'has_usage_vacuum': leader.get('has_usage_vacuum', False),
                    'usage_bump': leader.get('usage_bump'),
                    'stats': leader.get('stats', {}),
                    'min': leader.get('min', '0:00'),
                    'updated_at': SERVER_TIMESTAMP
                }
                batch.set(player_ref, player_data, merge=True)
                
                # === 3. Alpha Spikes (Blazing or Usage Vacuum only) ===
                is_blazing = leader.get('heat_status') == 'blazing'
                has_vacuum = leader.get('has_usage_vacuum', False)
                
                if is_blazing or has_vacuum:
                    spike_ref = game_ref.collection('alpha_spikes').document(player_id)
                    
                    # Calculate expiration time
                    expires_at = datetime.utcnow() + timedelta(seconds=self.ALPHA_SPIKE_TTL_SECONDS)
                    
                    spike_data = {
                        'player_id': player_id,
                        'player_name': leader.get('name', 'Unknown'),
                        'team': leader.get('team', ''),
                        'spike_type': 'blazing' if is_blazing else 'usage_vacuum',
                        'pie': leader.get('pie', 0.0),
                        'context': self._generate_spike_context(leader),
                        'stats': leader.get('stats', {}),
                        'created_at': SERVER_TIMESTAMP,
                        'expires_at': expires_at
                    }
                    
                    # Include type-specific data
                    if is_blazing:
                        spike_data['matchup_difficulty'] = leader.get('matchup_difficulty')
                        spike_data['opponent_team'] = leader.get('opponent_team')
                        spike_data['opponent_def_rating'] = leader.get('opponent_def_rating')
                    
                    if has_vacuum:
                        spike_data['usage_bump'] = leader.get('usage_bump')
                        spike_data['vacuum_source'] = leader.get('vacuum_source', 'Team need')
                    
                    batch.set(spike_ref, spike_data, merge=True)
            
            # Commit batch in executor (non-blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, batch.commit)
            
            logger.debug(f"✅ Firebase: Wrote {game_id} ({len(leaders)} leaders)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase write failed for {game_state.game_id}: {e}")
            return False
    
    def _generate_spike_context(self, leader: Dict) -> str:
        """
        Generate human-readable context string for alpha spike notifications.
        
        Examples:
          - "🔥 Destroying #1 Defense"
          - "🔥 Hot vs LAC (112.3 DEF Rating)"
          - "⚡ +12% Usage vs Season"
        
        Args:
            leader: Player leader dict with stats and context
            
        Returns:
            Human-readable context string for mobile display
        """
        heat_status = leader.get('heat_status', 'steady')
        matchup = leader.get('matchup_difficulty', 'average')
        opponent = leader.get('opponent_team', 'Unknown')
        opponent_rating = leader.get('opponent_def_rating')
        has_vacuum = leader.get('has_usage_vacuum', False)
        usage_bump = leader.get('usage_bump', 0)
        
        # Blazing: Hot performance context
        if heat_status == 'blazing':
            if matchup == 'elite':
                # Top-tier defense domination
                if opponent_rating and opponent_rating <= 108:
                    return f"🔥 Destroying #{self._get_def_rank(opponent_rating)} Defense"
                return f"🔥 Dominating {opponent} Elite Defense"
            elif matchup == 'soft':
                return f"🔥 Exploiting {opponent} Weak Defense"
            else:
                if opponent_rating:
                    return f"🔥 Hot vs {opponent} ({opponent_rating:.1f} DEF)"
                return f"🔥 On Fire vs {opponent}"
        
        # Freezing: Cold performance (red flag)
        elif heat_status == 'freezing':
            if matchup == 'soft':
                return f"❄️ Struggling vs {opponent} Weak Defense"
            return f"❄️ Cold Performance vs {opponent}"
        
        # Usage Vacuum: Elevated usage due to missing teammates
        elif has_vacuum:
            if usage_bump and usage_bump > 0:
                return f"⚡ +{usage_bump:.0f}% Usage vs Season"
            return "⚡ Usage Vacuum (Team Need)"
        
        # Default fallback
        return "🎯 Alpha Opportunity Detected"
    
    def _get_def_rank(self, def_rating: float) -> str:
        """Estimate defensive rank from rating (rough approximation)."""
        if def_rating <= 106:
            return "1"
        elif def_rating <= 107:
            return "2-3"
        elif def_rating <= 108:
            return "4-5"
        else:
            return "Top 10"
    
    async def get_game_state(self, game_id: str) -> Optional[Dict]:
        """
        Fetch a game state from Firestore (for testing/validation).
        
        Args:
            game_id: The game ID to fetch
            
        Returns:
            Game data dict or None if not found
        """
        if not self.enabled or not self.db:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            doc_ref = self.db.collection('live_games').document(game_id)
            doc = await loop.run_in_executor(None, doc_ref.get)
            
            if doc.exists:
                data = doc.to_dict()
                data['game_id'] = game_id
                return data
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch game {game_id}: {e}")
            return None
    
    async def get_alpha_spikes(self, game_id: str) -> List[Dict]:
        """
        Fetch alpha spikes for a game (for testing/validation).
        
        Args:
            game_id: The game ID to fetch spikes for
            
        Returns:
            List of alpha spike dicts
        """
        if not self.enabled or not self.db:
            return []
        
        try:
            loop = asyncio.get_event_loop()
            spikes_ref = self.db.collection('live_games').document(game_id).collection('alpha_spikes')
            docs = await loop.run_in_executor(None, lambda: list(spikes_ref.stream()))
            
            return [doc.to_dict() for doc in docs]
            
        except Exception as e:
            logger.error(f"Failed to fetch spikes for {game_id}: {e}")
            return []
    
    async def cleanup_expired_spikes(self) -> int:
        """
        Clean up expired alpha spikes (enforce TTL).
        Call periodically to prevent unbounded growth.
        
        Returns:
            Number of spikes deleted
        """
        if not self.enabled or not self.db:
            return 0
        
        try:
            now = datetime.utcnow()
            loop = asyncio.get_event_loop()
            
            # Query expired spikes across all games
            spikes_ref = self.db.collection_group('alpha_spikes')
            query = spikes_ref.where('expires_at', '<', now)
            
            docs = await loop.run_in_executor(None, lambda: list(query.stream()))
            
            if not docs:
                return 0
            
            # Delete in batch
            batch = self.db.batch()
            for doc in docs:
                batch.delete(doc.reference)
            
            await loop.run_in_executor(None, batch.commit)
            
            logger.info(f"🧹 Cleaned up {len(docs)} expired alpha spikes")
            return len(docs)
            
        except Exception as e:
            logger.error(f"Spike cleanup failed: {e}")
            return 0


# === Singleton Instance ===
_firebase_service: Optional[FirebaseAdminService] = None


def get_firebase_service(credentials_path: Optional[str] = None) -> Optional[FirebaseAdminService]:
    """
    Get or create the global Firebase service singleton.
    Returns None if Firebase is not available/configured.
    """
    global _firebase_service
    
    if _firebase_service is None:
        _firebase_service = FirebaseAdminService(credentials_path)
    
    return _firebase_service if _firebase_service.enabled else None
