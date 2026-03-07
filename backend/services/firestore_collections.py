"""
Firestore Collections Registry
================================
Single source of truth for every Firestore collection and subcollection
path string used by the QuantSight backend.

Import this module instead of using magic strings anywhere.

Usage:
    from services.firestore_collections import GAMES, LIVE_GAMES, pad_sequence
"""

# ── Canonical game records ────────────────────────────────────────────────────
GAMES = "games"                  # games/{gameId}

# ── Date-based calendar index ─────────────────────────────────────────────────
CALENDAR = "calendar"            # calendar/{YYYY-MM-DD}/games/{gameId}
CALENDAR_GAMES_SUB = "games"     # subcollection name under calendar/{date}

# ── Live state cache (hot doc, updated at controlled cadence) ─────────────────
LIVE_GAMES = "live_games"        # live_games/{gameId}

# ── Play-by-play event stream (append-only, ordered by doc ID) ───────────────
PBP_EVENTS = "pbp_events"        # pbp_events/{gameId}/events/{sequenceNumber}
PBP_EVENTS_SUB = "events"        # subcollection name

# ── Shot chart attempts (lean docs, shot-plays only) ─────────────────────────
SHOTS = "shots"                  # shots/{gameId}/attempts/{sequenceNumber}
SHOTS_ATTEMPTS_SUB = "attempts"  # subcollection name

# ── Per-player cross-game shot history ────────────────────────────────────────
PLAYER_SHOTS = "player_shots"    # player_shots/{playerId}/shots/{gameId}_{seq}
PLAYER_SHOTS_SUB = "shots"       # subcollection name under player_shots/{playerId}

# ── Final freeze snapshot (persisted once at game end) ───────────────────────
FINAL_GAMES = "final_games"      # final_games/{gameId}

# ── Legacy paths (READ-ONLY during transition, do not write new data here) ───
LEGACY_LIVE_PLAYS_SUB = "plays"  # live_games/{gameId}/plays/{playId}  ← OLD
LEGACY_GAME_CACHE = "game_cache" # game_cache/{gameId}                 ← OLD


# ── Helpers ───────────────────────────────────────────────────────────────────

def pad_sequence(seq: int, width: int = 6) -> str:
    """
    Zero-pad a sequence number so Firestore lexicographic sort equals numeric sort.

    Firestore document IDs are sorted as strings. Without padding:
        "9" > "10" > "100" (wrong)

    With 6-digit padding:
        "000009" < "000010" < "000100" (correct)

    Args:
        seq:   Integer sequence number (>= 0).
        width: Total digit width, default 6 (supports up to 999,999 plays per game).

    Returns:
        Zero-padded string, e.g. pad_sequence(42) -> "000042"

    Raises:
        ValueError: If seq is negative or exceeds the representable range.
    """
    if seq < 0:
        raise ValueError(f"Sequence number must be non-negative, got {seq}")
    padded = str(seq).zfill(width)
    if len(padded) > width:
        raise ValueError(
            f"Sequence number {seq} exceeds {width}-digit width "
            f"(max {10**width - 1}). Increase width parameter."
        )
    return padded
