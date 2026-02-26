"""
WebSocket Message Handler — Phase 8 Step 8.2.4
=================================================
Dispatches incoming WebSocket messages to appropriate handlers.

Protocol:
  Client → Server messages MUST contain an "action" field:
    - subscribe:   { action: "subscribe", filters: { team: "LAL", ... } }
    - unsubscribe: { action: "unsubscribe" }
    - ping:        { action: "ping" }
    - annotate:    { action: "annotate", context_type, context_id, content }
    - react:       { action: "react", context_type, context_id, note_id, reaction }

  Server → Client messages contain a "type" field:
    - connected, subscribed, unsubscribed, pong, error
    - leaders_update, game_update, player_update
    - presence_update, annotation_added, reaction_added
"""

import logging
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Valid subscription filter keys
VALID_FILTER_KEYS = {"team", "player_id", "game_id"}

# Valid annotation context types
VALID_CONTEXT_TYPES = {"player", "incident", "game"}


async def handle_ws_message(
    connection_id: str,
    session_token: str,
    message: dict,
    websocket: WebSocket,
):
    """
    Route incoming WebSocket message to the appropriate handler.
    Never raises — errors are sent back to the client as error messages.
    """
    from services.ws_connection_manager import get_ws_manager
    from services.presence_manager import get_presence_manager

    manager = get_ws_manager()
    presence = get_presence_manager()
    action = message.get("action")

    try:
        if action == "subscribe":
            filters = message.get("filters", {})
            # Validate filter keys — only allow known keys
            valid_filters = {
                k: v for k, v in filters.items()
                if k in VALID_FILTER_KEYS
            }
            await manager.update_filters(connection_id, valid_filters)
            await presence.update_context(session_token, valid_filters)
            await websocket.send_json({
                "type": "subscribed",
                "filters": valid_filters,
            })
            logger.info(
                "ws_subscribed",
                extra={
                    "connection_id": connection_id,
                    "filters": valid_filters,
                },
            )

        elif action == "unsubscribe":
            await manager.update_filters(connection_id, {})
            await presence.update_context(session_token, {})
            await websocket.send_json({
                "type": "unsubscribed",
            })

        elif action == "ping":
            await manager.update_last_ping(connection_id)
            await websocket.send_json({
                "type": "pong",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        elif action == "annotate":
            await _handle_annotation(
                connection_id, session_token, message, websocket,
            )

        elif action == "react":
            await _handle_reaction(
                connection_id, session_token, message, websocket,
            )

        else:
            await websocket.send_json({
                "type": "error",
                "code": "unknown_action",
                "message": f"Unknown action: {action}",
            })

    except Exception as e:
        logger.warning(
            "ws_message_handler_error",
            extra={
                "connection_id": connection_id,
                "action": action,
                "error": str(e),
            },
        )
        try:
            await websocket.send_json({
                "type": "error",
                "code": "handler_error",
                "message": str(e),
            })
        except Exception:
            pass  # connection may already be dead


async def _handle_annotation(
    connection_id: str,
    session_token: str,
    message: dict,
    websocket: WebSocket,
):
    """Handle annotation creation via WebSocket."""
    from services.annotation_service import get_annotation_service
    from services.ws_connection_manager import get_ws_manager

    manager = get_ws_manager()
    annotation_service = get_annotation_service()

    context_type = message.get("context_type")
    context_id = message.get("context_id")
    content = message.get("content", "")

    if context_type not in VALID_CONTEXT_TYPES:
        await websocket.send_json({
            "type": "error",
            "code": "invalid_context",
            "message": f"context_type must be one of {VALID_CONTEXT_TYPES}",
        })
        return

    if not context_id:
        await websocket.send_json({
            "type": "error",
            "code": "missing_context_id",
            "message": "context_id is required",
        })
        return

    try:
        note = await annotation_service.add_annotation(
            context_type=context_type,
            context_id=context_id,
            session_token=session_token,
            content=content,
        )

        # Determine broadcast filter based on context type
        if context_type == "player":
            broadcast_filter_key = "player_id"
        elif context_type == "game":
            broadcast_filter_key = "game_id"
        else:
            broadcast_filter_key = None

        # Broadcast to all subscribers of the same context
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

    except ValueError as e:
        await websocket.send_json({
            "type": "error",
            "code": "annotation_error",
            "message": str(e),
        })


async def _handle_reaction(
    connection_id: str,
    session_token: str,
    message: dict,
    websocket: WebSocket,
):
    """Handle reaction addition via WebSocket."""
    from services.annotation_service import get_annotation_service
    from services.ws_connection_manager import get_ws_manager

    manager = get_ws_manager()
    annotation_service = get_annotation_service()

    context_type = message.get("context_type")
    context_id = message.get("context_id")
    note_id = message.get("note_id")
    reaction = message.get("reaction")

    if not all([context_type, context_id, note_id, reaction]):
        await websocket.send_json({
            "type": "error",
            "code": "missing_fields",
            "message": "context_type, context_id, note_id, and reaction are required",
        })
        return

    try:
        await annotation_service.add_reaction(
            context_type=context_type,
            context_id=context_id,
            note_id=note_id,
            reaction=reaction,
        )

        # Broadcast reaction to subscribers
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

    except ValueError as e:
        await websocket.send_json({
            "type": "error",
            "code": "reaction_error",
            "message": str(e),
        })
