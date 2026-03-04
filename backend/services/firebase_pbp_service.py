"""
Firebase PBP Service — Refactored (Phase 2)
============================================
Manages play-by-play event storage and shot chart extraction.

Schema changes from legacy:
  OLD: live_games/{gameId}/plays/{playId}     ← keyed by playId
  NEW: pbp_events/{gameId}/events/{seq}       ← keyed by zero-padded sequenceNumber

The sequenceNumber doc-ID approach gives us free lexicographic ordering
(Firestore sorts doc IDs as strings — zero-padding ensures numeric order matches).

Shot chart extraction:
  For any event with isShootingPlay == True, a lean "shot doc" is simultaneously
  written to shots/{gameId}/attempts/{seq}. This avoids a second query pass.

Legacy compatibility:
  - save_plays_batch()          → still writes to OLD path (preserved during transition)
  - get_cached_plays()          → still reads from OLD path
  - save_plays_batch_v2()       → writes to NEW pbp_events/ path
  - get_cached_plays_v2()       → reads from NEW path, falls back to OLD if empty
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from firestore_db import get_firestore_db
from services.nba_pbp_service import PlayEvent
from services.firestore_collections import (
    LIVE_GAMES, LEGACY_LIVE_PLAYS_SUB, LEGACY_GAME_CACHE,
    PBP_EVENTS, PBP_EVENTS_SUB,
    SHOTS, SHOTS_ATTEMPTS_SUB,
    FINAL_GAMES, GAMES, CALENDAR, CALENDAR_GAMES_SUB,
    pad_sequence,
)

logger = logging.getLogger(__name__)

# Batch size — conservatively 225 per sub-batch because each shot play
# generates TWO Firestore writes (pbp_events + shots).  225 * 2 = 450 < 500.
_BATCH_LIMIT = 225


class FirebasePBPService:

    # ── DB accessor ────────────────────────────────────────────────────────────

    @staticmethod
    def get_db():
        return get_firestore_db()

    # ═══════════════════════════════════════════════════════════════════════════
    # NEW (Phase 2) — pbp_events/ + shots/ paths
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def save_plays_batch_v2(game_id: str, plays: List[PlayEvent]) -> int:
        """
        Idempotent batch write to the NEW schema path.

        Writes each play to:
            pbp_events/{game_id}/events/{pad_sequence(sequenceNumber)}

        For shooting plays (isShootingPlay == True), also writes a lean doc to:
            shots/{game_id}/attempts/{pad_sequence(sequenceNumber)}

        Batch logic:
            Firestore limits batches to 500 ops.  Since a shot play produces
            2 writes, we cap sub-batches at 225 plays to stay safely under.

        Args:
            game_id: Game ID string.
            plays:   List of PlayEvent objects.

        Returns:
            Number of plays written.
        """
        if not plays:
            return 0

        db = FirebasePBPService.get_db()
        pbp_col = (
            db.collection(PBP_EVENTS)
            .document(str(game_id))
            .collection(PBP_EVENTS_SUB)
        )
        shots_col = (
            db.collection(SHOTS)
            .document(str(game_id))
            .collection(SHOTS_ATTEMPTS_SUB)
        )

        total_written = 0
        for i in range(0, len(plays), _BATCH_LIMIT):
            chunk = plays[i : i + _BATCH_LIMIT]
            batch = db.batch()
            for play in chunk:
                doc_id = pad_sequence(play.sequenceNumber)
                # PBP event
                batch.set(pbp_col.document(doc_id), play.model_dump(), merge=True)
                # Shot chart (only for shooting plays)
                if play.isShootingPlay:
                    shot_doc = FirebasePBPService.extract_shot_doc(play)
                    batch.set(shots_col.document(doc_id), shot_doc, merge=True)
            batch.commit()
            total_written += len(chunk)

        logger.info(
            f"[PBP-v2] Wrote {total_written} plays for game {game_id} "
            f"(shots extracted inline)"
        )
        return total_written

    @staticmethod
    def extract_shot_doc(play: PlayEvent) -> Dict[str, Any]:
        """
        Extract a lean shot-chart document from a PlayEvent.

        Only stores the fields needed for shot chart visualisation.
        Full play detail remains in pbp_events/.

        Returns:
            Dict with shot-relevant fields only.
        """
        return {
            "sequenceNumber": play.sequenceNumber,
            "playerId": play.primaryPlayerId,
            "playerName": play.primaryPlayerName,
            "teamId": play.teamId,
            "teamTricode": play.teamTricode,
            "shotType": play.eventType,
            "distance": play.shotDistance,
            "made": play.isScoringPlay,
            "period": play.period,
            "clock": play.clock,
            "x": play.coordinateX,
            "y": play.coordinateY,
            "pointsValue": play.pointsValue,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def get_cached_plays_v2(
        game_id: str, limit: int = 1500
    ) -> List[Dict[str, Any]]:
        """
        Read plays from the NEW pbp_events/{game_id}/events/ path.

        Falls back to the legacy live_games/{game_id}/plays/ subcollection
        if the new collection is empty (handles transition period).

        Returns:
            List of play dicts in ascending sequence order.
        """
        db = FirebasePBPService.get_db()

        # Try new path first
        new_col = (
            db.collection(PBP_EVENTS)
            .document(str(game_id))
            .collection(PBP_EVENTS_SUB)
        )
        # Doc IDs are zero-padded → lexicographic sort == numeric sort
        docs = list(new_col.limit(limit).stream())
        if docs:
            return [d.to_dict() for d in docs]

        # Fallback to legacy path (logs a warning so we can monitor transition)
        logger.warning(
            f"[PBP-v2] pbp_events empty for {game_id} — "
            f"falling back to legacy live_games/.../plays/"
        )
        legacy_col = (
            db.collection(LIVE_GAMES)
            .document(str(game_id))
            .collection(LEGACY_LIVE_PLAYS_SUB)
        )
        try:
            legacy_docs = list(
                legacy_col.order_by("sequenceNumber").limit(limit).stream()
            )
            return [d.to_dict() for d in legacy_docs]
        except Exception as e:
            logger.error(f"[PBP-v2] Legacy fallback also failed for {game_id}: {e}")
            return []

    @staticmethod
    def get_shot_chart(game_id: str) -> List[Dict[str, Any]]:
        """
        Read all shot attempts from shots/{game_id}/attempts/.

        Returns:
            List of lean shot dicts in ascending sequence order.
        """
        try:
            db = FirebasePBPService.get_db()
            col = (
                db.collection(SHOTS)
                .document(str(game_id))
                .collection(SHOTS_ATTEMPTS_SUB)
            )
            docs = col.stream()
            return [d.to_dict() for d in docs]
        except Exception as e:
            logger.error(f"[PBP-v2] get_shot_chart failed for {game_id}: {e}")
            return []

    # ═══════════════════════════════════════════════════════════════════════════
    # FINALIZATION (Phase 4 — implemented here, wired in Phase 4 tests)
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def finalize_game(game_id: str) -> bool:
        """
        Create or update final_games/{game_id} when a game reaches FINAL status.

        Steps:
          1. Read live_games/{game_id} for the final scoreboard state.
          2. Safety check: abort if data looks incomplete (missing scores).
          3. Upsert final_games/{game_id} with snapshot + collection pointers.
          4. Mark live_games/{game_id}: trackingEnabled=false, status='final'.
          5. Update games/{game_id} and calendar index status via game service.

        Idempotent: if final_games/{game_id} already exists, we merge (never
        overwrite) so createdAt and existing data are preserved.

        Returns:
            True if finalized successfully, False if skipped (safety guard).
        """
        try:
            db = FirebasePBPService.get_db()
            live_ref = db.collection(LIVE_GAMES).document(str(game_id))
            live_snap = live_ref.get()

            if not live_snap.exists:
                logger.error(
                    f"[Finalize] live_games/{game_id} does not exist — cannot finalize"
                )
                return False

            live = live_snap.to_dict()

            # Safety guard: only finalize if we have a real scoreboard
            home_score = live.get("homeScore")
            away_score = live.get("awayScore")
            if home_score is None or away_score is None:
                logger.warning(
                    f"[Finalize] Aborting — incomplete data for {game_id}: "
                    f"homeScore={home_score}, awayScore={away_score}"
                )
                return False

            now_iso = datetime.now(timezone.utc).isoformat()

            final_ref = db.collection(FINAL_GAMES).document(str(game_id))
            existing_final = final_ref.get()
            created_at = (
                existing_final.to_dict().get("createdAt", now_iso)
                if existing_final.exists
                else now_iso
            )

            snapshot = {
                "gameId": str(game_id),
                "gameDate": live.get("gameDate", ""),
                "season": live.get("season", ""),
                "homeTeam": live.get("homeTeam", {}),
                "awayTeam": live.get("awayTeam", {}),
                "homeScore": home_score,
                "awayScore": away_score,
                "period": live.get("period", 4),
                "status": "Final",
                "totalPlays": live.get("lastSequenceNumber", 0),
                "lastSequenceNumber": live.get("lastSequenceNumber", 0),
                "pbpPath": f"{PBP_EVENTS}/{game_id}/{PBP_EVENTS_SUB}",
                "shotsPath": f"{SHOTS}/{game_id}/{SHOTS_ATTEMPTS_SUB}",
                "finalizedAt": now_iso,
                "createdAt": created_at,
            }
            final_ref.set(snapshot, merge=True)

            # Mark live game as done
            live_ref.set(
                {
                    "trackingEnabled": False,
                    "status": "final",
                    "updatedAt": now_iso,
                },
                merge=True,
            )

            # Update canonical game + calendar index via game service
            game_date = live.get("gameDate", "")
            if game_date:
                from services.firebase_game_service import FirebaseGameService
                FirebaseGameService.update_game_status(game_id, game_date, "Final")

            logger.info(f"[Finalize] Game {game_id} successfully finalized.")
            return True

        except Exception as e:
            logger.error(f"[Finalize] finalize_game failed for {game_id}: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # LEGACY — preserved for backward compat during transition (do NOT delete)
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def save_game_metadata(game_id: str, metadata: Dict[str, Any]):
        """
        [LEGACY] Save high-level metadata for a live game to live_games/{gameId}.

        Still active — the polling service uses this to keep the live state doc
        current.  In Phase 3 this will be superseded by _write_live_state().
        """
        db = FirebasePBPService.get_db()
        doc_ref = db.collection(LIVE_GAMES).document(str(game_id))
        doc_ref.set(metadata, merge=True)

    @staticmethod
    def save_plays_batch(game_id: str, plays: List[PlayEvent]):
        """
        [LEGACY] Idempotent batch write to OLD path: live_games/{gameId}/plays/{playId}.

        Preserved so existing callers (pbp_polling_service before Phase 3)
        are not broken during transition.

        Also calls save_plays_batch_v2() so data is written to BOTH paths
        during the transition window.
        """
        if not plays:
            return

        db = FirebasePBPService.get_db()
        plays_ref = (
            db.collection(LIVE_GAMES)
            .document(str(game_id))
            .collection(LEGACY_LIVE_PLAYS_SUB)
        )

        batch_size = 450
        for i in range(0, len(plays), batch_size):
            batch = db.batch()
            for play in plays[i : i + batch_size]:
                doc_ref = plays_ref.document(str(play.playId))
                batch.set(doc_ref, play.model_dump(), merge=True)
            batch.commit()

        logger.info(
            f"[PBP-legacy] Wrote {len(plays)} plays for game {game_id}"
        )

        # Dual-write: also write to new schema during transition
        FirebasePBPService.save_plays_batch_v2(game_id, plays)

    @staticmethod
    def get_cached_plays(game_id: str, limit: int = 1500) -> List[Dict[str, Any]]:
        """
        [LEGACY] Fetch cached plays from old live_games/{gameId}/plays/ path.

        Returns plays sorted by sequenceNumber ascending.
        """
        db = FirebasePBPService.get_db()
        plays_ref = (
            db.collection(LIVE_GAMES)
            .document(str(game_id))
            .collection(LEGACY_LIVE_PLAYS_SUB)
        )
        try:
            query = plays_ref.order_by("sequenceNumber").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        except Exception as e:
            logger.error(f"[PBP-legacy] get_cached_plays failed for {game_id}: {e}")
            return []

    @staticmethod
    def update_cache_snapshot(game_id: str, plays_count: int, last_polled: str):
        """[LEGACY] Update the fast-read cache snapshot document."""
        db = FirebasePBPService.get_db()
        doc_ref = db.collection(LEGACY_GAME_CACHE).document(str(game_id))
        doc_ref.set(
            {"playsCount": plays_count, "lastPolled": last_polled},
            merge=True,
        )


# Module-level singleton (backward compat)
firebase_pbp_service = FirebasePBPService()
