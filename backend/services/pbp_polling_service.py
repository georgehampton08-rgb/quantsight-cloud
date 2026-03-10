"""
PBP Polling Service — Refactored (Phase 3)
==========================================
Key changes from the original:

1. CURSOR PERSISTENCE: On poller start, reads lastSequenceNumber from
   live_games/{gameId} in Firestore. If Cloud Run cold-starts mid-game,
   we resume from the correct position — no redundant re-ingestion.

2. LIVE STATE CADENCE: live_games/{gameId} is written at most every
   LIVE_STATE_CADENCE_SEC seconds (default 5). This prevents Firestore
   write hotspots on busy games.

3. NEW WRITE PATH: Uses save_plays_batch_v2() which writes to both
   pbp_events/ (new) AND live_games/.../plays/ (legacy dual-write).

4. FINALIZATION: When 'End Game' is detected, calls finalize_game()
   which creates final_games/{gameId} and marks tracking disabled.

5. GAME RECORD UPDATE: On every batch, upserts canonical games/ and
   calendar/ records via FirebaseGameService.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from firestore_db import get_firestore_db
from services.nba_pbp_service import pbp_client, PlayEvent
from services.firebase_pbp_service import firebase_pbp_service, FirebasePBPService
from services.firestore_collections import LIVE_GAMES

logger = logging.getLogger(__name__)


class PBPPollingService:
    # Minimum seconds between live_games/{id} state writes
    LIVE_STATE_CADENCE_SEC: float = 5.0

    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.game_metadata_cache: Dict[str, Dict[str, Any]] = {}
        # In-memory broker for SSE routes. game_id -> list[asyncio.Queue]
        self.sse_queues: Dict[str, List[asyncio.Queue]] = {}

    def get_tracked_games(self) -> List[str]:
        return list(self.active_tasks.keys())

    async def start_tracking(self, game_id: str):
        if game_id in self.active_tasks:
            logger.info(f"Already tracking game {game_id}")
            return
        logger.info(f"Starting tracking for game {game_id}")
        self.active_tasks[game_id] = asyncio.create_task(
            self._poll_loop(game_id)
        )

    def stop_tracking(self, game_id: str):
        task = self.active_tasks.pop(game_id, None)
        if task:
            task.cancel()
            logger.info(f"Stopped tracking game {game_id}")

    # ── Core helpers (sync — called via asyncio.to_thread) ────────────────────

    @staticmethod
    def _read_cursor(game_id: str) -> int:
        """
        Read lastSequenceNumber from live_games/{gameId}.

        Returns the stored cursor, or -1 if the doc doesn't exist yet
        (first time tracking this game).
        """
        try:
            db = get_firestore_db()
            doc = db.collection(LIVE_GAMES).document(str(game_id)).get()
            if doc.exists:
                data = doc.to_dict()
                val = data.get("lastSequenceNumber", -1)
                return int(val) if val is not None else -1
            return -1
        except Exception as e:
            logger.warning(f"[Polling] _read_cursor failed for {game_id}: {e}")
            return -1

    @staticmethod
    def _write_live_state(game_id: str, last_seq: int, last_play: PlayEvent):
        """
        Atomically update live_games/{gameId} with current scoreboard + cursor.

        Fields written:
            status, period, clock, homeScore, awayScore,
            lastSequenceNumber, lastPlayId, ingestHeartbeat, updatedAt,
            trackingEnabled
        """
        try:
            db = get_firestore_db()
            now = datetime.now(timezone.utc).isoformat()
            doc = {
                "status": "In Progress",
                "period": last_play.period,
                "clock": last_play.clock,
                "homeScore": last_play.homeScore,
                "awayScore": last_play.awayScore,
                "lastSequenceNumber": last_seq,
                "lastPlayId": str(last_play.playId),
                "ingestHeartbeat": now,
                "updatedAt": now,
                "trackingEnabled": True,
            }
            db.collection(LIVE_GAMES).document(str(game_id)).set(doc, merge=True)
        except Exception as e:
            logger.error(f"[Polling] _write_live_state failed for {game_id}: {e}")

    @staticmethod
    def _update_game_records(game_id: str, plays: List[PlayEvent]):
        """
        Upsert canonical games/ + calendar/ index from the latest play metadata.

        Only has the game_id and score info from plays — we use the live_games
        doc for any richer metadata (teams, date) if available.
        """
        try:
            db = get_firestore_db()
            live_doc = db.collection(LIVE_GAMES).document(str(game_id)).get()

            if not live_doc.exists:
                return  # No metadata yet — skip silently

            live = live_doc.to_dict()
            game_date = live.get("gameDate", "")
            if not game_date:
                return  # Can't build calendar index without a date

            from services.firebase_game_service import FirebaseGameService
            home_team = live.get("homeTeam", {})
            away_team = live.get("awayTeam", {})

            FirebaseGameService.upsert_canonical_game(
                game_id=game_id,
                game_date=game_date,
                season=live.get("season", ""),
                home_team=home_team,
                away_team=away_team,
                status=live.get("status", "In Progress"),
                start_time=live.get("startTime", ""),
            )
            FirebaseGameService.upsert_calendar_index(
                game_id=game_id,
                game_date=game_date,
                status=live.get("status", "In Progress"),
                home_team=home_team.get("tricode", ""),
                away_team=away_team.get("tricode", ""),
                start_time=live.get("startTime", ""),
            )
        except Exception as e:
            logger.error(f"[Polling] _update_game_records failed for {game_id}: {e}")

    # ── Main polling loop ─────────────────────────────────────────────────────

    async def _poll_loop(self, game_id: str):
        poll_interval = 10  # seconds
        consecutive_errors = 0

        # Phase 3 addition: bootstrap cursor from Firestore (crash-recovery)
        last_sequence_num: int = await asyncio.to_thread(
            self._read_cursor, game_id
        )
        logger.info(
            f"[Polling] Starting game {game_id} with cursor={last_sequence_num}"
        )

        last_live_write: float = 0.0  # epoch time of last live_games write

        try:
            while True:
                try:
                    plays = pbp_client.fetch_espn_plays(game_id)
                    consecutive_errors = 0
                except Exception as e:
                    logger.error(f"ESPN failed for {game_id}: {e}")
                    consecutive_errors += 1
                    plays = []

                # Filter to only plays newer than cursor
                new_plays = [
                    p for p in plays if p.sequenceNumber > last_sequence_num
                ]

                if new_plays:
                    # Fetch game metadata for player shot docs (best-effort — won't fail the batch)
                    try:
                        db = get_firestore_db()
                        meta_doc = db.collection(LIVE_GAMES).document(str(game_id)).get()
                        meta = meta_doc.to_dict() if meta_doc.exists else {}
                    except Exception:
                        meta = {}

                    game_date = meta.get("gameDate", "")
                    home_team = meta.get("homeTeam", {}).get("tricode", "") if isinstance(meta.get("homeTeam"), dict) else ""
                    away_team = meta.get("awayTeam", {}).get("tricode", "") if isinstance(meta.get("awayTeam"), dict) else ""

                    # Phase 3: use v2 write (writes to pbp_events/ + dual-writes legacy)
                    await asyncio.to_thread(
                        firebase_pbp_service.save_plays_batch_v2,
                        game_id,
                        new_plays,
                        game_date,
                        home_team,
                        away_team,
                    )

                    last_sequence_num = max(p.sequenceNumber for p in new_plays)

                    # Cadence-throttled live state write
                    now = time.monotonic()
                    if now - last_live_write >= self.LIVE_STATE_CADENCE_SEC:
                        await asyncio.to_thread(
                            self._write_live_state,
                            game_id,
                            last_sequence_num,
                            new_plays[-1],
                        )
                        last_live_write = now

                    # Update canonical game records (non-blocking best-effort)
                    await asyncio.to_thread(
                        self._update_game_records, game_id, new_plays
                    )

                    # Push new plays to SSE listeners
                    if game_id in self.sse_queues:
                        payload = [p.model_dump() for p in new_plays]
                        for q in self.sse_queues[game_id]:
                            try:
                                q.put_nowait(payload)
                            except asyncio.QueueFull:
                                pass

                    logger.info(
                        f"[Polling] {len(new_plays)} new plays for {game_id}. "
                        f"Cursor={last_sequence_num}"
                    )

                # Game-end detection → finalize
                if plays and any(
                    (
                        p.eventType.lower() in ("end game", "game end")
                        or p.description.lower() in ("end of game", "game over")
                    )
                    for p in plays
                ):
                    logger.info(f"[Polling] Game {game_id} ended. Finalizing.")
                    await asyncio.to_thread(
                        FirebasePBPService.finalize_game, game_id
                    )
                    # Signal SSE clients to close gracefully — prevents zombie
                    # connections from exhausting Cloud Run concurrency limits.
                    sentinel = [{"type": "system_game_ended"}]
                    for q in self.sse_queues.get(game_id, []):
                        try:
                            q.put_nowait(sentinel)
                        except asyncio.QueueFull:
                            pass
                    self.active_tasks.pop(game_id, None)
                    break

                # Exponential backoff on consecutive errors
                sleep_time = (
                    min(poll_interval * (2 ** consecutive_errors), 60)
                    if consecutive_errors > 0
                    else poll_interval
                )
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info(f"[Polling] Poller for {game_id} was cancelled.")
        except Exception as e:
            logger.error(f"[Polling] Fatal error in loop for {game_id}: {e}")
            self.active_tasks.pop(game_id, None)

    # ── SSE Broker ────────────────────────────────────────────────────────────

    def subscribe_sse(self, game_id: str) -> asyncio.Queue:
        if game_id not in self.sse_queues:
            self.sse_queues[game_id] = []
        q = asyncio.Queue(maxsize=100)
        self.sse_queues[game_id].append(q)
        return q

    def unsubscribe_sse(self, game_id: str, q: asyncio.Queue):
        if game_id in self.sse_queues and q in self.sse_queues[game_id]:
            self.sse_queues[game_id].remove(q)
            if not self.sse_queues[game_id]:
                del self.sse_queues[game_id]


# Module-level singleton (unchanged API for callers)
pbp_polling_manager = PBPPollingService()
