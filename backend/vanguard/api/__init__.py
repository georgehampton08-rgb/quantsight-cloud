"""Vanguard API routes."""

from .health import router as health_router
from .admin_routes import router as admin_router
from .cron_routes import router as cron_router

__all__ = ["health_router", "admin_router", "cron_router"]
