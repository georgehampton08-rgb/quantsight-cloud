"""
Firebase Game Service
======================
Handles canonical game records (games/{gameId}) and the thin
date-indexed calendar documents (calendar/{YYYY-MM-DD}/games/{gameId}).

Design decisions:
  - All writes use merge=True → fully idempotent, safe to re-run.
  - calendar docs are kept deliberately thin (no PBP, no box score) so
    list-view queries are fast and cheap on Firestore reads.
  - createdAt is set only on initial document creation via a Firestore
    sentinel check-before-set pattern.
  - All path strings come from firestore_collections, never hardcoded.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from firestore_db import get_firestore_db
from services.firestore_collections import (
    CALENDAR, CALENDAR_GAMES_SUB,
    GAMES,
)

logger = logging.getLogger(__name__)


class FirebaseGameService:
    """
    Service for canonical game records and the date-indexed calendar.

    All public methods are static — no instance state needed (Firestore
    client is a singleton managed by get_firestore_db()).
    """

    # ── Canonical game record ─────────────────────────────────────────────────

    @staticmethod
    def upsert_canonical_game(
        game_id: str,
        game_date: str,
        season: str,
        home_team: Dict[str, Any],
        away_team: Dict[str, Any],
        status: str,
        start_time: str,
    ) -> bool:
        """
        Create or update games/{gameId}.

        Fields written:
            gameId, gameDate, season, homeTeam, awayTeam,
            status, startTime, updatedAt
            createdAt (only on initial creation — preserved thereafter)

        Args:
            game_id:    ESPN/NBA game ID string.
            game_date:  'YYYY-MM-DD' string.
            season:     e.g. '2025-26'.
            home_team:  Dict with at least 'tricode' key.
            away_team:  Dict with at least 'tricode' key.
            status:     Current status string ('Scheduled', 'In Progress', 'Final', …).
            start_time: ISO-8601 start time string.

        Returns:
            True on success, False on error.
        """
        try:
            db = get_firestore_db()
            ref = db.collection(GAMES).document(str(game_id))

            now_iso = datetime.now(timezone.utc).isoformat()

            # Check if doc already exists to preserve createdAt
            existing = ref.get()
            created_at = (
                existing.to_dict().get("createdAt", now_iso)
                if existing.exists
                else now_iso
            )

            doc = {
                "gameId": str(game_id),
                "gameDate": game_date,
                "season": season,
                "homeTeam": home_team,
                "awayTeam": away_team,
                "status": status,
                "startTime": start_time,
                "createdAt": created_at,
                "updatedAt": now_iso,
            }
            ref.set(doc, merge=True)
            logger.debug(f"[GameService] Upserted canonical game {game_id}")
            return True

        except Exception as e:
            logger.error(f"[GameService] upsert_canonical_game failed for {game_id}: {e}")
            return False

    @staticmethod
    def get_canonical_game(game_id: str) -> Optional[Dict[str, Any]]:
        """
        Read games/{gameId}.

        Returns:
            Document dict, or None if not found.
        """
        try:
            db = get_firestore_db()
            doc = db.collection(GAMES).document(str(game_id)).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.error(f"[GameService] get_canonical_game failed for {game_id}: {e}")
            return None

    # ── Calendar index ─────────────────────────────────────────────────────────

    @staticmethod
    def upsert_calendar_index(
        game_id: str,
        game_date: str,
        status: str,
        home_team: str,
        away_team: str,
        start_time: str,
    ) -> bool:
        """
        Create or update a thin index doc at calendar/{game_date}/games/{game_id}.

        This is intentionally lean — only the fields needed to render a
        game-list calendar view. The full record lives at games/{gameId}.

        Args:
            game_id:    Game ID string.
            game_date:  'YYYY-MM-DD' string.
            status:     Current status string.
            home_team:  Team tricode string (e.g. 'LAL').
            away_team:  Team tricode string (e.g. 'BOS').
            start_time: ISO-8601 start time string.

        Returns:
            True on success, False on error.
        """
        try:
            db = get_firestore_db()
            ref = (
                db.collection(CALENDAR)
                .document(game_date)
                .collection(CALENDAR_GAMES_SUB)
                .document(str(game_id))
            )

            doc = {
                "gameId": str(game_id),
                "status": status,
                "homeTeam": home_team,
                "awayTeam": away_team,
                "startTime": start_time,
                "refPath": f"{GAMES}/{game_id}",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
            ref.set(doc, merge=True)
            logger.debug(
                f"[GameService] Upserted calendar index {game_date}/{game_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"[GameService] upsert_calendar_index failed for {game_id}: {e}"
            )
            return False

    @staticmethod
    def get_games_for_date(date_str: str) -> List[Dict[str, Any]]:
        """
        Return all game index docs for a given date.

        Reads calendar/{date_str}/games/ subcollection.

        Args:
            date_str: 'YYYY-MM-DD' string.

        Returns:
            List of thin game dicts (may be empty).
        """
        try:
            db = get_firestore_db()
            docs = (
                db.collection(CALENDAR)
                .document(date_str)
                .collection(CALENDAR_GAMES_SUB)
                .stream()
            )
            return [d.to_dict() for d in docs]
        except Exception as e:
            logger.error(
                f"[GameService] get_games_for_date failed for {date_str}: {e}"
            )
            return []

    # ── Status helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def update_game_status(game_id: str, game_date: str, status: str) -> bool:
        """
        Update status on both games/{gameId} and calendar/{date}/games/{gameId}.

        Called by the polling service when a game transitions state.

        Returns:
            True if both writes succeeded, False otherwise.
        """
        try:
            db = get_firestore_db()
            now = datetime.now(timezone.utc).isoformat()

            canonical_ref = db.collection(GAMES).document(str(game_id))
            canonical_ref.set({"status": status, "updatedAt": now}, merge=True)

            calendar_ref = (
                db.collection(CALENDAR)
                .document(game_date)
                .collection(CALENDAR_GAMES_SUB)
                .document(str(game_id))
            )
            calendar_ref.set({"status": status, "updatedAt": now}, merge=True)

            return True
        except Exception as e:
            logger.error(f"[GameService] update_game_status failed for {game_id}: {e}")
            return False
