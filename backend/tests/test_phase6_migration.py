"""
Phase 6 — Migration Script Tests
==================================
Tests for scripts/migrate_firestore_schema.py using in-memory Firestore mock.
Completely offline.

Run:
    cd backend && python tests/test_phase6_migration.py
"""
import sys
import os
import copy
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback

PASS = "\u2705"
FAIL = "\u274c"
results = []


# ── In-memory mock DB (self-contained, consistent with prior phases) ──────────

class _MockDoc:
    def __init__(self, data=None, doc_id=""):
        self._data = data
        self.id = doc_id
        self.exists = data is not None
    def to_dict(self):
        return copy.deepcopy(self._data) if self._data else {}
    # For cleanup test
    @property
    def reference(self):
        return self

class _MockBatch:
    def __init__(self, store):
        self._store = store
        self._ops = []
    def set(self, ref, data, merge=False):
        self._ops.append(("set", ref._path, data, merge))
    def delete(self, ref_or_self):
        path = ref_or_self._path if hasattr(ref_or_self, "_path") else ref_or_self
        self._ops.append(("del", path, None, False))
    def commit(self):
        for op, path, data, merge in self._ops:
            if op == "set":
                if merge and path in self._store._docs:
                    self._store._docs[path] = {**self._store._docs[path], **data}
                else:
                    self._store._docs[path] = copy.deepcopy(data)
            elif op == "del":
                self._store._docs.pop(path, None)
        self._ops.clear()

class _MockRef:
    def __init__(self, store, path):
        self._store = store
        self._path = path
    def collection(self, name):
        return _MockCollection(self._store, f"{self._path}/{name}")
    def get(self):
        data = self._store._docs.get(self._path)
        doc_id = self._path.split("/")[-1] if "/" in self._path else self._path
        return _MockDoc(data, doc_id)
    def set(self, data, merge=False):
        if merge and self._path in self._store._docs:
            self._store._docs[self._path] = {**self._store._docs[self._path], **data}
        else:
            self._store._docs[self._path] = copy.deepcopy(data)

class _MockCollection:
    def __init__(self, store, path):
        self._store = store
        self._path = path
    def document(self, doc_id):
        return _MockRef(self._store, f"{self._path}/{doc_id}")
    def stream(self):
        prefix = self._path + "/"
        docs = [
            (k, v) for k, v in self._store._docs.items()
            if k.startswith(prefix) and "/" not in k[len(prefix):]
        ]
        docs.sort(key=lambda x: x[0])
        for k, v in docs:
            doc_id = k[len(prefix):]
            yield _MockDoc(v, doc_id)

class _MockStore:
    def __init__(self):
        self._docs: Dict = {}
    def collection(self, name):
        return _MockCollection(self, name)
    def batch(self):
        return _MockBatch(self)


def test(name, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, None))
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  {FAIL}  {name}\n       {e}")
        results.append((name, False, tb))


GAME_ID = "0022500789"
GAME_DATE = "2026-03-03"


def _make_live_doc(game_id: str, date: str, status: str = "Final",
                   final: bool = True) -> Dict:
    doc = {
        "_id": game_id,
        "game_id": game_id,
        "gameDate": date,
        "season": "2025-26",
        "status": status,
        "homeTeam": {"tricode": "LAL"},
        "awayTeam": {"tricode": "BOS"},
        "startTime": f"{date}T19:30:00Z",
        "period": 4,
        "lastSequenceNumber": 10,
    }
    if final:
        doc["homeScore"] = 112
        doc["awayScore"] = 108
    return doc


def _make_play(i: int, is_shot: bool = False) -> Dict:
    return {
        "playId": f"p{i}",
        "sequenceNumber": i,
        "eventType": "3pt" if is_shot else "Sub",
        "description": f"play {i}",
        "period": 2,
        "clock": "5:00",
        "homeScore": 50,
        "awayScore": 48,
        "isShootingPlay": is_shot,
        "isScoringPlay": is_shot,
        "source": "espn",
    }


