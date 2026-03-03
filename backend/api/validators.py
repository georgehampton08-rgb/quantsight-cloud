"""
QuantSight Input Validators
============================
Central validation module for all user-supplied inputs.

Import pattern:
    from api.validators import safe_id, safe_collection, safe_date

HARD STOP RULE: If any validator is bypassed or weakened, stop and raise with the team.
"""
import re
from fastapi import HTTPException

# ─── Compiled patterns (module-level for performance) ──────────────────────────
SAFE_ID_RE          = re.compile(r'^[a-zA-Z0-9_\-]{1,128}$')
DATE_RE             = re.compile(r'^\d{4}-\d{2}-\d{2}$')
TEAM_ABBR_RE        = re.compile(r'^[A-Z]{2,4}$')

# ─── Allowlists ────────────────────────────────────────────────────────────────
ALLOWED_COLLECTIONS = frozenset({
    "teams", "players", "player_stats", "game_logs", "team_stats"
})
ALLOWED_STATUSES = frozenset({
    "OUT", "QUESTIONABLE", "PROBABLE", "GTD"
})
VANGUARD_MODES = frozenset({
    "SILENT_OBSERVER", "CIRCUIT_BREAKER", "FULL_SOVEREIGN"
})
NBA_TEAMS = frozenset({
    'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN',
    'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA',
    'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHX',
    'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS',
})
DANGEROUS_CHARS_RE = re.compile(r'[<>{};`\'"]')


# ─── Validators ────────────────────────────────────────────────────────────────

def safe_id(value: str, name: str = "id") -> str:
    """Validate a player/team/fingerprint/endpoint ID.
    Allows: alphanumeric, dash, underscore. Max 128 chars.
    """
    if not value or not SAFE_ID_RE.match(value):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {name}: only alphanumeric, dash, underscore allowed (max 128 chars). Got: '{value[:20]}'"
        )
    return value


def safe_date(value: str) -> str:
    """Validate a date string in YYYY-MM-DD format."""
    if not value or not DATE_RE.match(value):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date '{value}': must be YYYY-MM-DD format"
        )
    return value


def safe_collection(name: str) -> str:
    """Validate that a Firestore collection name is in the approved allowlist.
    Prevents path traversal and unauthorized collection access.
    """
    if name not in ALLOWED_COLLECTIONS:
        raise HTTPException(
            status_code=403,
            detail=f"Collection '{name}' is not accessible. Allowed: {sorted(ALLOWED_COLLECTIONS)}"
        )
    return name


def safe_vanguard_mode(mode: str) -> str:
    """Validate a Vanguard operational mode string."""
    normalized = mode.upper() if mode else ""
    if normalized not in VANGUARD_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid mode '{mode}'. Use one of: {sorted(VANGUARD_MODES)}"
        )
    return normalized


def safe_injury_status(status: str) -> str:
    """Validate an injury status string."""
    normalized = status.upper() if status else ""
    if normalized not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{status}'. Use one of: {sorted(ALLOWED_STATUSES)}"
        )
    return normalized


def safe_text(value: str, name: str = "field", max_len: int = 500) -> str:
    """Sanitize a free-text field. Strips dangerous characters and enforces length."""
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{name} must be a string")
    stripped = value.strip()
    if len(stripped) > max_len:
        raise HTTPException(
            status_code=422,
            detail=f"{name} exceeds {max_len} character limit ({len(stripped)} chars)"
        )
    if DANGEROUS_CHARS_RE.search(stripped):
        raise HTTPException(
            status_code=422,
            detail=f"{name} contains invalid characters (<>{{}}; backtick, quotes)"
        )
    return stripped


def safe_team_abbr(value: str) -> str:
    """Validate a 2-4 letter NBA team abbreviation against the official list."""
    normalized = value.upper() if value else ""
    if normalized not in NBA_TEAMS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid team abbreviation '{value}': must be a valid NBA team (e.g. LAL, GSW, BOS)"
        )
    return normalized


def safe_limit(value: int, min_val: int = 1, max_val: int = 2000) -> int:
    """Clamp a limit param within safe bounds."""
    if value < min_val or value > max_val:
        raise HTTPException(
            status_code=422,
            detail=f"limit must be between {min_val} and {max_val}"
        )
    return value
