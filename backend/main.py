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

# Import cloud-native pulse producer (graceful fallback)
try:
    from services.async_pulse_producer_cloud import start_cloud_producer, stop_cloud_producer, get_cloud_producer
    PRODUCER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Cloud producer not available: {e}")
    PRODUCER_AVAILABLE = False

# Import admin routes for database management
try:
    from api.admin_routes import router as admin_router
    ADMIN_ROUTES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Admin routes not available: {e}")
    ADMIN_ROUTES_AVAILABLE = False

# Import public API routes
try:
    from api.public_routes import router as public_router
    PUBLIC_ROUTES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"⚠️ Public routes not available: {e}")
    PUBLIC_ROUTES_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan for startup/shutdown."""
    # Startup
    logger.info("🚀 Cloud Run starting up...")
    logger.info(f"   └─ PORT: {os.getenv('PORT', '8080')}")
    logger.info(f"   └─ FIREBASE_PROJECT_ID: {os.getenv('FIREBASE_PROJECT_ID', 'Not set')}")
    logger.info(f"   └─ DATABASE_URL: {'Set' if os.getenv('DATABASE_URL') else 'Not set'}")
    
    # Start the cloud producer (if available)
    if PRODUCER_AVAILABLE:
        try:
            await start_cloud_producer()
            logger.info("✅ Cloud pulse producer started")
        except Exception as e:
            logger.error(f"❌ Failed to start cloud producer: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Cloud Run shutting down...")
    if PRODUCER_AVAILABLE:
        await stop_cloud_producer()
        logger.info("✅ Cloud pulse producer stopped")


app = FastAPI(
    title="QuantSight Live Pulse (Cloud)",
    description="Headless live data producer for Firebase",
    version="1.0.0",
    lifespan=lifespan
)

# Include admin routes if available
if ADMIN_ROUTES_AVAILABLE:
    app.include_router(admin_router)
    logger.info("✅ Admin routes registered")

# Include public routes if available
if PUBLIC_ROUTES_AVAILABLE:
    app.include_router(public_router)
    logger.info("✅ Public routes registered")

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
    result = {"status": "healthy", "database_url_set": bool(os.getenv('DATABASE_URL'))}
    
    if PRODUCER_AVAILABLE:
        try:
            producer = get_cloud_producer()
            if producer:
                status = producer.get_status()
                result["producer"] = status
                result["firebase"] = {
                    "enabled": status.get("firebase_enabled", False),
                    "write_errors": status.get("firebase_write_errors", 0)
                }
        except Exception as e:
            result["producer_error"] = str(e)
    else:
        result["producer"] = "not_loaded"
    
    return result


@app.get("/status")
async def status():
    """Detailed status endpoint for monitoring."""
    if not PRODUCER_AVAILABLE:
        return {"status": "producer_not_available", "admin_routes": ADMIN_ROUTES_AVAILABLE}
    
    try:
        producer = get_cloud_producer()
        if producer:
            return producer.get_status()
        return {"error": "Producer not initialized"}
    except Exception as e:
        return {"error": str(e)}



# Cloud Run will call this on PORT environment variable
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
