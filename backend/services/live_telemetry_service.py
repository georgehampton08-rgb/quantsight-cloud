"""
Live Telemetry Service
======================
Polls NBA live data and syncs to Firestore for mobile/web consumption.

Schema (Mobile-Ready):
{
  "gameId": "0022300123",
  "meta": { "clock": "Q4 04:30", "period": 4, "status": "LIVE" },
  "score": { "home": 105, "away": 102, "diff": 3 },
  "leaders": [ ...list of alpha players... ]
}
"""
import time
import json
import logging
import random
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

# Try importing firebase (might not be installed yet)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

# Try importing NBA API (if available)
try:
    from nba_api.live.nba.endpoints import boxscore
    HAS_NBA_API = True
except ImportError:
    HAS_NBA_API = False

logger = logging.getLogger(__name__)

class LiveTelemetryService:
    def __init__(self, db_path: Optional[str] = None, use_firebase: bool = True):
        self.running = False
        self.use_firebase = use_firebase and HAS_FIREBASE
        self.firestore_db = None
        
        # Initialize Firebase
        if self.use_firebase:
            try:
                # Check for standard credentials path
                cred_path = Path.home() / '.gemini' / 'firebase_credentials.json'
                if cred_path.exists():
                    cred = credentials.Certificate(str(cred_path))
                    firebase_admin.initialize_app(cred)
                    self.firestore_db = firestore.client()
                    logger.info("🔥 Firebase initialized successfully")
                else:
                    logger.warning(f"⚠️ Firebase credentials not found at {cred_path}")
                    self.use_firebase = False
            except Exception as e:
                logger.error(f"❌ Firebase init failed: {e}")
                self.use_firebase = False
        else:
            logger.info("ℹ️ Running in LOCAL MODE (No Firebase)")

    def push_to_hot_store(self, collection: str, doc_id: str, data: Dict):
        """Push update to Firestore Hot Store."""
        if not self.use_firebase or not self.firestore_db:
            # In local mode, just print the update (or save to local file if needed)
            if random.random() < 0.05:  # Sample logs to avoid spam
                logger.debug(f"Pushing to {collection}/{doc_id}: {json.dumps(data)[:100]}...")
            return

        try:
            doc_ref = self.firestore_db.collection(collection).document(doc_id)
            doc_ref.set(data, merge=True)
            logger.debug(f"✅ Pushed update to {doc_id}")
        except Exception as e:
            logger.error(f"❌ Push failed: {e}")

    def fetch_live_game_data(self, game_id: str) -> Optional[Dict]:
        """Fetch live data from NBA API (or simulate)."""
        if HAS_NBA_API:
            try:
                box = boxscore.BoxScore(game_id=game_id)
                data = box.get_dict()
                return self._transform_nba_data(data)
            except Exception as e:
                logger.error(f"NBA API fetch failed: {e}")
                return self._simulate_live_data(game_id)
        else:
            return self._simulate_live_data(game_id)

    def _transform_nba_data(self, data: Dict) -> Dict:
        """Transform raw NBA data to Mobile-Ready Schema."""
        game = data.get('game', {})
        
        # Extract clock
        period = game.get('period', 1)
        clock = game.get('gameClock', '12:00')
        status = game.get('gameStatusText', 'LIVE')
        
        # Scores
        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})
        
        # Leaders (simplified PIE calculation)
        leaders = []
        # In a real implementation, we'd parse all players. 
        # For this snippet, we'll extract top scorers as proxies for leaders
        for team in [home, away]:
            for player in team.get('players', []):
                if player.get('status') == 'ACTIVE':
                    stats = player.get('statistics', {})
                    pts = stats.get('points', 0)
                    reb = stats.get('reboundsTotal', 0)
                    ast = stats.get('assists', 0)
                    
                    # Simple in-game PIE proxy
                    pie_proxy = (pts + reb + ast) / 100.0
                    
                    leaders.append({
                        "playerId": str(player.get('personId')),
                        "name": player.get('name'),
                        "team": team.get('teamTricode'),
                        "pie": round(pie_proxy, 3),
                        "stats": {"pts": pts, "reb": reb, "ast": ast}
                    })
        
        # Sort leaders by PIE
        leaders.sort(key=lambda x: x['pie'], reverse=True)
        
        return {
            "gameId": game.get('gameId'),
            "meta": {
                "clock": f"Q{period} {clock}",
                "period": period,
                "status": status
            },
            "score": {
                "home": home.get('score', 0),
                "away": away.get('score', 0),
                "diff": home.get('score', 0) - away.get('score', 0)
            },
            "leaders": leaders[:10]  # Top 10 only
        }

    def _simulate_live_data(self, game_id: str) -> Dict:
        """Simulate data for testing/demo."""
        return {
            "gameId": game_id,
            "meta": {
                "clock": f"Q4 {random.randint(0,11):02d}:{random.randint(0,59):02d}",
                "period": 4,
                "status": "LIVE"
            },
            "score": {
                "home": 100 + random.randint(0, 10),
                "away": 95 + random.randint(0, 10),
                "diff": random.randint(-5, 5)
            },
            "leaders": [
                {
                    "playerId": "2544", 
                    "name": "LeBron James", 
                    "team": "LAL", 
                    "pie": 0.25 + random.random() * 0.05,
                    "stats": {"pts": 28, "reb": 8, "ast": 9}
                },
                {
                    "playerId": "203999", 
                    "name": "Nikola Jokic", 
                    "team": "DEN", 
                    "pie": 0.28 + random.random() * 0.05,
                    "stats": {"pts": 32, "reb": 12, "ast": 10}
                }
            ]
        }

    def run_loop(self):
        """Main polling loop."""
        self.running = True
        logger.info("🚀 Live Telemetry Service Started")
        
        # Fake tracking active games
        active_games = ["0022300123"] 
        
        while self.running:
            for game_id in active_games:
                data = self.fetch_live_game_data(game_id)
                if data:
                    self.push_to_hot_store("live_games", game_id, data)
            
            time.sleep(10)  # 10s polling interval

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = LiveTelemetryService()
    try:
        service.run_loop()
    except KeyboardInterrupt:
        print("Stopping service...")
