"""
WebSocket Heartbeat — Phase 8 Step 8.5.1
==========================================
Background task that pings all WebSocket connections every 30s.
Disconnects non-responsive connections after 40s of silence.

Started as asyncio.create_task() during lifespan.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def heartbeat_loop():
    """
    Background task. Pings all connections every 30s.
    Disconnects non-responsive connections after 40s.
    """
    from services.ws_connection_manager import get_ws_manager

    logger.info("ws_heartbeat_loop_started")

    while True:
        try:
            await asyncio.sleep(30)

            manager = get_ws_manager()
            states = await manager.get_connection_states()

            if not states:
                continue

            now = datetime.now(timezone.utc)
            dead = []

            for conn_id, state in states:
                since_ping = (now - state.last_ping).total_seconds()

                if since_ping > 40:
                    # No pong received in 40s — connection is dead
                    dead.append((conn_id, state))
                else:
                    # Send server-side ping
                    try:
                        await state.websocket.send_json({
                            "type": "ping",
                            "timestamp": now.isoformat(),
                        })
                    except Exception:
                        dead.append((conn_id, state))

            # Prune dead connections
            for conn_id, state in dead:
                try:
                    await state.websocket.close(
                        code=1001,
                        reason="ping timeout",
                    )
                except Exception:
                    pass  # connection may already be closed
                await manager.disconnect(conn_id)

            if dead:
                logger.info(
                    "ws_heartbeat_pruned",
                    extra={
                        "pruned": len(dead),
                        "remaining": manager.active_count,
                    },
                )

        except asyncio.CancelledError:
            logger.info("ws_heartbeat_loop_cancelled")
            break
        except Exception as e:
            logger.error(f"ws_heartbeat_error: {e}")
            await asyncio.sleep(5)  # avoid tight loop on error
