"""
Two-Layer Admin Auth Guard
==========================
Layer 1 — verify_firebase_token: validates the Firebase JWT
Layer 2 — require_admin_role:    checks Firestore admins/{uid} for role='admin'

CRITICAL:
  • Creating a Firebase account grants ZERO access.
  • Admin role must be explicitly written by the owner to Firestore:
      db.collection("admins").document(UID).set({"role": "admin"})
  • Fail-closed: if Firestore check fails, access is DENIED, not granted.

Usage in any protected route:
    from api.auth_middleware import require_admin_role
    @router.post("/admin/...")
    async def my_route(admin: dict = Depends(require_admin_role)):
        ...
"""
import time
import logging
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger  = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=True)

# In-process cache: uid → (is_admin, monotonic_timestamp)
# Reset on process restart (safe — Cloud Run restarts are rare but expected)
_admin_cache: dict[str, tuple[bool, float]] = {}
_CACHE_TTL = 300.0  # 5 minutes — recheck Firestore after this window


async def verify_firebase_token(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """
    Layer 1: Verify Firebase ID token.
    Returns decoded JWT claims dict on success.
    Raises HTTP 401 on failure.
    """
    try:
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(creds.credentials)
        return decoded
    except Exception as exc:
        logger.warning(f"[AUTH] Token verification failed: {exc}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin_role(
    decoded: dict = Security(verify_firebase_token),
) -> dict:
    """
    Layer 2: Verify the authenticated user is in the Firestore admins allowlist
    with role='admin'. A valid token alone is NOT sufficient.

    Sanitization checks (all run before Firestore):
      - uid must pass safe_id validation (alphanumeric, no path traversal)
      - email must be present in claims
      - email_verified must be True (rejects unverified accounts)

    Fail-closed: if Firestore is unavailable, access is DENIED (503).
    """
    uid = decoded.get("uid", "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="Token is missing uid claim")

    # Sanitize uid — prevents Firestore path traversal / injection
    try:
        from api.validators import safe_id
        uid = safe_id(uid, "uid")
    except Exception:
        raise HTTPException(status_code=401, detail="Malformed uid in token")

    # Require email present
    email = decoded.get("email", "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=401, detail="Token is missing valid email claim")

    # Require email verified (Google always verifies, but be explicit)
    if not decoded.get("email_verified", False):
        logger.warning(f"[AUTH] Unverified email blocked: uid={uid} email={email}")
        raise HTTPException(
            status_code=403,
            detail="Email address must be verified before accessing admin features."
        )

    now = time.monotonic()

    # Check in-process cache first (avoids Firestore round-trip on every request)
    cached = _admin_cache.get(uid)
    if cached:
        is_admin, cached_at = cached
        if now - cached_at < _CACHE_TTL:
            if not is_admin:
                raise HTTPException(status_code=403, detail=_access_denied(decoded))
            return decoded
        # Cache stale — fall through to fresh Firestore check

    # Fresh Firestore role check
    try:
        from firebase_admin import firestore
        doc = firestore.client().collection("admins").document(uid).get()
        is_admin: bool = doc.exists and doc.to_dict().get("role") == "admin"
    except Exception as exc:
        logger.error(f"[AUTH] Firestore admin check failed uid={uid}: {exc}")
        # Fail CLOSED — deny if we cannot verify. Never fail open.
        raise HTTPException(
            status_code=503,
            detail="Authorization service temporarily unavailable. Try again in a moment."
        )

    # Update cache
    _admin_cache[uid] = (is_admin, now)

    if not is_admin:
        logger.warning(
            f"[AUTH] Access denied: uid={uid} email={email} "
            f"— not present in admins collection"
        )
        raise HTTPException(status_code=403, detail=_access_denied(decoded))

    logger.info(f"[AUTH] Admin access granted: uid={uid} email={email}")
    return decoded


def invalidate_admin_cache(uid: str) -> None:
    """Force a fresh Firestore check on next request for this uid.
    Call after manually revoking admin role."""
    _admin_cache.pop(uid, None)


def _access_denied(decoded: dict) -> str:
    return (
        f"Access denied for '{decoded.get('email', 'unknown')}'. "
        "Your account exists but has not been granted admin access. "
        "Contact the system owner."
    )
