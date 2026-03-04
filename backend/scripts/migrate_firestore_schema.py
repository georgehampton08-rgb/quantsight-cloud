"""
Firestore Schema Migration Script
===================================
One-time migration from legacy schema to the new 6-collection architecture.
Safe to re-run at any time (fully idempotent via merge=True writes).

Usage:
    # Full migration (reads + writes to new collections):
    python scripts/migrate_firestore_schema.py

    # Dry run (scan + count only, ZERO writes):
    python scripts/migrate_firestore_schema.py --dry-run

    # Verify migration (compare counts between old and new):
    python scripts/migrate_firestore_schema.py --verify

    # Cleanup legacy data (ONLY after --verify passes):
    python scripts/migrate_firestore_schema.py --cleanup

Collections written to (new):
    games/{gameId}
    calendar/{date}/games/{gameId}
    pbp_events/{gameId}/events/{paddedSeq}
    shots/{gameId}/attempts/{paddedSeq}
    final_games/{gameId}

Collections read from (legacy — NEVER deleted in default run):
    live_games/{gameId}
    live_games/{gameId}/plays/{playId}
    game_logs/{date}/games/{gameId}
    game_cache/{gameId}
"""
import sys
import os
import argparse
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Allow running from the backend/ directory directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migrate")


# ── Lazy import of Firestore services (only when actually running, not in tests) ──

def _get_services():
    from firestore_db import get_firestore_db
    from services.firestore_collections import (
        LIVE_GAMES, LEGACY_LIVE_PLAYS_SUB, LEGACY_GAME_CACHE,
        GAMES, CALENDAR, CALENDAR_GAMES_SUB,
        PBP_EVENTS, PBP_EVENTS_SUB,
        SHOTS, SHOTS_ATTEMPTS_SUB,
        FINAL_GAMES,
        pad_sequence,
    )
    from services.firebase_game_service import FirebaseGameService
    from services.firebase_pbp_service import FirebasePBPService
    from services.nba_pbp_service import PlayEvent
    return {
        "db": get_firestore_db(),
        "FirebaseGameService": FirebaseGameService,
        "FirebasePBPService": FirebasePBPService,
        "PlayEvent": PlayEvent,
        "pad_sequence": pad_sequence,
        "LIVE_GAMES": LIVE_GAMES,
        "LEGACY_LIVE_PLAYS_SUB": LEGACY_LIVE_PLAYS_SUB,
        "LEGACY_GAME_CACHE": LEGACY_GAME_CACHE,
        "GAMES": GAMES,
        "CALENDAR": CALENDAR,
        "CALENDAR_GAMES_SUB": CALENDAR_GAMES_SUB,
        "PBP_EVENTS": PBP_EVENTS,
        "PBP_EVENTS_SUB": PBP_EVENTS_SUB,
        "SHOTS": SHOTS,
        "SHOTS_ATTEMPTS_SUB": SHOTS_ATTEMPTS_SUB,
        "FINAL_GAMES": FINAL_GAMES,
    }


