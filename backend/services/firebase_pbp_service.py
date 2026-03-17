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
    PLAYER_SHOTS, PLAYER_SHOTS_SUB,
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
    def save_plays_batch_v2(
        game_id: str,
        plays: List[PlayEvent],
        game_date: str = "",
        home_team: str = "",
        away_team: str = "",
    ) -> int:
        """
        Idempotent batch write to the NEW schema path.

        Writes each play to:
            pbp_events/{game_id}/events/{pad_sequence(sequenceNumber)}

        For shooting plays (isShootingPlay == True), also writes a lean doc to:
            shots/{game_id}/attempts/{pad_sequence(sequenceNumber)}

        For shooting plays with a known primaryPlayerId, ALSO writes to:
            player_shots/{playerId}/shots/{game_id}_{pad_sequence(sequenceNumber)}

        Batch logic:
            Firestore limits batches to 500 ops.  Since a shot play produces
            3 writes (pbp + game-shots + player-shots), we cap sub-batches at
            150 plays to stay safely under 500.

        Args:
            game_id:    Game ID string.
            plays:      List of PlayEvent objects.
            game_date:  'YYYY-MM-DD' string.  Used for player shot docs.
            home_team:  Home team tricode (e.g. 'LAL').  Used for matchup.
            away_team:  Away team tricode (e.g. 'GSW').  Used for matchup.

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

        matchup = f"{away_team} @ {home_team}" if home_team and away_team else ""

        # Cap sub-batches at 150 plays (3 writes each = 450 ops, well under 500)
        _BATCH_LIMIT = 150
        total_written = 0
        for i in range(0, len(plays), _BATCH_LIMIT):
            chunk = plays[i : i + _BATCH_LIMIT]
            batch = db.batch()
            for play in chunk:
                doc_id = pad_sequence(play.sequenceNumber)
                # 1. PBP event (full)
                batch.set(pbp_col.document(doc_id), play.model_dump(), merge=True)
                # 2. Game-level shot chart (only for shooting plays)
                if play.isShootingPlay:
                    shot_doc = FirebasePBPService.extract_shot_doc(
                        play, game_id=game_id, game_date=game_date, matchup=matchup
                    )
                    batch.set(shots_col.document(doc_id), shot_doc, merge=True)
                    # 3. Per-player cross-game shot history
                    player_id = play.primaryPlayerId
                    if player_id:
                        player_doc_id = f"{game_id}_{doc_id}"
                        player_shot_ref = (
                            db.collection(PLAYER_SHOTS)
                            .document(str(player_id))
                            .collection(PLAYER_SHOTS_SUB)
                            .document(player_doc_id)
                        )
                        batch.set(player_shot_ref, shot_doc, merge=True)
            batch.commit()
            total_written += len(chunk)

        logger.info(
            f"[PBP-v2] Wrote {total_written} plays for game {game_id} "
            f"(shots extracted + player_shots written)"
        )
        return total_written

    @staticmethod
    def extract_shot_doc(
        play: PlayEvent,
        game_id: str = "",
        game_date: str = "",
        matchup: str = "",
    ) -> Dict[str, Any]:
        """
        Extract a lean shot-chart document from a PlayEvent.

        Stores all fields needed for both game-level and player-level
        shot chart visualisation, including cross-game metadata.

        Returns:
            Dict with shot-relevant fields only.
        """
        return {
            "sequenceNumber": play.sequenceNumber,
            "gameId": game_id,
            "gameDate": game_date,
            "matchup": matchup,
            "playerId": play.primaryPlayerId,
            "playerName": play.primaryPlayerName,
            "teamId": play.teamId,
            "teamTricode": play.teamTricode,
            "shotType": play.eventType,
            "distance": play.shotDistance,
            "shotArea": getattr(play, 'shotArea', None),
            "made": play.isScoringPlay,
            "period": play.period,
            "clock": play.clock,
            "x": play.coordinateX,
            "y": play.coordinateY,
            "pointsValue": play.pointsValue,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _resolve_game_id(db, game_id: str) -> Optional[str]:
        """
        Look up game_id_map to find the alternate ID (ESPN↔NBA).
        Returns the alternate ID if found, else None.
        """
        try:
            map_doc = db.collection("game_id_map").document(str(game_id)).get()
            if map_doc.exists:
                data = map_doc.to_dict()
                # Return whichever ID is NOT the one we already have
                espn = data.get("espn_id", "")
                nba = data.get("nba_id", "")
                return espn if str(game_id) == nba else nba
        except Exception as e:
            logger.debug(f"[PBP] game_id_map lookup failed for {game_id}: {e}")
        return None

    @staticmethod
    def _sort_plays_chronologically(plays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort plays into true game-time order: period ASC, clock DESC.

        ESPN occasionally assigns high sequence numbers to late-reviewed/corrected
        plays that belong to an earlier period or time. Sorting by sequenceNumber
        alone produces a jumbled feed (e.g. Q3 plays appearing after End of Game).

        Clock format is either "MM:SS" (e.g. "11:32") or a bare seconds float
        (e.g. "58.0"). Within a period the clock counts DOWN, so higher clock
        value = earlier in the period.

        Tie-break: sequenceNumber ASC, so simultaneous plays appear in ESPN order.
        """
        def _clock_to_secs(clock_str: Any) -> float:
            try:
                s = str(clock_str)
                if ':' in s:
                    mins, secs = s.split(':', 1)
                    return int(mins) * 60 + float(secs)
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        return sorted(
            plays,
            key=lambda p: (
                p.get('period', 0),          # period ASC
                -_clock_to_secs(p.get('clock', '0:00')),  # clock DESC (higher = earlier)
                p.get('sequenceNumber', 0),  # seq ASC as tie-break
            )
        )

    @staticmethod
    def get_cached_plays_v2(
        game_id: str, limit: int = 1500
    ) -> List[Dict[str, Any]]:
        """
        Read plays from pbp_events/{game_id}/events/.

        Resolution order:
          1. pbp_events/{game_id}/events/        (direct lookup)
          2. game_id_map → alternate ID → pbp_events/{alt_id}/events/
          3. Legacy live_games/{game_id}/plays/   (old schema fallback)

        Returns:
            List of play dicts in chronological game order: period ASC, clock DESC.
        """
        db = FirebasePBPService.get_db()

        # 1. Try direct lookup
        new_col = (
            db.collection(PBP_EVENTS)
            .document(str(game_id))
            .collection(PBP_EVENTS_SUB)
        )
        docs = list(new_col.limit(limit).stream())
        if docs:
            return FirebasePBPService._sort_plays_chronologically(
                [d.to_dict() for d in docs]
            )

        # 2. Try alternate ID via game_id_map (ESPN ↔ NBA translation)
        alt_id = FirebasePBPService._resolve_game_id(db, game_id)
        if alt_id:
            logger.info(f"[PBP-v2] Resolved {game_id} → {alt_id} via game_id_map")
            alt_col = (
                db.collection(PBP_EVENTS)
                .document(str(alt_id))
                .collection(PBP_EVENTS_SUB)
            )
            alt_docs = list(alt_col.limit(limit).stream())
            if alt_docs:
                return FirebasePBPService._sort_plays_chronologically(
                    [d.to_dict() for d in alt_docs]
                )

        # 3. Fallback to legacy path
        logger.warning(
            f"[PBP-v2] pbp_events empty for {game_id} (alt={alt_id}) — "
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
            return FirebasePBPService._sort_plays_chronologically(
                [d.to_dict() for d in legacy_docs]
            )
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

    @staticmethod
    def get_player_shots(
        player_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """
        Return all shot attempts for a player across games.

        Reads player_shots/{player_id}/shots/ subcollection.
        Optionally filtered by gameDate range.

        Args:
            player_id: NBA player ID string.
            date_from: 'YYYY-MM-DD' inclusive lower bound (optional).
            date_to:   'YYYY-MM-DD' inclusive upper bound (optional).
            limit:     Maximum number of shot docs to return.

        Returns:
            List of shot dicts ordered by gameDate + sequenceNumber.
        """
        try:
            db = FirebasePBPService.get_db()
            col = (
                db.collection(PLAYER_SHOTS)
                .document(str(player_id))
                .collection(PLAYER_SHOTS_SUB)
            )
            query = col.limit(limit)
            if date_from:
                query = query.where("gameDate", ">=", date_from)
            if date_to:
                query = query.where("gameDate", "<=", date_to)
            docs = query.stream()
            results = [d.to_dict() for d in docs]
            # Client-side sort: by gameDate desc, then sequenceNumber asc
            results.sort(key=lambda s: (s.get("gameDate", ""), s.get("sequenceNumber", 0)))
            return results
        except Exception as e:
            logger.error(f"[PBP-v2] get_player_shots failed for {player_id}: {e}")
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
    def save_plays_batch(
        game_id: str,
        plays: List[PlayEvent],
        game_date: str = "",
        home_team: str = "",
        away_team: str = "",
    ):
        """
        [LEGACY] Idempotent batch write to OLD path: live_games/{gameId}/plays/{playId}.

        Preserved so existing callers (pbp_polling_service before Phase 3)
        are not broken during transition.

        Also calls save_plays_batch_v2() so data is written to BOTH paths
        during the transition window.  game_date / home_team / away_team are
        forwarded so shot docs receive correct matchup metadata.
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
        # Forward metadata so shot docs are enriched correctly.
        FirebasePBPService.save_plays_batch_v2(
            game_id, plays, game_date, home_team, away_team
        )

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
