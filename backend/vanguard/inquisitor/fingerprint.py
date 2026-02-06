"""
Error Fingerprinting
====================
SHA256 hashing for error deduplication.
"""

import hashlib


def generate_error_fingerprint(
    exception_type: str,
    traceback_lines: list[str],
    endpoint: str
) -> str:
    """
    Generate a unique fingerprint for an error.
    
    Args:
        exception_type: e.g., "IntegrityError"
        traceback_lines: First 10 lines of traceback
        endpoint: API endpoint where error occurred
    
    Returns:
        SHA256 hash (hex string)
    """
    # Combine error components
    components = [
        exception_type,
        endpoint,
        *traceback_lines[:10],  # First 10 lines only
    ]
    
    # Create hash input
    hash_input = "\n".join(components).encode("utf-8")
    
    # Generate SHA256 fingerprint
    fingerprint = hashlib.sha256(hash_input).hexdigest()
    
    return fingerprint