class FirestoreMigrator:
    """
    Orchestrates the one-time migration from legacy to new Firestore schema.

    Designed to be injectable with a mock DB (for testing) via the `db` parameter.
    When db=None, connects to real Firestore.
    """

    def __init__(self, db=None, dry_run: bool = False):
        self.dry_run = dry_run
        self._db = db  # None means use real Firestore
        self._svc = None  # lazily loaded when db is None

    def _get_db(self):
        if self._db is not None:
            return self._db
        if self._svc is None:
            self._svc = _get_services()
        return self._svc["db"]

    def _pad(self, seq: int) -> str:
        from services.firestore_collections import pad_sequence
        return pad_sequence(seq)

    # ── Scanning ──────────────────────────────────────────────────────────────

    def scan_live_games(self) -> List[Dict[str, Any]]:
        """Return list of (game_id, doc_data) dicts from live_games/ collection."""
        db = self._get_db()
        docs = db.collection("live_games").stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["_id"] = doc.id if hasattr(doc, "id") else data.get("game_id", "unknown")
            results.append(data)
        return results

    def scan_game_logs(self) -> Dict[str, List[str]]:
        """
        Return: {date_str: [game_id, ...]} from game_logs/{date}/games/ hierarchy.
        """
        db = self._get_db()
        date_map: Dict[str, List[str]] = {}
        try:
            date_docs = db.collection("game_logs").stream()
            for date_doc in date_docs:
                date_str = date_doc.id if hasattr(date_doc, "id") else ""
                if not date_str:
                    continue
                game_docs = (
                    db.collection("game_logs")
                    .document(date_str)
                    .collection("games")
                    .stream()
                )
                ids = [
                    g.id if hasattr(g, "id") else g.to_dict().get("game_id", "")
                    for g in game_docs
                ]
                if ids:
                    date_map[date_str] = ids
        except Exception as e:
            logger.warning(f"scan_game_logs error: {e}")
        return date_map

    def read_legacy_plays(self, game_id: str) -> List[Dict[str, Any]]:
        """Read all plays from live_games/{gameId}/plays/ subcollection."""
        db = self._get_db()
        try:
            docs = (
                db.collection("live_games")
                .document(str(game_id))
                .collection("plays")
                .stream()
            )
            plays = [d.to_dict() for d in docs]
            # Sort by sequenceNumber so migration order is deterministic
            plays.sort(key=lambda p: p.get("sequenceNumber", 0))
            return plays
        except Exception as e:
            logger.warning(f"read_legacy_plays failed for {game_id}: {e}")
            return []

    # ── Inference helpers ──────────────────────────────────────────────────────

    def infer_game_date(
        self, game_id: str, live_data: Dict, game_log_map: Dict[str, List[str]]
    ) -> str:
        """
        Infer gameDate for a game.

        Priority:
          1. live_games doc has gameDate field (best case)
          2. Scan game_logs/{date}/games/ and match game_id
          3. Fall back to today's date (with warning)
        """
        # Option 1: already in live doc
        date = live_data.get("gameDate", "")
        if date:
            return date

        # Option 2: scan game_logs
        for date_str, ids in game_log_map.items():
            if game_id in ids:
                return date_str

        # Option 3: warn and use today
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.warning(
            f"Could not infer game_date for {game_id} — using today {today}"
        )
        return today

    # ── Migration ──────────────────────────────────────────────────────────────

    def migrate_game(
        self,
        game_id: str,
        live_data: Dict[str, Any],
        game_date: str,
    ) -> Dict[str, int]:
        """
        Migrate one game. Returns counts: {pbp_written, shots_written}.
        In dry_run mode: scans and returns expected counts without writing.
        """
        db = self._get_db()
        now = datetime.now(timezone.utc).isoformat()
        counts = {"pbp_written": 0, "shots_written": 0}

        # ── 1. Canonical game record ──────────────────────────────────────────
        home_team = live_data.get("homeTeam", {})
        away_team = live_data.get("awayTeam", {})
        status = live_data.get("status", "Unknown")

        if not self.dry_run:
            ref = db.collection("games").document(str(game_id))
            existing = ref.get()
            created_at = (
                existing.to_dict().get("createdAt", now)
                if existing.exists
                else now
            )
            ref.set(
                {
                    "gameId": str(game_id),
                    "gameDate": game_date,
                    "season": live_data.get("season", ""),
                    "homeTeam": home_team,
                    "awayTeam": away_team,
                    "status": status,
                    "startTime": live_data.get("startTime", ""),
                    "createdAt": created_at,
                    "updatedAt": now,
                },
                merge=True,
            )

        # ── 2. Calendar index ─────────────────────────────────────────────────
        if not self.dry_run:
            cal_ref = (
                db.collection("calendar")
                .document(game_date)
                .collection("games")
                .document(str(game_id))
            )
            cal_ref.set(
                {
                    "gameId": str(game_id),
                    "status": status,
                    "homeTeam": home_team.get("tricode", "") if isinstance(home_team, dict) else str(home_team),
                    "awayTeam": away_team.get("tricode", "") if isinstance(away_team, dict) else str(away_team),
                    "startTime": live_data.get("startTime", ""),
                    "refPath": f"games/{game_id}",
                    "updatedAt": now,
                },
                merge=True,
            )

        # ── 3. Migrate PBP plays ──────────────────────────────────────────────
        legacy_plays = self.read_legacy_plays(game_id)

        if not legacy_plays:
            logger.info(f"  [{game_id}] No legacy plays to migrate.")
            counts["pbp_written"] = 0
        else:
            logger.info(f"  [{game_id}] Migrating {len(legacy_plays)} plays...")

            from services.firestore_collections import pad_sequence as _pad

            BATCH_LIMIT = 225
            for i in range(0, len(legacy_plays), BATCH_LIMIT):
                chunk = legacy_plays[i : i + BATCH_LIMIT]

                if not self.dry_run:
                    batch = db.batch()
                    pbp_col = (
                        db.collection("pbp_events")
                        .document(str(game_id))
                        .collection("events")
                    )
                    shots_col = (
                        db.collection("shots")
                        .document(str(game_id))
                        .collection("attempts")
                    )

                    for play in chunk:
                        seq = play.get("sequenceNumber", 0)
                        doc_id = _pad(int(seq))
                        # Write PBP event (all fields preserved)
                        batch.set(pbp_col.document(doc_id), play, merge=True)
                        # Write shot if applicable
                        if play.get("isShootingPlay"):
                            shot_doc = {
                                "sequenceNumber": seq,
                                "playerId": play.get("primaryPlayerId"),
                                "playerName": play.get("primaryPlayerName"),
                                "teamId": play.get("teamId"),
                                "teamTricode": play.get("teamTricode"),
                                "shotType": play.get("eventType"),
                                "distance": play.get("shotDistance"),
                                "made": play.get("isScoringPlay", False),
                                "period": play.get("period"),
                                "clock": play.get("clock"),
                                "x": play.get("coordinateX"),
                                "y": play.get("coordinateY"),
                                "pointsValue": play.get("pointsValue", 0),
                                "ts": now,
                            }
                            batch.set(shots_col.document(doc_id), shot_doc, merge=True)
                            counts["shots_written"] += 1
                    batch.commit()

                counts["pbp_written"] += len(chunk)

        # ── 4. Final freeze (if game was final) ───────────────────────────────
        is_final = status.lower() in ("final", "finished", "post")
        home_score = live_data.get("homeScore")
        away_score = live_data.get("awayScore")

        if is_final and home_score is not None and away_score is not None:
            if not self.dry_run:
                final_ref = db.collection("final_games").document(str(game_id))
                existing_final = final_ref.get()
                created_at_final = (
                    existing_final.to_dict().get("createdAt", now)
                    if existing_final.exists
                    else now
                )
                final_ref.set(
                    {
                        "gameId": str(game_id),
                        "gameDate": game_date,
                        "season": live_data.get("season", ""),
                        "homeTeam": home_team,
                        "awayTeam": away_team,
                        "homeScore": home_score,
                        "awayScore": away_score,
                        "period": live_data.get("period", 4),
                        "status": "Final",
                        "lastSequenceNumber": live_data.get("lastSequenceNumber", len(legacy_plays)),
                        "totalPlays": len(legacy_plays),
                        "pbpPath": f"pbp_events/{game_id}/events",
                        "shotsPath": f"shots/{game_id}/attempts",
                        "finalizedAt": now,
                        "createdAt": created_at_final,
                    },
                    merge=True,
                )
            logger.info(f"  [{game_id}] Final freeze written.")

        return counts

    # ── Full migration run ─────────────────────────────────────────────────────

    def run_migration(self) -> Dict[str, Any]:
        """
        Execute migration for all games in live_games/.
        Returns summary report dict.
        """
        mode = "DRY RUN" if self.dry_run else "MIGRATION"
        logger.info(f"\n{'='*60}")
        logger.info(f"  Firestore Schema Migration — {mode}")
        logger.info(f"  Started: {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"{'='*60}\n")

        game_log_map = self.scan_game_logs()
        live_games = self.scan_live_games()

        logger.info(f"Found {len(live_games)} games in live_games/")
        logger.info(f"Found {sum(len(v) for v in game_log_map.values())} games in game_logs/")

        report = {
            "games_found": len(live_games),
            "games_migrated": 0,
            "total_pbp_written": 0,
            "total_shots_written": 0,
            "errors": [],
        }

        for live_data in live_games:
            game_id = live_data.get("_id") or live_data.get("game_id", "unknown")
            try:
                game_date = self.infer_game_date(game_id, live_data, game_log_map)
                counts = self.migrate_game(game_id, live_data, game_date)
                report["games_migrated"] += 1
                report["total_pbp_written"] += counts["pbp_written"]
                report["total_shots_written"] += counts["shots_written"]
                logger.info(
                    f"  ✅ {game_id} on {game_date}: "
                    f"{counts['pbp_written']} plays, {counts['shots_written']} shots"
                )
            except Exception as e:
                logger.error(f"  ❌ {game_id}: {e}")
                report["errors"].append({"game_id": game_id, "error": str(e)})

        logger.info(f"\n{'─'*60}")
        logger.info(f"  Games migrated:   {report['games_migrated']}/{report['games_found']}")
        logger.info(f"  PBP events written: {report['total_pbp_written']}")
        logger.info(f"  Shot docs written:  {report['total_shots_written']}")
        logger.info(f"  Errors:             {len(report['errors'])}")
        if self.dry_run:
            logger.info("  [DRY RUN — no writes made]")
        else:
            logger.info("  ✅ Migration complete")

        return report

    # ── Verification ──────────────────────────────────────────────────────────

    def verify_migration(self) -> bool:
        """
        Compare document counts between old and new collections.
        Returns True if all checks pass, False otherwise.
        """
        db = self._get_db()
        logger.info("\n" + "="*60)
        logger.info("  Migration Verification Report")
        logger.info(f"  {datetime.now(timezone.utc).isoformat()}")
        logger.info("="*60 + "\n")

        all_pass = True
        live_games = self.scan_live_games()

        for live_data in live_games:
            game_id = live_data.get("_id") or live_data.get("game_id", "unknown")
            try:
                # Count legacy plays
                legacy_plays = self.read_legacy_plays(game_id)
                legacy_count = len(legacy_plays)

                # Count new pbp_events
                new_docs = list(
                    db.collection("pbp_events")
                    .document(str(game_id))
                    .collection("events")
                    .stream()
                )
                new_count = len(new_docs)

                # Count shots
                shot_docs = list(
                    db.collection("shots")
                    .document(str(game_id))
                    .collection("attempts")
                    .stream()
                )
                shot_count = len(shot_docs)

                counts_match = legacy_count == new_count
                shots_ok = shot_count <= new_count
                status = "✅" if (counts_match and shots_ok) else "❌"
                logger.info(
                    f"  {status} {game_id}: "
                    f"legacy={legacy_count}, new={new_count}, shots={shot_count}"
                )
                if not counts_match:
                    all_pass = False
                    logger.warning(
                        f"     COUNT MISMATCH: legacy={legacy_count} != new={new_count}"
                    )
            except Exception as e:
                logger.error(f"  ❌ {game_id}: verification error: {e}")
                all_pass = False

        result = "ALL CHECKS PASSED ✅" if all_pass else "FAILURES DETECTED ❌"
        logger.info(f"\n  RESULT: {result}")
        return all_pass

    # ── Cleanup (optional, post-verify) ───────────────────────────────────────

    def cleanup_legacy(self):
        """
        Delete legacy subcollections ONLY.
        NEVER called in default migration — requires explicit --cleanup flag.
        ALWAYS run --verify first.
        """
        db = self._get_db()
        logger.info("\n" + "="*60)
        logger.info("  ⚠️  CLEANUP: Removing legacy live_games/.../plays/ docs")
        logger.info("="*60 + "\n")

        live_games = self.scan_live_games()
        deleted_total = 0

        for live_data in live_games:
            game_id = live_data.get("_id") or live_data.get("game_id", "unknown")
            plays_col = (
                db.collection("live_games")
                .document(str(game_id))
                .collection("plays")
            )
            batch = db.batch()
            count = 0
            for doc in plays_col.stream():
                batch.delete(doc.reference)
                count += 1
                if count % 450 == 0:
                    batch.commit()
                    batch = db.batch()
            if count % 450 != 0:
                batch.commit()
            deleted_total += count
            logger.info(f"  Deleted {count} legacy plays for {game_id}")

        logger.info(f"\n  Total legacy play docs deleted: {deleted_total}")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Firestore Schema Migration")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan + count only. Make ZERO writes.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Compare counts between legacy and new collections.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete legacy live_games/.../plays/ after verification.",
    )
    args = parser.parse_args()

    if args.cleanup:
        logger.warning(
            "⚠️  CLEANUP mode — this will delete legacy subcollection data. "
            "Make sure --verify passed first!"
        )
        inp = input("Type 'yes-delete' to confirm: ").strip()
        if inp != "yes-delete":
            print("Aborted.")
            sys.exit(0)
        migrator = FirestoreMigrator(dry_run=False)
        migrator.cleanup_legacy()
    elif args.verify:
        migrator = FirestoreMigrator(dry_run=False)
        passed = migrator.verify_migration()
        sys.exit(0 if passed else 1)
    else:
        migrator = FirestoreMigrator(dry_run=args.dry_run)
        report = migrator.run_migration()
        sys.exit(0 if not report["errors"] else 1)
