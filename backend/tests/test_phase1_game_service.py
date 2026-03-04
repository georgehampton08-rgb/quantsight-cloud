"""
Phase 1 — Game Service & Calendar Index
==========================================
Tests for firebase_game_service.py using an in-memory Firestore mock.

All tests are completely offline — no Firebase credentials required.

Run:
    cd backend && python tests/test_phase1_game_service.py
"""
import sys
import os
import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback

PASS = "\u2705"
FAIL = "\u274c"
results = []


# ─────────────────────────────────────────────────────────────────────────────
# Minimal in-memory Firestore mock
# ─────────────────────────────────────────────────────────────────────────────

class _MockDoc:
    """Simulates a Firestore document snapshot."""
    def __init__(self, data: Optional[Dict] = None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data) if self._data else {}


class _MockStore:
    """
    Very simple in-memory hierarchical store: path -> dict.
    Supports collection/doc/collection/doc nesting via '/' paths.
    """
    def __init__(self):
        self._docs: Dict[str, Dict] = {}

    def _ref(self, path: str) -> "_MockRef":
        return _MockRef(self, path)

    def collection(self, name: str) -> "_MockCollection":
        return _MockCollection(self, name)


class _MockCollection:
    def __init__(self, store: _MockStore, path: str):
        self._store = store
        self._path = path

    def document(self, doc_id: str) -> "_MockRef":
        return _MockRef(self._store, f"{self._path}/{doc_id}")

    def stream(self):
        prefix = self._path + "/"
        seen = {}
        for k, v in self._store._docs.items():
            if k.startswith(prefix):
                remainder = k[len(prefix):]
                # Only direct children (no sub-sub-docs)
                if "/" not in remainder:
                    seen[k] = v
        for k, v in seen.items():
            yield _MockDoc(v)


class _MockRef:
    def __init__(self, store: _MockStore, path: str):
        self._store = store
        self._path = path

    def collection(self, name: str) -> "_MockCollection":
        return _MockCollection(self._store, f"{self._path}/{name}")

    def get(self) -> _MockDoc:
        data = self._store._docs.get(self._path)
        return _MockDoc(data)

    def set(self, data: Dict, merge: bool = False):
        if merge and self._path in self._store._docs:
            existing = self._store._docs[self._path]
            merged = {**existing, **data}
            self._store._docs[self._path] = merged
        else:
            self._store._docs[self._path] = copy.deepcopy(data)


# ─────────────────────────────────────────────────────────────────────────────
# Helper — build a fresh mock DB for each test
# ─────────────────────────────────────────────────────────────────────────────

GAME_ID = "0022500789"
GAME_DATE = "2026-03-03"
HOME = {"tricode": "LAL", "name": "Los Angeles Lakers", "teamId": "1610612747"}
AWAY = {"tricode": "BOS", "name": "Boston Celtics", "teamId": "1610612738"}
STATUS = "In Progress"
START = "2026-03-03T19:30:00-05:00"
SEASON = "2025-26"

def _run_with_mock(fn):
    """Run fn(mock_db) with get_firestore_db patched to return mock_db."""
    mock_db = _MockStore()
    with patch("services.firebase_game_service.get_firestore_db", return_value=mock_db):
        fn(mock_db)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test(name: str, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, None))
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  {FAIL}  {name}\n       {e}")
        results.append((name, False, tb))


# T-10: upsert_canonical_game creates a doc at games/{gameId}
def t10_upsert_canonical_creates_doc():
    from services.firebase_game_service import FirebaseGameService

    def run(db):
        ok = FirebaseGameService.upsert_canonical_game(
            GAME_ID, GAME_DATE, SEASON, HOME, AWAY, STATUS, START
        )
        assert ok, "Expected True return value"
        doc = db._docs.get(f"games/{GAME_ID}")
        assert doc is not None, "Doc not created at games/{gameId}"
        assert doc["gameId"] == GAME_ID
        assert doc["gameDate"] == GAME_DATE
        assert doc["season"] == SEASON
        assert doc["status"] == STATUS
        assert doc["startTime"] == START
        assert "createdAt" in doc
        assert "updatedAt" in doc

    _run_with_mock(run)


# T-11: upsert_canonical_game is idempotent — createdAt must be preserved
def t11_upsert_canonical_idempotent():
    from services.firebase_game_service import FirebaseGameService

    def run(db):
        FirebaseGameService.upsert_canonical_game(
            GAME_ID, GAME_DATE, SEASON, HOME, AWAY, STATUS, START
        )
        first_created = db._docs[f"games/{GAME_ID}"]["createdAt"]
        first_updated = db._docs[f"games/{GAME_ID}"]["updatedAt"]

        import time; time.sleep(0.01)  # small gap so updatedAt differs
        FirebaseGameService.upsert_canonical_game(
            GAME_ID, GAME_DATE, SEASON, HOME, AWAY, "Final", START
        )
        doc_after = db._docs[f"games/{GAME_ID}"]

        assert doc_after["createdAt"] == first_created, \
            "createdAt must not change on re-upsert"
        assert doc_after["status"] == "Final", "Status should be updated"

    _run_with_mock(run)


