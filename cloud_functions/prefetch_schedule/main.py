"""
Background Job: NBA Schedule Pre-fetcher
Runs every hour to keep schedule cache warm
Deploy as Cloud Function with Cloud Scheduler
"""
import functions_framework
from google.cloud import firestore
from datetime import datetime
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@functions_framework.http
def prefetch_schedule(request):
    """
    HTTP Cloud Function to pre-fetch NBA schedule
    Triggered by Cloud Scheduler every hour
    """
    try:
        logger.info("🕐 Starting hourly schedule pre-fetch...")
        
        # Fetch from NBA API
        from nba_api.live.nba.endpoints import scoreboard
        
        time.sleep(0.6)  # Rate limit
        games_data = scoreboard.ScoreBoard()
        scoreboard_dict = games_data.get_dict()
        
        games = []
        if 'scoreboard' in scoreboard_dict and 'games' in scoreboard_dict['scoreboard']:
            for game in scoreboard_dict['scoreboard']['games']:
                games.append({
                    "gameId": game.get("gameId"),
                    "gameCode": game.get("gameCode"),
                    "status": game.get("gameStatusText", "Scheduled"),
                    "homeTeam": {
                        "tricode": game.get("homeTeam", {}).get("teamTricode"),
                        "score": game.get("homeTeam", {}).get("score", 0)
                    },
                    "awayTeam": {
                        "tricode": game.get("awayTeam", {}).get("teamTricode"),
                        "score": game.get("awayTeam", {}).get("score", 0)
                    },
                    "period": game.get("period", 0),
                    "gameTimeUTC": game.get("gameTimeUTC")
                })
        
        # Store in Firestore
        db = firestore.Client()
        today = str(datetime.now().date())
        
        db.collection('cache').document('schedule').set({
            'date': today,
            'games': games,
            'total': len(games),
            'updated_at': datetime.utcnow(),
            'ttl_minutes': 60
        })
        
        logger.info(f"✅ Pre-fetched and stored {len(games)} games in Firestore")
        
        return {
            "status": "success",
            "games_fetched": len(games),
            "date": today,
            "timestamp": datetime.utcnow().isoformat()
        }, 200
        
    except Exception as e:
        logger.error(f"❌ Error pre-fetching schedule: {e}")
        return {
            "status": "error",
            "error": str(e)
        }, 500
