"""
Phase 4 — Game Finalization & Final Freeze
==========================================
Tests for FirebasePBPService.finalize_game():
  - Creates final_games/{gameId} with correct fields + pointers
  - Marks live_games/{gameId} as done
  - Updates canonical games/ and calendar/ status
  - Idempotent (preserves createdAt on re-finalize)
  - Safety guard: aborts if live state data is incomplete
  - Preserves pre-existing final_games entries

Run:
    cd backend && python tests/test_phase4_finalization.py
"""
import sys
import os
import copy
import time
from datetime import datetime, timezone
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback
from unittest.mock import patch

PASS = "\u2705"
FAIL = "\u274c"
results = []


# ── In-memory mock (self-contained; consistent with Phases 1-3) ───────────────

class _MockDoc:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None
    def to_dict(self):
        return copy.deepcopy(self._data) if self._data else {}

class _MockRef:
    def __init__(self, store, path):
        self._store = store
        self._path = path
    def collection(self, name):
        return _MockCollection(self._store, f"{self._path}/{name}")
    def get(self):
        return _MockDoc(self._store._docs.get(self._path))
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
        return iter([])

class _MockStore:
    def __init__(self):
        self._docs: Dict = {}
    def collection(self, name):
        return _MockCollection(self, name)


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


def _make_live_state(complete: bool = True) -> Dict:
    """Build a realistic live_games doc."""
    doc = {
        "gameDate": GAME_DATE,
        "season": "2025-26",
        "status": "In Progress",
        "period": 4,
        "clock": "0:00",
        "homeTeam": {"tricode": "LAL", "name": "Los Angeles Lakers"},
        "awayTeam": {"tricode": "BOS", "name": "Boston Celtics"},
        "lastSequenceNumber": 487,
        "lastPlayId": "play_487",
        "trackingEnabled": True,
    }
    if complete:
        doc["homeScore"] = 112
        doc["awayScore"] = 108
    return doc


def with_mock(fn):
    db = _MockStore()
    # Also patch game service so it doesn't try to talk to Firestore
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db), \
         patch("services.firebase_game_service.get_firestore_db", return_value=db):
        fn(db)


# ─────────────────────────────────────────────────────────────────────────────
# T-40: finalize_game creates final_games/{id} with all required fields
# ─────────────────────────────────────────────────────────────────────────────
def t40_finalize_creates_final_doc():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        db._docs[f"live_games/{GAME_ID}"] = _make_live_state(complete=True)
        ok = FirebasePBPService.finalize_game(GAME_ID)
        assert ok, "finalize_game should return True on success"

        doc = db._docs.get(f"final_games/{GAME_ID}")
        assert doc is not None, "final_games doc not created"

        required = {
            "gameId", "gameDate", "homeScore", "awayScore",
            "period", "status", "pbpPath", "shotsPath",
            "finalizedAt", "createdAt", "lastSequenceNumber",
        }
        missing = required - set(doc.keys())
        assert not missing, f"Missing fields in final_games doc: {missing}"

        assert doc["homeScore"] == 112
        assert doc["awayScore"] == 108
        assert doc["status"] == "Final"
        assert "pbp_events" in doc["pbpPath"]
        assert "shots" in doc["shotsPath"]

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-41: finalize_game marks live_games/{id} as done
# ─────────────────────────────────────────────────────────────────────────────
def t41_finalize_marks_live_game_done():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        db._docs[f"live_games/{GAME_ID}"] = _make_live_state()
        FirebasePBPService.finalize_game(GAME_ID)

        live = db._docs[f"live_games/{GAME_ID}"]
        assert live.get("trackingEnabled") is False, \
            f"trackingEnabled should be False, got {live.get('trackingEnabled')}"
        assert live.get("status") == "final", \
            f"status should be 'final', got {live.get('status')}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-42: finalize_game updates canonical games/ status
# ─────────────────────────────────────────────────────────────────────────────
def t42_finalize_updates_canonical():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # Pre-populate canonical game
        db._docs[f"games/{GAME_ID}"] = {
            "gameId": GAME_ID, "status": "In Progress", "gameDate": GAME_DATE,
            "createdAt": "2026-03-03T10:00:00Z", "updatedAt": "2026-03-03T10:00:00Z",
        }
        db._docs[f"live_games/{GAME_ID}"] = _make_live_state()

        FirebasePBPService.finalize_game(GAME_ID)

        canonical = db._docs.get(f"games/{GAME_ID}")
        assert canonical is not None
        assert canonical.get("status") == "Final", \
            f"Canonical status should be 'Final', got {canonical.get('status')}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-43: finalize_game updates calendar index status