# T-12: upsert_calendar_index creates thin doc with correct fields
def t12_upsert_calendar_creates_thin_doc():
    from services.firebase_game_service import FirebaseGameService

    def run(db):
        ok = FirebaseGameService.upsert_calendar_index(
            GAME_ID, GAME_DATE, STATUS, HOME["tricode"], AWAY["tricode"], START
        )
        assert ok, "Expected True return value"
        key = f"calendar/{GAME_DATE}/games/{GAME_ID}"
        doc = db._docs.get(key)
        assert doc is not None, f"Doc not found at {key}"

        # Thin fields only
        assert doc["gameId"] == GAME_ID
        assert doc["status"] == STATUS
        assert doc["homeTeam"] == HOME["tricode"]
        assert doc["awayTeam"] == AWAY["tricode"]
        assert doc["startTime"] == START
        assert doc["refPath"] == f"games/{GAME_ID}", \
            f"refPath mismatch: {doc['refPath']}"
        assert "updatedAt" in doc

        # Must NOT have fat fields
        assert "season" not in doc, "Calendar index must not contain season"
        assert "homeScore" not in doc

    _run_with_mock(run)


# T-13: get_games_for_date returns all games for a date
def t13_get_games_for_date():
    from services.firebase_game_service import FirebaseGameService

    def run(db):
        # Write two games on same date
        FirebaseGameService.upsert_calendar_index(
            "AAA", GAME_DATE, "Final", "LAL", "BOS", START
        )
        FirebaseGameService.upsert_calendar_index(
            "BBB", GAME_DATE, "Final", "GSW", "MEM", START
        )
        # Write one game on a different date — must NOT appear in results
        FirebaseGameService.upsert_calendar_index(
            "CCC", "2026-03-04", "Scheduled", "MIL", "PHX", START
        )

        games = FirebaseGameService.get_games_for_date(GAME_DATE)
        assert len(games) == 2, f"Expected 2 games, got {len(games)}: {games}"
        ids = {g["gameId"] for g in games}
        assert ids == {"AAA", "BBB"}, f"Wrong game IDs: {ids}"

    _run_with_mock(run)


# T-14: get_canonical_game returns None for non-existent game
def t14_get_canonical_not_found():
    from services.firebase_game_service import FirebaseGameService

    def run(db):
        result = FirebaseGameService.get_canonical_game("NONEXISTENT")
        assert result is None, f"Expected None, got {result}"

    _run_with_mock(run)


# T-15: get_canonical_game returns correct data for existing game
def t15_get_canonical_returns_data():
    from services.firebase_game_service import FirebaseGameService

    def run(db):
        FirebaseGameService.upsert_canonical_game(
            GAME_ID, GAME_DATE, SEASON, HOME, AWAY, STATUS, START
        )
        result = FirebaseGameService.get_canonical_game(GAME_ID)
        assert result is not None, "Expected a dict, got None"
        assert result["gameId"] == GAME_ID
        assert result["homeTeam"]["tricode"] == "LAL"

    _run_with_mock(run)


# T-16: update_game_status updates both collections
def t16_update_game_status_both():
    from services.firebase_game_service import FirebaseGameService

    def run(db):
        FirebaseGameService.upsert_canonical_game(
            GAME_ID, GAME_DATE, SEASON, HOME, AWAY, STATUS, START
        )
        FirebaseGameService.upsert_calendar_index(
            GAME_ID, GAME_DATE, STATUS, HOME["tricode"], AWAY["tricode"], START
        )
        FirebaseGameService.update_game_status(GAME_ID, GAME_DATE, "Final")

        assert db._docs[f"games/{GAME_ID}"]["status"] == "Final"
        assert db._docs[f"calendar/{GAME_DATE}/games/{GAME_ID}"]["status"] == "Final"

    _run_with_mock(run)


# T-17: Phase 0 regression — constants + pad_sequence still pass
def t17_phase0_regression():
    from services.firestore_collections import pad_sequence, GAMES, CALENDAR
    assert GAMES == "games"
    assert CALENDAR == "calendar"
    assert pad_sequence(1) == "000001"


# ── Run all ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Phase 1 — Game Service & Calendar Index         ║")
    print("╚══════════════════════════════════════════════════╝\n")

    test("T-10  upsert_canonical_game creates doc", t10_upsert_canonical_creates_doc)
    test("T-11  upsert_canonical_game is idempotent (createdAt preserved)", t11_upsert_canonical_idempotent)
    test("T-12  upsert_calendar_index creates thin doc", t12_upsert_calendar_creates_thin_doc)
    test("T-13  get_games_for_date returns correct games", t13_get_games_for_date)
    test("T-14  get_canonical_game returns None when missing", t14_get_canonical_not_found)
    test("T-15  get_canonical_game returns data", t15_get_canonical_returns_data)
    test("T-16  update_game_status updates both collections", t16_update_game_status_both)
    test("T-17  Phase 0 regression", t17_phase0_regression)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'─' * 52}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ✅ PHASE 1 GATE: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("  ❌ PHASE 1 GATE: FAILURES — DO NOT ADVANCE")
        for name, ok, tb in results:
            if not ok:
                print(f"\n  FAILED: {name}\n{tb}")
        sys.exit(1)
