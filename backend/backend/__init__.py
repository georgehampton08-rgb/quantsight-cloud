"""
╔══════════════════════════════════════════════════════════════════╗
║                   ⚠️  DEPRECATED — DO NOT USE  ⚠️               ║
║                                                                  ║
║  This module tree (backend/backend/) is the LEGACY Desktop       ║
║  Backend and is NOT the active Cloud production service.         ║
║                                                                  ║
║  The canonical, production backend is:                           ║
║    backend/main.py   (ASGI entrypoint)                           ║
║    backend/vanguard/  (Immune system)                             ║
║    backend/services/  (Business logic)                            ║
║    backend/routers/   (API routes)                                ║
║                                                                  ║
║  If you find yourself importing from backend.backend.*, you      ║
║  are hitting the Shadow Service Paradox and should redirect       ║
║  your import to the canonical backend/* modules.                 ║
║                                                                  ║
║  See: ARCHITECTURE_DECISIONS.md (Shadow Service Paradox)         ║
║  See: Knowledge Item — Vanguard Autonomous Operations            ║
╚══════════════════════════════════════════════════════════════════╝
"""

# DEPRECATED: This module tree exists only for backward compatibility
# with the Desktop Dashboard application. DO NOT import from this
# module in Cloud Run services.

import warnings
warnings.warn(
    "Importing from backend.backend is DEPRECATED. "
    "Use backend.* (the canonical cloud backend) instead. "
    "See ARCHITECTURE_DECISIONS.md for details.",
    DeprecationWarning,
    stacklevel=2,
)
