"""
Vanguard Lifespan Management
=============================
FastAPI lifespan hook for Vanguard initialization and shutdown.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastapi import FastAPI

from ..core.config import get_vanguard_config
from ..utils.logger import get_logger, configure_logging
from .redis_client import get_redis, close_redis, ping_redis

logger = get_logger(__name__)


@asynccontextmanager
async def vanguard_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Vanguard lifecycle manager.
    Ensures Vanguard starts FIRST and stops LAST.
    
    Startup:
      1. Configure structured logging
      2. Load configuration
      3. Initialize Redis connection
      4. Health check
    
    Shutdown:
      5. Close Redis connections
    """
    # ===== STARTUP =====
    logger.info("vanguard_starting", version="3.1.0")
    
    try:
        # Step 1: Configure logging
        configure_logging()
        logger.info("vanguard_logging_configured")
        
        # Step 2: Load configuration
        config = get_vanguard_config()
        logger.info(
            "vanguard_config_loaded",
            mode=config.mode.value,
            enabled=config.enabled,
            llm_enabled=config.llm_enabled,
        )
        
        if not config.enabled:
            logger.warning("vanguard_disabled", message="VANGUARD_ENABLED=false, running in degraded mode")
            yield
            return
        
        # Step 3: Initialize Redis
        try:
            await get_redis()
            redis_healthy = await ping_redis()
            logger.info("vanguard_redis_initialized", healthy=redis_healthy)
        except Exception as e:
            logger.error("vanguard_redis_failed", error=str(e), fallback="standalone mode")
            # Continue without Redis (standalone mode)
        
        # Step 3.5: Initialize Firebase/Firestore (Shared Storage)
        if config.storage_mode == "FIRESTORE":
            try:
                import firebase_admin
                from firebase_admin import credentials
                if not firebase_admin._apps:
                    try:
                        # Try Application Default Credentials (Cloud Run)
                        cred = credentials.ApplicationDefault()
                        firebase_admin.initialize_app(cred)
                        logger.info("vanguard_firebase_initialized", mode="ApplicationDefault")
                    except Exception:
                        # Fallback for local/other environments
                        firebase_admin.initialize_app()
                        logger.info("vanguard_firebase_initialized", mode="default")
                else:
                    logger.debug("vanguard_firebase_already_initialized")
            except Exception as e:
                logger.error("vanguard_firebase_init_failed", error=str(e))
        
        # Step 4: Initialize all subsystems
        try:
            from ..profiler.llm_client import get_llm_client
            from ..surgeon.remediation import get_surgeon
            from ..inquisitor.sampler import get_sampler
            
            # Warm up LLM client
            llm_client = get_llm_client()
            logger.info("profiler_initialized", model=config.llm_model if config.llm_enabled else "disabled")
            
            # Initialize Surgeon
            surgeon = get_surgeon()
            logger.info("surgeon_initialized", mode=config.mode.value)
            
            # Initialize Sampler
            sampler = get_sampler()
            logger.info("inquisitor_initialized", sampling_rate=config.sampling_rate)
            
        except Exception as e:
            logger.error("subsystem_initialization_failed", error=str(e))
            # Continue - subsystems will lazy-load on first use
        
        logger.info("vanguard_operational", message="Digital Immune System ACTIVE")
    
    except Exception as e:
        logger.error("vanguard_startup_failed", error=str(e))
        # Don't crash the app - allow FastAPI to continue
    
    # ===== YIELD CONTROL TO FASTAPI =====
    yield
    
    # ===== SHUTDOWN =====
    logger.info("vanguard_shutting_down")
    
    try:
        await close_redis()
        logger.info("vanguard_shutdown_complete")
    except Exception as e:
        logger.error("vanguard_shutdown_error", error=str(e))
