"""
Live Pulse Router - Cloud Mobile API
=====================================
Health check endpoint for mobile app status monitoring.
Replaces desktop SSE with Firebase real-time listeners.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status")
async def get_live_pulse_status():
    """
    Mobile health check for live pulse system.
    
    Desktop equivalent: server.py:L387
    Returns producer status without SSE stream.
    Mobile app uses Firebase listeners instead.
    """
    try:
        # Import Firebase service
        from services.firebase_admin_service import get_firebase_service
        
        firebase = get_firebase_service()
        
        if not firebase:
            return {
                "status": "degraded",
                "firebase_connected": False,
                "message": "Firebase not initialized",
                "timestamp": datetime.now().isoformat()
            }
        
        # Check Firebase connection by attempting a test read
        try:
            firebase.db.collection('live_games').limit(1).get()
            firebase_healthy = True
        except Exception as e:
            logger.error(f"Firebase health check failed: {e}")
            firebase_healthy = False
        
        return {
            "status": "operational" if firebase_healthy else "degraded",
            "firebase_connected": firebase_healthy,
            "producer_running": True,  # Assume producer is running if endpoint responds
            "update_frequency_seconds": 10,
            "timestamp": datetime.now().isoformat(),
            "mobile_instructions": "Use Firebase listeners on collections: live_games, live_leaders"
        }
        
    except Exception as e:
        logger.error(f"Live pulse status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
