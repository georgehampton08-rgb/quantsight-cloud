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
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

# Configure logging for Cloud Run (MUST BE FIRST)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Suppress uvloop/asyncio SSL transport noise.
# Cloud Run's load balancer frequently closes TCP connections mid-stream
# (health probes, keep-alive resets), causing uvloop's SSL protocol to
# emit RuntimeError tracebacks that are infrastructure noise, not bugs.
# Setting these to ERROR (above WARNING) silences them without masking
# real application-level errors.
# -----------------------------------------------------------------------
logging.getLogger("uvloop").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.WARNING)
# h11 and httpcore also emit benign connection-reset warnings
logging.getLogger("h11").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Vanguard Sovereign Imports - Enhanced Debugging
import os
logger.info(f"🔍 Current working directory: {os.getcwd()}")
logger.info(f"🔍 Directory contents: {os.listdir('.')[:15]}...")
if os.path.exists('vanguard'):
    logger.info(f"📁 vanguard/ directory exists: {os.listdir('vanguard')}")
else:
    logger.error("❌ vanguard/ directory NOT FOUND in container!")

try:
    from vanguard.bootstrap import vanguard_lifespan
    from vanguard.middleware import RequestIDMiddleware, IdempotencyMiddleware, DegradedInjectorMiddleware
    from vanguard.inquisitor import VanguardTelemetryMiddleware
    VANGUARD_AVAILABLE = True
    logger.info("✅ Vanguard modules loaded successfully")
except ImportError as e:
    import traceback
    logger.error(f"❌ Vanguard import FAILED: {e}")
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    VANGUARD_AVAILABLE = False


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
    logger.info("✅ Admin routes imported successfully")
except ImportError as e:
    import traceback
    logger.error(f"❌ Admin routes not available: {e}")
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    ADMIN_ROUTES_AVAILABLE = False

# Import public API routes
try:
    from api.public_routes import router as public_router
    PUBLIC_ROUTES_AVAILABLE = True
    logger.info("✅ Public routes imported successfully")
except ImportError as e:
    import traceback
    logger.error(f"❌ Public routes not available: {e}")
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    PUBLIC_ROUTES_AVAILABLE = False

# Nexus routes disabled (uses SQL - will convert later)
NEXUS_ROUTES_AVAILABLE = False
# Database diagnostics removed - using Firestore now
DIAGNOSTICS_AVAILABLE = False

# ── Live SSE stream router (/live/stream) ────────────────────────────────────
# The frontend Pulse page opens an EventSource to /live/stream.
# This router bridges the CloudAsyncPulseProducer in-memory snapshot to clients.
try:
    from api.live_stream_routes import router as live_stream_router
    LIVE_STREAM_AVAILABLE = True
    logger.info("✅ Live stream routes imported successfully")
except ImportError as e:
    logger.warning(f"⚠️ Live stream routes not available: {e}")
    LIVE_STREAM_AVAILABLE = False