# Patch constant so migration uses our mock DB
def with_mock_migration(fn, dry_run=False):
    db = _MockStore()
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    from migrate_firestore_schema import FirestoreMigrator
    migrator = FirestoreMigrator(db=db, dry_run=dry_run)
    fn(db, migrator)


# ─────────────────────────────────────────────────────────────────────────────
# T-60: dry run makes zero writes
# ─────────────────────────────────────────────────────────────────────────────
def t60_dry_run_no_writes():
    def run(db, migrator):
        # Pre-populate live_games with one game
        db._docs[f"live_games/{GAME_ID}"] = _make_live_doc(GAME_ID, GAME_DATE)
        db._docs[f"live_games/{GAME_ID}/plays/p1"] = _make_play(1)

        initial_doc_count = len(db._docs)
        migrator.run_migration()
        final_doc_count = len(db._docs)

        assert final_doc_count == initial_doc_count, \
            f"Dry run wrote {final_doc_count - initial_doc_count} new docs — should be 0"

    with_mock_migration(run, dry_run=True)


# ─────────────────────────────────────────────────────────────────────────────
# T-61: Full migration of a single game writes to all 5 new collections
# ─────────────────────────────────────────────────────────────────────────────
def t61_migrate_single_game():
    def run(db, migrator):
        db._docs[f"live_games/{GAME_ID}"] = _make_live_doc(GAME_ID, GAME_DATE)
        # 3 plays: 2 shots, 1 non-shot
        for i, is_shot in [(1, True), (2, False), (3, True)]:
            db._docs[f"live_games/{GAME_ID}/plays/p{i}"] = _make_play(i, is_shot)

        report = migrator.run_migration()

        assert report["games_migrated"] == 1
        # games/ collection
        assert f"games/{GAME_ID}" in db._docs, "canonical game doc missing"
        # calendar/
        assert f"calendar/{GAME_DATE}/games/{GAME_ID}" in db._docs, "calendar doc missing"
        # pbp_events/
        assert f"pbp_events/{GAME_ID}/events/000001" in db._docs
        assert f"pbp_events/{GAME_ID}/events/000002" in db._docs
        assert f"pbp_events/{GAME_ID}/events/000003" in db._docs
        # shots/
        assert f"shots/{GAME_ID}/attempts/000001" in db._docs, "shot 1 missing"
        assert f"shots/{GAME_ID}/attempts/000003" in db._docs, "shot 3 missing"
        assert f"shots/{GAME_ID}/attempts/000002" not in db._docs, "non-shot 2 in shots/"
        # final_games/
        assert f"final_games/{GAME_ID}" in db._docs, "final_games doc missing"

    with_mock_migration(run, dry_run=False)


# ─────────────────────────────────────────────────────────────────────────────
# T-62: Migration is idempotent (running twice produces same doc count)
# ─────────────────────────────────────────────────────────────────────────────
def t62_migration_idempotent():
    def run(db, migrator):
        db._docs[f"live_games/{GAME_ID}"] = _make_live_doc(GAME_ID, GAME_DATE)
        db._docs[f"live_games/{GAME_ID}/plays/p1"] = _make_play(1, is_shot=True)

        migrator.run_migration()
        count_after_first = len(db._docs)

        migrator.run_migration()
        count_after_second = len(db._docs)

        assert count_after_first == count_after_second, \
            f"Idempotency broken: first={count_after_first}, second={count_after_second}"

    with_mock_migration(run, dry_run=False)


# ─────────────────────────────────────────────────────────────────────────────
# T-63: --verify confirms play counts match
# ─────────────────────────────────────────────────────────────────────────────
def t63_verify_counts_match():
    def run(db, migrator):
        db._docs[f"live_games/{GAME_ID}"] = _make_live_doc(GAME_ID, GAME_DATE)
        db._docs[f"live_games/{GAME_ID}/plays/p1"] = _make_play(1)
        db._docs[f"live_games/{GAME_ID}/plays/p2"] = _make_play(2)

        # Migrate first
        migrator.run_migration()

        # Then verify
        passed = migrator.verify_migration()
        assert passed, "verify_migration should return True when counts match"

    with_mock_migration(run, dry_run=False)


