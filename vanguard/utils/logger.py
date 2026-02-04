"""
Structured Logging Configuration
=================================
Structlog setup for JSON output with request_id injection.
"""

import logging
import sys
from typing import Any, Dict
import structlog
from structlog.types import EventDict, WrappedLogger

from ..core.context import get_request_id


def add_request_id(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add request_id from context to every log entry."""
    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog for Cloud Run compatibility.
    Outputs JSON to stdout with timestamp, severity, and request_id.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_request_id,  # Custom processor to inject request_id
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),  # JSON output for Cloud Run
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
