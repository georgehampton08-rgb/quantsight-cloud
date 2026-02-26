import asyncio
import logging
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class DegradedInjectorMiddleware(BaseHTTPMiddleware):
    """
    Reads the in-memory Oracle snapshot and injects an `X-System-Status: degraded`
    header into the response if Vanguard or other non-critical subsystems are down.
    This prevents downstream UI from assuming full observability functionality.
    """

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        try:
            from vanguard.snapshot import SYSTEM_SNAPSHOT
            
            # If Vanguard is not OK, or Gemini is not OK, we are degraded
            is_degraded = (
                not SYSTEM_SNAPSHOT.get("vanguard_ok", True) or 
                not SYSTEM_SNAPSHOT.get("gemini_ok", True)
            )

            if is_degraded:
                response.headers["X-System-Status"] = "degraded"
                
        except ImportError:
            # Snapshot module not found or unavailable
            pass
        except Exception as e:
            logger.debug(f"Failed to resolve Oracle snapshot for header injection: {e}")

        return response
