"""
WebSocket Routes — Phase 8 Step 8.2.3
========================================
Full-duplex WebSocket endpoint for real-time pulse data.

Replaces the Phase 6 stub. Provides:
  - /live/ws WebSocket endpoint with subscription filtering
  - /live/presence/{context_type}/{context_id} HTTP presence endpoint
  - /annotations/{context_type}/{context_id} HTTP annotation endpoints

Connection lifecycle:
  1. Client connects to /live/ws?session_token=<uuid>
  2. Server sends "connected" acknowledgment
  3. Client sends { action: "subscribe", filters: {...} }
  4. Server broadcasts matching events to client
  5. Client can annotate, react, ping
  6. On disconnect: presence cleaned up, connection removed

Feature flag: FEATURE_WEBSOCKET_ENABLED gates activation.
When disabled, connections receive close code 1013 (Try Again Later).
"""

import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def _ws_enabled() -> bool:
    """Check if WebSocket is enabled via feature flag."""
    try:
        from vanguard.core.feature_flags import flag
        return flag("FEATURE_WEBSOCKET_ENABLED")
    except Exception:
        return False


def _is_load_shedding() -> bool:
    """Check if load shedding is active (memory pressure)."""
    try:
        from vanguard.snapshot import SYSTEM_SNAPSHOT
        return SYSTEM_SNAPSHOT.get("shedding_active", False)
    except Exception:
        return False


# ── WebSocket Endpoint ───────────────────────────────────────────────────────

@router.websocket("/live/ws")
async def websocket_live(websocket: WebSocket):
    """
    Full-duplex WebSocket endpoint for real-time pulse data.

    Query params:
      - session_token: anonymous session UUID (optional, auto-generated if missing)

    Close codes:
      - 1013: Feature disabled
      - 1008: Connection limit reached or memory pressure
      - 1001: Ping timeout
      - 1011: Internal error
    """
    from services.ws_connection_manager import get_ws_manager
    from services.presence_manager import get_presence_manager
    from services.ws_message_handler import handle_ws_message

    # Gate on feature flag
    if not _ws_enabled():
        await websocket.close(
            code=1013,
            reason="WebSocket not enabled. Use /live/stream SSE instead.",
        )
        return

    # Gate on memory pressure
    if _is_load_shedding():
        await websocket.close(
            code=1008,
            reason="Memory pressure — new connections temporarily unavailable.",
        )
        return

    manager = get_ws_manager()
    presence = get_presence_manager()

    connection_id = str(_uuid.uuid4())
    session_token = (
        websocket.query_params.get("session_token")
        or str(_uuid.uuid4())
    )

    # Accept the WebSocket connection
    await websocket.accept()

    # Register with connection manager
    connected = await manager.connect(
        connection_id, websocket, session_token,
    )

    if not connected:
        await websocket.close(
            code=1008,
            reason="Connection limit reached. Retry after 30s.",
        )
        return

    # Register presence (empty context initially)
    await presence.join(session_token, connection_id, context={})

    try:
        # Send connection acknowledgment
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "session_token": session_token,
            "server_time": datetime.now(timezone.utc).isoformat(),
        })

        # Message loop — process incoming messages
        async for raw in websocket.iter_json():
            if isinstance(raw, dict):
                await handle_ws_message(
                    connection_id,
                    session_token,
                    raw,
                    websocket,
                )

    except WebSocketDisconnect:
        logger.info(
            "ws_client_disconnected",
            extra={"connection_id": connection_id},
        )
    except Exception as e:
        logger.warning(
            "ws_connection_error",
            extra={"connection_id": connection_id, "error": str(e)},
        )
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
    finally:
        await manager.disconnect(connection_id)
        await presence.leave(session_token, connection_id)


# ── HTTP Presence Endpoint ───────────────────────────────────────────────────

@router.get("/live/presence/{context_type}/{context_id}")
async def get_presence(context_type: str, context_id: str):
    """
    Get viewer count for a specific context.
    For non-WebSocket clients (initial page load, API consumers).
    """
    from services.presence_manager import get_presence_manager

    presence = get_presence_manager()
    viewers = await presence.get_viewers(context_type, context_id)

    return {
        "viewers": viewers,
        "context_type": context_type,
        "context_id": context_id,
    }


# ── HTTP Annotation Endpoints ───────────────────────────────────────────────

@router.get("/annotations/{context_type}/{context_id}")
async def get_annotations(context_type: str, context_id: str, limit: int = 50):
    """
    Get annotations for a context.
    Returns last N annotations, ordered by created_at desc.
    """
    from services.annotation_service import get_annotation_service, VALID_CONTEXT_TYPES

    if context_type not in VALID_CONTEXT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"context_type must be one of {VALID_CONTEXT_TYPES}",
        )

    service = get_annotation_service()
    notes = await service.get_annotations(context_type, context_id, limit=min(limit, 50))

    return {
        "notes": notes,
        "context_type": context_type,
        "context_id": context_id,
        "count": len(notes),
    }


@router.post("/annotations/{context_type}/{context_id}")
async def create_annotation(
    context_type: str,
    context_id: str,
    body: dict,
):
    """
    Create an annotation via HTTP.
    Body: { "content": "...", "session_token": "..." }
    Broadcasts to WebSocket subscribers.
    """
    from services.annotation_service import get_annotation_service, VALID_CONTEXT_TYPES
    from services.ws_connection_manager import get_ws_manager

    if context_type not in VALID_CONTEXT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"context_type must be one of {VALID_CONTEXT_TYPES}",
        )

    content = body.get("content", "")
    session_token = body.get("session_token", str(_uuid.uuid4()))

    service = get_annotation_service()

    try:
        note = await service.add_annotation(
            context_type=context_type,
            context_id=context_id,
            session_token=session_token,
            content=content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Broadcast to WebSocket subscribers
    manager = get_ws_manager()
    if context_type == "player":
        broadcast_filter_key = "player_id"
    elif context_type == "game":
        broadcast_filter_key = "game_id"
    else:
        broadcast_filter_key = None

    await manager.broadcast_to_subscribers(
        event_type="annotation_added",
        data={
            "note": note,
            "context_type": context_type,
            "context_id": context_id,
        },
        filter_key=broadcast_filter_key,
        filter_value=context_id,
    )

    return JSONResponse(status_code=201, content=note)


@router.post("/annotations/{context_type}/{context_id}/{note_id}/react")
async def add_reaction(
    context_type: str,
    context_id: str,
    note_id: str,
    body: dict,
):
    """
    Add a reaction to a note.
    Body: { "reaction": "👍" }  (allowed: 👍, 🔥, ⚠️)
    """
    from services.annotation_service import get_annotation_service
    from services.ws_connection_manager import get_ws_manager

    reaction = body.get("reaction", "")

    service = get_annotation_service()

    try:
        await service.add_reaction(
            context_type=context_type,
            context_id=context_id,
            note_id=note_id,
            reaction=reaction,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Broadcast reaction
    manager = get_ws_manager()
    if context_type == "player":
        broadcast_filter_key = "player_id"
    elif context_type == "game":
        broadcast_filter_key = "game_id"
    else:
        broadcast_filter_key = None

    await manager.broadcast_to_subscribers(
        event_type="reaction_added",
        data={
            "context_type": context_type,
            "context_id": context_id,
            "note_id": note_id,
            "reaction": reaction,
        },
        filter_key=broadcast_filter_key,
        filter_value=context_id,
    )

    return {"status": "ok", "reaction": reaction, "note_id": note_id}