# ─────────────────────────────────────────────────────────────────────────────
def t43_finalize_updates_calendar():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # Pre-populate calendar index
        db._docs[f"calendar/{GAME_DATE}/games/{GAME_ID}"] = {
            "gameId": GAME_ID, "status": "In Progress",
        }
        db._docs[f"live_games/{GAME_ID}"] = _make_live_state()

        FirebasePBPService.finalize_game(GAME_ID)

        cal = db._docs.get(f"calendar/{GAME_DATE}/games/{GAME_ID}")
        assert cal is not None
        assert cal.get("status") == "Final", \
            f"Calendar status should be 'Final', got {cal.get('status')}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-44: finalize_game is idempotent — createdAt preserved on 2nd call
# ─────────────────────────────────────────────────────────────────────────────
def t44_finalize_idempotent():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        db._docs[f"live_games/{GAME_ID}"] = _make_live_state()

        FirebasePBPService.finalize_game(GAME_ID)
        first_created = db._docs[f"final_games/{GAME_ID}"]["createdAt"]
        first_finalized = db._docs[f"final_games/{GAME_ID}"]["finalizedAt"]

        time.sleep(0.01)
        FirebasePBPService.finalize_game(GAME_ID)
        second_created = db._docs[f"final_games/{GAME_ID}"]["createdAt"]

        assert first_created == second_created, \
            f"createdAt changed on re-finalize: {first_created} -> {second_created}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-45: finalize_game aborts when live state is incomplete (no homeScore)
# ─────────────────────────────────────────────────────────────────────────────
def t45_safety_guard_incomplete_data():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        incomplete = _make_live_state(complete=False)  # no homeScore/awayScore
        db._docs[f"live_games/{GAME_ID}"] = incomplete

        result = FirebasePBPService.finalize_game(GAME_ID)
        assert result is False, \
            f"finalize_game should return False for incomplete data, got {result}"
        assert f"final_games/{GAME_ID}" not in db._docs, \
            "final_games doc should NOT be created with incomplete data"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-46: finalize_game returns False when live_games doc is missing entirely
# ─────────────────────────────────────────────────────────────────────────────
def t46_finalize_missing_live_game():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # No live_games doc at all
        result = FirebasePBPService.finalize_game(GAME_ID)
        assert result is False, \
            f"finalize_game should return False when live_games missing, got {result}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-47: Pre-existing final_games doc is preserved (fields not wiped)
# ─────────────────────────────────────────────────────────────────────────────
def t47_preserves_existing_final_doc():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # Simulate a pre-existing final_games entry (e.g., from migration)
        db._docs[f"final_games/{GAME_ID}"] = {
            "gameId": GAME_ID,
            "createdAt": "2026-01-01T00:00:00Z",   # earlier date
            "customField": "do-not-lose-me",
            "homeScore": 100,
            "awayScore": 90,
        }
        db._docs[f"live_games/{GAME_ID}"] = _make_live_state()

        FirebasePBPService.finalize_game(GAME_ID)

        doc = db._docs[f"final_games/{GAME_ID}"]
        # createdAt must be the ORIGINAL value
        assert doc["createdAt"] == "2026-01-01T00:00:00Z", \
            f"createdAt was overwritten: {doc['createdAt']}"
        # Existing data still there (merge, not overwrite)
        assert doc.get("customField") == "do-not-lose-me", \
            "Existing custom field was lost"
        # But new data is also merged in
        assert doc.get("status") == "Final"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-48: Phase 0+1+2+3 regression
# ─────────────────────────────────────────────────────────────────────────────
def t48_regression():
    from services.firestore_collections import FINAL_GAMES, pad_sequence
    from services.firebase_game_service import FirebaseGameService
    from services.firebase_pbp_service import FirebasePBPService
    from services.pbp_polling_service import PBPPollingService

    assert FINAL_GAMES == "final_games"
    assert pad_sequence(487) == "000487"
    assert hasattr(FirebaseGameService, "update_game_status")
    assert hasattr(FirebasePBPService, "finalize_game")
    assert hasattr(PBPPollingService, "_read_cursor")


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Phase 4 — Game Finalization & Final Freeze      ║")
    print("╚══════════════════════════════════════════════════╝\n")

    test("T-40  finalize creates final_games doc with all fields", t40_finalize_creates_final_doc)
    test("T-41  finalize marks live_games as done", t41_finalize_marks_live_game_done)
    test("T-42  finalize updates canonical games/ status", t42_finalize_updates_canonical)
    test("T-43  finalize updates calendar index status", t43_finalize_updates_calendar)
    test("T-44  finalize is idempotent (createdAt preserved)", t44_finalize_idempotent)
    test("T-45  Safety guard: aborts on incomplete data", t45_safety_guard_incomplete_data)
    test("T-46  finalize returns False when live doc missing", t46_finalize_missing_live_game)
    test("T-47  Pre-existing final_games doc preserved", t47_preserves_existing_final_doc)
    test("T-48  Phase 0+1+2+3 regression", t48_regression)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'─' * 52}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ✅ PHASE 4 GATE: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("  ❌ PHASE 4 GATE: FAILURES — DO NOT ADVANCE")
        for name, ok, tb in results:
            if not ok:
                print(f"\n  FAILED: {name}\n{tb}")
        sys.exit(1)
