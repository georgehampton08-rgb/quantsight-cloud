"""
Vanguard Context Management
============================
ContextVar for request ID propagation across async boundaries.
"""

from contextvars import ContextVar
from typing import Optional


# ContextVar for request_id (async-safe, thread-safe)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in context."""
    request_id_var.set(request_id)
