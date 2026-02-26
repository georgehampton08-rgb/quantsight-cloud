"""
WebSocket Upgrade Path — Phase 6 Step 6.7 (STUB)
===================================================
Placeholder for WebSocket upgrade path alongside SSE.

STATUS: DISABLED by default (FEATURE_WEBSOCKET_ENABLED=false)
REASON: Phase 6.1 Discovery found NO bidirectional latency requirement.
        All current clients use unidirectional SSE or Firestore listeners.

When enabled, this provides a /ws/pulse WebSocket endpoint that
streams the same live data as /live/stream SSE endpoint.

This stub registers the route but immediately returns 503 if the
feature flag is disabled, preventing accidental activation.
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def _ws_enabled() -> bool:
    """Check if WebSocket is enabled via feature flag."""
    try:
        from vanguard.core.feature_flags import flag
        return flag("FEATURE_WEBSOCKET_ENABLED")
    except Exception:
        return False


@router.websocket("/ws/pulse")
async def websocket_pulse(websocket: WebSocket):
    """
    WebSocket endpoint for live pulse data.

    STUB: Returns 1008 (Policy Violation) when FEATURE_WEBSOCKET_ENABLED=false.
    """
    if not _ws_enabled():
        await websocket.close(code=1008, reason="WebSocket not enabled. Use /live/stream SSE instead.")
        return

    # When enabled: accept and stream live data
    await websocket.accept()
    logger.info("WebSocket client connected to /ws/pulse")

    try:
        while True:
            # Read latest snapshot from pulse producer
            try:
                from services.async_pulse_producer_cloud import get_cloud_producer
                producer = get_cloud_producer()
                if producer:
                    snapshot = producer.get_latest_snapshot()
                    if snapshot:
                        await websocket.send_json(snapshot)
            except Exception as e:
                logger.warning(f"WebSocket pulse send failed: {e}")

            # Pause between sends (match SSE interval)
            import asyncio
            await asyncio.sleep(10)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/pulse")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
