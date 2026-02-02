"""
Cloud Run Entry Point for QuantSight Live Pulse
================================================
Headless FastAPI server for Cloud Run deployment.
No SSE endpoints - purely writes to Firebase for mobile/web consumption.

Architecture:
  AsyncPulseProducer (Cloud) → FirebaseAdminService → Firestore
                            (no local cache, no SSE)

Environment:
  - PORT: Cloud Run sets this dynamically
  - FIREBASE_PROJECT_ID: From .env.cloud
  - GOOGLE_APPLICATION_CREDENTIALS: Mounted via Secret Manager
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Configure logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import cloud-native pulse producer
from services.async_pulse_producer_cloud import start_cloud_producer, stop_cloud_producer, get_cloud_producer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan for startup/shutdown."""
    # Startup
    logger.info("🚀 Cloud Run starting up...")
    logger.info(f"   └─ PORT: {os.getenv('PORT', '8080')}")
    logger.info(f"   └─ FIREBASE_PROJECT_ID: {os.getenv('FIREBASE_PROJECT_ID', 'Not set')}")
    
    # Start the cloud producer
    try:
        await start_cloud_producer()
        logger.info("✅ Cloud pulse producer started")
    except Exception as e:
        logger.error(f"❌ Failed to start cloud producer: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Cloud Run shutting down...")
    await stop_cloud_producer()
    logger.info("✅ Cloud pulse producer stopped")


app = FastAPI(
    title="QuantSight Live Pulse (Cloud)",
    description="Headless live data producer for Firebase",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for web/mobile clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint - redirect to health."""
    return {"service": "QuantSight Live Pulse (Cloud)", "status": "running"}


@app.get("/health")
async def health():
    """Health check for Cloud Run."""
    producer = get_cloud_producer()
    
    if not producer:
        raise HTTPException(status_code=503, detail="Producer not initialized")
    
    status = producer.get_status()
    
    # Cloud Run expects 200 for healthy, 503 for unhealthy
    if not status.get("running"):
        raise HTTPException(status_code=503, detail="Producer not running")
    
    return {
        "status": "healthy",
        "producer": status,
        "firebase": {
            "enabled": status.get("firebase_enabled", False),
            "write_errors": status.get("firebase_write_errors", 0)
        }
    }


@app.get("/status")
async def status():
    """Detailed status endpoint for monitoring."""
    producer = get_cloud_producer()
    
    if not producer:
        return {"error": "Producer not initialized"}
    
    return producer.get_status()


# Cloud Run will call this on PORT environment variable
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