except Exception as e:
    import traceback
    logger.error(f"❌ Live stream routes not available: {e}")
    logger.error(f"Full traceback:\n{traceback.format_exc()}")
    LIVE_STREAM_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan for startup/shutdown with Vanguard integration."""
    # Startup
    logger.info("🚀 Cloud Run starting up (Firestore)...")
    logger.info(f"   └─ PORT: {os.getenv('PORT', '8080')}")
    logger.info(f"   └─ FIREBASE_PROJECT_ID: {os.getenv('FIREBASE_PROJECT_ID', 'Not set')}")
    logger.info(f"   └─ Database: Firestore (NoSQL)")
    
    # Initialize Vanguard (runs FIRST)
    if VANGUARD_AVAILABLE:
        from vanguard.snapshot import start_snapshot_loop, stop_snapshot_loop
        start_snapshot_loop()
        
        async with vanguard_lifespan(app):
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
            stop_snapshot_loop()
    else:
        # Run without Vanguard
        if PRODUCER_AVAILABLE:
            try:
                await start_cloud_producer()
                logger.info("✅ Cloud pulse producer started")
            except Exception as e:
                logger.error(f"❌ Failed to start cloud producer: {e}")
        
        yield
        
        logger.info("🛑 Cloud Run shutting down...")
        if PRODUCER_AVAILABLE:
            await stop_cloud_producer()
            logger.info("✅ Cloud pulse producer stopped")


app = FastAPI(
    title="QuantSight Cloud API",
    description="NBA Analytics &amp; Prediction Platform",
    version="2.0.0",
    docs_url=None,  # Disable /docs in production
    redoc_url=None,  # Disable /redoc in production
    lifespan=lifespan
)

# Include admin routes if available
if ADMIN_ROUTES_AVAILABLE:
    app.include_router(admin_router)
    logger.info("✅ Admin routes registered")

# Include public routes if available (bare path: /teams, /players, etc.)
# NOTE: /public/* aliases are defined directly in public_routes.py
if PUBLIC_ROUTES_AVAILABLE:
    app.include_router(public_router)
    logger.info("✅ Public routes registered at / and /public/*")

# Include Live SSE stream router (/live/stream)
# MUST be registered with no prefix — frontend hardcodes /live/stream
if LIVE_STREAM_AVAILABLE:
    app.include_router(live_stream_router)
    logger.info("✅ Live stream router registered at /live/*")

# Include admin injury routes
try:
    from api.injury_admin import router as admin_injury_router
    app.include_router(admin_injury_router)
    logger.info("✅ Admin injury routes registered")
except ImportError as e:
    logger.warning(f"⚠️ Admin injury routes not available: {e}")

# Include Nexus service routes
try:
    from nexus import router as nexus_router
    app.include_router(nexus_router)
    logger.info("✅ Nexus service routes registered")
except ImportError as e:
    logger.warning(f"⚠️ Nexus service not available: {e}")

# Include game logs routes
try:
    from api.game_logs_routes import router as game_logs_router
    app.include_router(game_logs_router)
    logger.info("✅ Game logs routes registered")
except ImportError as e:
    logger.warning(f"⚠️ Game logs routes not available: {e}")

# Include H2H population routes
try:
    from api.h2h_population_routes import router as h2h_router
    app.include_router(h2h_router)
    logger.info("✅ H2H population routes registered")
except ImportError as e:
    logger.warning(f"⚠️ H2H population routes not available: {e}")

# Include Aegis router (AI Analysis / Simulations)
try:
    from app.routers.aegis import router as aegis_router
    app.include_router(aegis_router, prefix="/aegis", tags=["Aegis AI"])
    logger.info("✅ Aegis router registered at /aegis/*")
except ImportError as e:
    logger.warning(f"⚠️ Aegis router not available: {e}")

# Include Live Pulse status router
try:
    from app.routers.live_pulse import router as live_pulse_router
    app.include_router(live_pulse_router, prefix="/pulse", tags=["Live Pulse"])
    logger.info("✅ Live Pulse router registered at /pulse/*")
except ImportError as e:
    logger.warning(f"⚠️ Live Pulse router not available: {e}")


# Include Vanguard health endpoint (MUST BE BEFORE MIDDLEWARE)
if VANGUARD_AVAILABLE:
    try:
        from vanguard.api.health import router as health_router
        app.include_router(health_router)
        logger.info("✅ Vanguard health router registered at /vanguard/health")
    except ImportError as e:
        logger.warning(f"⚠️ Vanguard health router not available: {e}")
        # NOTE: Do NOT set VANGUARD_AVAILABLE=False here — health.py is non-critical
    except Exception as e:
        logger.warning(f"⚠️ Vanguard health router registration failed: {e}")

# Vanguard Admin API — always attempt independently (not gated on health router success)
try:
    from vanguard.api.admin_routes import router as admin_router
    app.include_router(admin_router)
    logger.info("✅ Vanguard admin routes registered at /vanguard/admin/*")
except ImportError as e:
    logger.warning(f"⚠️ Vanguard admin router not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ Vanguard admin router registration failed: {e}")

# Vanguard Cron API
try:
    from vanguard.api.cron_routes import router as cron_router
    app.include_router(cron_router)
    logger.info("✅ Vanguard cron routes registered at /vanguard/admin/cron/*")
except ImportError as e:
    logger.warning(f"⚠️ Vanguard cron router not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ Vanguard cron router registration failed: {e}")

# Vanguard Vaccine API
try:
    from vanguard.api.vaccine_routes import router as vaccine_router
    app.include_router(vaccine_router)
    logger.info("✅ Vanguard vaccine routes registered at /vanguard/admin/vaccine/*")
except ImportError as e:
    logger.warning(f"⚠️ Vanguard vaccine router not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ Vanguard vaccine router registration failed: {e}")

# Vanguard Surgeon API
try:
    from vanguard.api.surgeon_routes import router as surgeon_router
    app.include_router(surgeon_router)
    logger.info("✅ Vanguard surgeon routes registered at /vanguard/surgeon/*")
except ImportError as e:
    logger.warning(f"⚠️ Vanguard surgeon router not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ Vanguard surgeon router registration failed: {e}")

if not VANGUARD_AVAILABLE:
    logger.warning("⚠️ Vanguard core unavailable — only admin routes attempted via fallback")



# CORS configuration for web/mobile clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS for preflight
    allow_headers=["*"],
)

# Vanguard Request ID Middleware (added LAST so it executes FIRST)
if VANGUARD_AVAILABLE:
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(DegradedInjectorMiddleware)
    app.add_middleware(VanguardTelemetryMiddleware)
    logger.info("✅ Vanguard middleware registered (RequestID + Idempotency + DegradedInjector + Telemetry)")



@app.get("/")
async def root():
    """Root endpoint - redirect to health."""
    return {"service": "QuantSight Live Pulse (Cloud)", "status": "running"}


@app.get("/health")
async def health_check():
    """
    Enhanced health check with REAL component verification.
    
    - NBA API: Actually pings stats.nba.com
    - Gemini: Verifies API key configuration
    - Firestore: Tests database connectivity
    """
    try:
        from vanguard.health_monitor import get_health_monitor
        
        # Run all health checks
        monitor = get_health_monitor()
        health_results = await monitor.run_all_checks()
        
        # Determine overall status
        statuses = [r.get('status') for r in health_results.values()]
        if 'critical' in statuses:
            overall_status = 'degraded'
        elif 'warning' in statuses:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'
        
        result = {
            "status": overall_status,
            "nba_api": health_results.get('nba_api', {}).get('status', 'unknown'),
            "gemini": health_results.get('gemini_ai', {}).get('status', 'unknown'),
            "database": health_results.get('firestore', {}).get('status', 'unknown'),
            "details": health_results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add producer status if available
        if PRODUCER_AVAILABLE:
            try:
                producer = get_cloud_producer()
                if producer:
                    status_data = producer.get_status()
                    result["producer"] = status_data
            except Exception as e:
                result["producer_error"] = str(e)
        else:
            result["producer"] = "not_loaded"
        
        return result
        
    except Exception as e:
        # Fallback to basic checks if health monitor fails
        return {
            "status": "degraded",
            "error": f"Health monitor failed: {str(e)}",
            "database_url_set": bool(os.getenv('DATABASE_URL')),
            "database": {
                "enabled": bool(os.getenv('FIREBASE_PROJECT_ID')),
                "type": "firestore" if os.getenv('FIREBASE_PROJECT_ID') else "not-configured"
            },
            "gemini": {
                "enabled": bool(os.getenv('GEMINI_API_KEY')),
                "configured": os.getenv('GEMINI_API_KEY') is not None
            },
            "firebase": {
                "enabled": bool(os.getenv('FIREBASE_PROJECT_ID')),
                "project_id": os.getenv('FIREBASE_PROJECT_ID') or "not-configured"
            },
            "timestamp": datetime.utcnow().isoformat(),
            "producer": "not_loaded"
        }

@app.get("/readyz")
async def readyz():
    """Liveness/Readiness probe for Cloud Run. Gates hard dependencies (Firestore)."""
    try:
        from vanguard.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        check_task = monitor.check_firestore()
        result = await asyncio.wait_for(check_task, timeout=2.0)
        
        if result.get("status") == "critical":
            return Response(status_code=503, content=f"Service Unavailable: {result.get('error')}")
        return Response(status_code=200, content="OK")
    except Exception as e:
        return Response(status_code=503, content=f"Service Unavailable: {e}")

@app.get("/health/deps")
async def health_deps():
    """Deep health check that exposes Oracle snapshot without failing traffic routing."""
    try:
        from vanguard.snapshot import SYSTEM_SNAPSHOT
        return SYSTEM_SNAPSHOT
    except ImportError:
        return {"status": "Vanguard not available"}



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



# Static file handlers to prevent 404 noise
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return empty favicon to prevent 404 errors."""
    # 1x1 transparent PNG
    return Response(
        content=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
        media_type="image/png"
    )

@app.get("/manifest.json", include_in_schema=False)
async def manifest():
    """Return minimal web app manifest."""
    return {
        "name": "QuantSight",
        "short_name": "QS",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1a1a2e",
        "theme_color": "#16213e"
    }


# Cloud Run will call this on PORT environment variable
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