# ─────────────────────────────────────────────────────────────────────────────
# T-64: Pre-existing final_games doc is NOT overwritten (createdAt preserved)
# ─────────────────────────────────────────────────────────────────────────────
def t64_preserves_existing_final():
    def run(db, migrator):
        # Pre-existing final_games entry (e.g., manually created or from earlier migration)
        old_created = "2026-01-01T00:00:00Z"
        db._docs[f"final_games/{GAME_ID}"] = {
            "gameId": GAME_ID,
            "createdAt": old_created,
            "customLegacyField": "keep-me",
            "homeScore": 100,
            "awayScore": 90,
        }
        db._docs[f"live_games/{GAME_ID}"] = _make_live_doc(GAME_ID, GAME_DATE)
        db._docs[f"live_games/{GAME_ID}/plays/p1"] = _make_play(1)

        migrator.run_migration()

        doc = db._docs[f"final_games/{GAME_ID}"]
        assert doc["createdAt"] == old_created, \
            f"createdAt was overwritten: got {doc['createdAt']}"
        assert doc.get("customLegacyField") == "keep-me", \
            "Custom legacy field was lost"

    with_mock_migration(run, dry_run=False)


# ─────────────────────────────────────────────────────────────────────────────
# T-65: gameDate inference from play doc when live doc lacks gameDate
# ─────────────────────────────────────────────────────────────────────────────
def t65_date_inference():
    def run(db, migrator):
        # Live doc has no gameDate
        live_no_date = _make_live_doc(GAME_ID, GAME_DATE)
        del live_no_date["gameDate"]
        db._docs[f"live_games/{GAME_ID}"] = live_no_date

        # game_logs has the date mapping
        game_log_map = {GAME_DATE: [GAME_ID]}

        inferred = migrator.infer_game_date(GAME_ID, live_no_date, game_log_map)
        assert inferred == GAME_DATE, f"Expected {GAME_DATE}, got {inferred}"

    with_mock_migration(run, dry_run=False)


# ─────────────────────────────────────────────────────────────────────────────
# T-66: Phase 0+1+2+3+4+5 regression
# ─────────────────────────────────────────────────────────────────────────────
def t66_regression():
    from services.firestore_collections import pad_sequence, FINAL_GAMES, PBP_EVENTS
    from services.firebase_pbp_service import FirebasePBPService
    from services.firebase_game_service import FirebaseGameService
    from services.pbp_polling_service import PBPPollingService
    import api.play_by_play_routes as routes

    assert pad_sequence(42) == "000042"
    assert FINAL_GAMES == "final_games"
    assert PBP_EVENTS == "pbp_events"
    assert hasattr(FirebasePBPService, "finalize_game")
    assert hasattr(FirebaseGameService, "upsert_calendar_index")
    assert hasattr(PBPPollingService, "_write_live_state")
    assert any("/shots" in r.path for r in routes.router.routes)


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Phase 6 — Migration Script                      ║")
    print("╚══════════════════════════════════════════════════╝\n")

    test("T-60  --dry-run makes zero writes", t60_dry_run_no_writes)
    test("T-61  Full migration writes to all 5 new collections", t61_migrate_single_game)
    test("T-62  Migration is idempotent (2nd run = same count)", t62_migration_idempotent)
    test("T-63  --verify passes when counts match", t63_verify_counts_match)
    test("T-64  Pre-existing final_games preserved (createdAt)", t64_preserves_existing_final)
    test("T-65  gameDate inferred from game_logs when missing", t65_date_inference)
    test("T-66  Phase 0+1+2+3+4+5 regression", t66_regression)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'─' * 52}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ✅ PHASE 6 GATE: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("  ❌ PHASE 6 GATE: FAILURES — DO NOT ADVANCE")
        for name, ok, tb in results:
            if not ok:
                print(f"\n  FAILED: {name}\n{tb}")
        sys.exit(1)
