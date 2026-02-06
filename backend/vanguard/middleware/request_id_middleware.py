"""
Request ID Middleware
======================
Generates or extracts X-Request-ID header for every request.
Stores in ContextVar for propagation across async calls.
"""

from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..core.context import set_request_id
from ..utils.request_id import generate_request_id
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
   Middleware to generate/extract request ID and inject into response headers.
    
    Order: This should be added LAST to FastAPI so it executes FIRST.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = generate_request_id()
        
        # Store in ContextVar (accessible to all downstream code)
        set_request_id(request_id)
        
        # Process request
        response = await call_next(request)
        
        # Inject request ID into response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
