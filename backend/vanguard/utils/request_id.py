"""
Request ID Generation
======================
UUID generation for request tracking.
"""

import uuid


def generate_request_id() -> str:
    """Generate a unique request ID (UUID4)."""
    return str(uuid.uuid4())
