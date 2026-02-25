"""
Live Stream Router — SSE Bridge
=================================
Provides the /live/stream endpoint that the frontend connects to via EventSource.

Architecture:
  CloudAsyncPulseProducer → Firestore  (existing)
                          → _latest_snapshot (new in-memory field)
                             ↓
  /live/stream → reads snapshot every 5s → EventSource client

Cloud Run notes:
  • X-Accel-Buffering: no  → prevents load balancer from buffering the stream
  • heartbeat comment every <25s → keeps TCP connection alive (60s idle timeout)
  • Each SSE client holds exactly one long-lived HTTP/1.1 connection
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Push a new frame every N seconds.  Producer polls NBA API every 10s, so 5s
# gives clients 2 frames per poll cycle — responsive without thrashing.
_STREAM_INTERVAL = 5.0

# Send a heartbeat comment if we have nothing new to push.
# This MUST be ≤ 25s so the Cloud Run 60s idle-connection timer never fires.
_HEARTBEAT_INTERVAL = 20.0


async def _event_generator():
    """
    Async generator that yields SSE frames.

    Format used by the frontend EventSource listener:
        data: <JSON payload>\n\n        ← data event (message)
        : heartbeat\n\n              ← SSE comment (keep-alive, invisible to JS)
    """
    last_heartbeat = asyncio.get_event_loop().time()

    while True:
        try:
            # — Pull snapshot from the running producer ——————————————————————
            try:
                from services.async_pulse_producer_cloud import get_cloud_producer
                producer = get_cloud_producer()
                snapshot = producer.get_latest_snapshot() if producer else None
            except Exception as e:
                logger.debug(f"SSE: producer lookup failed: {e}")
                snapshot = None

            now = asyncio.get_event_loop().time()

            if snapshot is not None:
                # Stamp frame time so clients can detect stale data
                snapshot.setdefault("meta", {})["streamed_at"] = (
                    datetime.utcnow().isoformat() + "Z"
                )
                payload = json.dumps(snapshot, default=str)
                yield f"data: {payload}\n\n"
                last_heartbeat = now
            else:
                # No game data yet (pre-season, off-day, or producer still
                # warming up) — send an empty-state frame so the frontend
                # can display "No active telemetry" instead of a spinner.
                if now - last_heartbeat >= _HEARTBEAT_INTERVAL:
                    empty = {
                        "games": [],
                        "leaders": [],
                        "meta": {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "game_count": 0,
                            "live_count": 0,
                            "update_cycle": 0,
                            "state": "no_active_games",
                        },
                        "changes": {},
                    }
                    yield f"data: {json.dumps(empty)}\n\n"
                    last_heartbeat = now
                else:
                    # Cheap keep-alive comment — JS EventSource ignores it
                    yield ": heartbeat\n\n"

        except asyncio.CancelledError:
            logger.info("SSE: client disconnected, generator cancelled")
            return
        except GeneratorExit:
            return
        except Exception as e:
            logger.warning(f"SSE: frame error: {e}")
            yield f": error {type(e).__name__}\n\n"

        await asyncio.sleep(_STREAM_INTERVAL)


@router.get("/live/stream")
async def live_stream():
    """
    Server-Sent Events endpoint consumed by the frontend Pulse page.

    The frontend opens a persistent EventSource connection here.
    Every 5 seconds the latest game snapshot is pushed as a 'data' event.
    Heartbeat comments keep the connection alive through Cloud Run's
    60-second idle-connection timeout.
    """
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Tells Cloud Run / nginx NOT to buffer — critical for SSE
            "X-Accel-Buffering": "no",
            # Wide-open CORS so Firebase Hosting can connect to Cloud Run
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/live/status")
async def live_status():
    """
    Quick status check — is the SSE producer running and do we have a snapshot?
    Frontend can call this without opening a stream.
    """
    try:
        from services.async_pulse_producer_cloud import get_cloud_producer
        producer = get_cloud_producer()
        if producer:
            return producer.get_status()
        return {"status": "producer_not_started", "snapshot_available": False}
    except Exception as e:
        return {"status": "error", "error": str(e), "snapshot_available": False}
