"""
Vanguard Standalone Entry Point — Phase 6 Step 6.6
=====================================================
Future Cloud Run service entrypoint for extracted Vanguard.

Currently: NOT deployed. The Vanguard package runs embedded in the
main API (main.py). This file is the extraction target — when
Vanguard is deployed as a standalone Cloud Run service, this becomes
its CMD.

Usage (future):
    docker build -f Dockerfile.vanguard -t vanguard-service .
    docker run -p 50051:50051 vanguard-service
"""
import asyncio
import logging
import os
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vanguard.standalone")


async def serve():
    """Run Vanguard as a standalone gRPC service."""
    # Initialize Firebase
    try:
        import firebase_admin
        from firebase_admin import credentials
        if not firebase_admin._apps:
            try:
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
            except Exception:
                firebase_admin.initialize_app()
        logger.info("Firebase initialized")
    except Exception as e:
        logger.error(f"Firebase init failed: {e}")

    # Initialize Redis
    try:
        from vanguard.bootstrap.redis_client import get_redis, ping_redis
        await get_redis()
        healthy = await ping_redis()
        logger.info(f"Redis: {'healthy' if healthy else 'unavailable'}")
    except Exception as e:
        logger.warning(f"Redis init failed: {e}")

    # Start gRPC server
    from vanguard.grpc_server import start_grpc_server, stop_grpc_server
    port = int(os.getenv("VANGUARD_GRPC_PORT", "50051"))
    server = await start_grpc_server(port=port)
    logger.info(f"Vanguard standalone gRPC server running on port {port}")

    # Handle shutdown gracefully
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        await stop_grpc_server()
        logger.info("Vanguard standalone shutdown complete")


if __name__ == "__main__":
    asyncio.run(serve())
