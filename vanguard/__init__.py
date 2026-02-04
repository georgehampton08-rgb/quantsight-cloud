"""
Vanguard Sovereign - Digital Immune System for FastAPI
========================================================
Self-healing autonomous investigation and remediation platform.

Version: 3.1
Architecture: Sidecar (embedded within application)
"""

__version__ = "3.1.0"
__author__ = "QuantSight AI Team"

from .core.config import VanguardConfig

__all__ = ["VanguardConfig"]
