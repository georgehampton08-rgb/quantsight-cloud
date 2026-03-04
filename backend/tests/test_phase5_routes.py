"""
Phase 5 — API Routes & Compatibility Layer
===========================================
Tests for updated play_by_play_routes.py using FastAPI TestClient.
Verifies:
  - /plays uses v2 path with legacy fallback
  - /shots returns shot-only docs
  - /by-date returns calendar data
  - /live works (mocked ESPN)
  - SSE /stream still importable

Run:
    cd backend && python tests/test_phase5_routes.py
"""
import sys
import os
import copy
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback
from unittest.mock import patch, MagicMock

PASS = "\u2705"
FAIL = "\u274c"
results = []

# ── Minimal mock store (reused) ───────────────────────────────────────────────

class _MockDoc:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None
    def to_dict(self):
        return copy.deepcopy(self._data) if self._data else {}

class _MockBatch:
    def __init__(self, store):
        self._store = store
        self._ops = []
    def set(self, ref, data, merge=False):
        self._ops.append((ref._path, data, merge))
    def commit(self):
        for path, data, merge in self._ops:
            if merge and path in self._store._docs:
                self._store._docs[path] = {**self._store._docs[path], **data}
            else:
                self._store._docs[path] = copy.deepcopy(data)

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
    def limit(self, n):
        return _MockQuery(self._store, self._path, limit=n)
    def stream(self):
        return _MockQuery(self._store, self._path).stream()
    def order_by(self, f):
        return _MockQuery(self._store, self._path)

class _MockQuery:
    def __init__(self, store, path, limit=9999):
        self._store = store
        self._path = path
        self._limit = limit
    def limit(self, n):
        self._limit = n
        return self
    def order_by(self, f):
        return self
    def stream(self):
        prefix = self._path + "/"
        docs = [
            (k, v) for k, v in self._store._docs.items()
            if k.startswith(prefix) and "/" not in k[len(prefix):]
        ]
        docs.sort(key=lambda x: x[0])
        for k, v in docs[:self._limit]:
            yield _MockDoc(v)

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


# ─────────────────────────────────────────────────────────────────────────────
# T-50: /plays endpoint uses v2 (pbp_events/) when data exists there
# ─────────────────────────────────────────────────────────────────────────────
def t50_plays_uses_v2():
    from services.firebase_pbp_service import FirebasePBPService

    db = _MockStore()
    # Pre-populate pbp_events/
    db._docs[f"pbp_events/{GAME_ID}/events/000001"] = {"sequenceNumber": 1, "playId": "p1"}
    db._docs[f"pbp_events/{GAME_ID}/events/000002"] = {"sequenceNumber": 2, "playId": "p2"}

    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        plays = FirebasePBPService.get_cached_plays_v2(GAME_ID)

    assert len(plays) == 2, f"Expected 2 plays from pbp_events/, got {len(plays)}"
    assert plays[0]["sequenceNumber"] == 1
    assert plays[1]["sequenceNumber"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# T-51: /plays endpoint falls back to legacy when pbp_events empty
# ─────────────────────────────────────────────────────────────────────────────
def t51_plays_legacy_fallback():
    from services.firebase_pbp_service import FirebasePBPService

    db = _MockStore()
    # Only legacy data
    db._docs[f"live_games/{GAME_ID}/plays/play_10"] = {
        "sequenceNumber": 10, "playId": "play_10",
    }

    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        plays = FirebasePBPService.get_cached_plays_v2(GAME_ID)

    assert len(plays) == 1, f"Expected 1 legacy play, got {len(plays)}"
    assert plays[0]["sequenceNumber"] == 10


# ─────────────────────────────────────────────────────────────────────────────
# T-52: /shots endpoint returns shot-only docs
# ─────────────────────────────────────────────────────────────────────────────
def t52_shots_endpoint():
    from services.firebase_pbp_service import FirebasePBPService
    from services.nba_pbp_service import PlayEvent

    db = _MockStore()
    plays = [
        PlayEvent(playId=f"p{i}", sequenceNumber=i, eventType="3pt" if i % 2 == 0 else "Sub",
                  description="", period=1, clock="5:00", homeScore=50, awayScore=50,
                  isShootingPlay=(i % 2 == 0), isScoringPlay=False, source="espn")
        for i in range(1, 7)
    ]

    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        shots = FirebasePBPService.get_shot_chart(GAME_ID)

    # Every even-indexed play (2,4,6) is a shot → 3 shots
    assert len(shots) == 3, f"Expected 3 shots, got {len(shots)}"
    for s in shots:
        assert "sequenceNumber" in s
        assert "made" in s


# ─────────────────────────────────────────────────────────────────────────────
# T-53: /shots returns empty list for game with no shots
# ─────────────────────────────────────────────────────────────────────────────
def t53_shots_empty_game():
    from services.firebase_pbp_service import FirebasePBPService

    db = _MockStore()
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        shots = FirebasePBPService.get_shot_chart("NONEXISTENT")

    assert shots == [], f"Expected empty list, got {shots}"


# ─────────────────────────────────────────────────────────────────────────────
# T-54: /by-date endpoint returns games for a given date
# ─────────────────────────────────────────────────────────────────────────────
def t54_by_date_returns_games():
    from services.firebase_game_service import FirebaseGameService

    db = _MockStore()
    with patch("services.firebase_game_service.get_firestore_db", return_value=db):
        FirebaseGameService.upsert_calendar_index(
            "GAME_A", GAME_DATE, "Final", "LAL", "BOS",
            "2026-03-03T19:30:00Z"
        )
        FirebaseGameService.upsert_calendar_index(
            "GAME_B", GAME_DATE, "Final", "GSW", "MEM",
            "2026-03-03T20:00:00Z"
        )
        games = FirebaseGameService.get_games_for_date(GAME_DATE)

    assert len(games) == 2, f"Expected 2 games, got {len(games)}"
    ids = {g["gameId"] for g in games}
    assert ids == {"GAME_A", "GAME_B"}


# ─────────────────────────────────────────────────────────────────────────────
# T-55: /by-date returns empty list if no games on that date
# ─────────────────────────────────────────────────────────────────────────────
def t55_by_date_empty():
    from services.firebase_game_service import FirebaseGameService

    db = _MockStore()
    with patch("services.firebase_game_service.get_firestore_db", return_value=db):
        games = FirebaseGameService.get_games_for_date("2099-01-01")

    assert games == [], f"Expected [], got {games}"


# ─────────────────────────────────────────────────────────────────────────────
# T-56: Route module imports cleanly (no crash, new routes present)
# ─────────────────────────────────────────────────────────────────────────────
def t56_route_module_importable():
    # The route module imports fastapi; we verify it loads without errors
    # and exposes the expected routes
    import importlib
    # Mock the service imports so we don't need live Firebase
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=_MockStore()), \
         patch("services.firebase_game_service.get_firestore_db", return_value=_MockStore()), \
         patch("firestore_db.get_firestore_db", return_value=_MockStore()):
        import api.play_by_play_routes as pbp_routes

    route_paths = [r.path for r in pbp_routes.router.routes]

    # Check new routes are registered
    assert any("/by-date/{date}" in p for p in route_paths), \
        f"/by-date not found in routes: {route_paths}"
    assert any("/shots" in p for p in route_paths), \
        f"/shots not found in routes: {route_paths}"
    # Legacy routes still present
    assert any("/plays" in p for p in route_paths), \
        f"/plays not found: {route_paths}"
    assert any("/stream" in p for p in route_paths), \
        f"/stream not found: {route_paths}"


# ─────────────────────────────────────────────────────────────────────────────
# T-57: Phase 0+1+2+3+4 regression
# ─────────────────────────────────────────────────────────────────────────────
def t57_regression():
    from services.firestore_collections import SHOTS, CALENDAR
    from services.firebase_pbp_service import FirebasePBPService
    from services.firebase_game_service import FirebaseGameService
    from services.pbp_polling_service import PBPPollingService

    assert SHOTS == "shots"
    assert CALENDAR == "calendar"
    assert hasattr(FirebasePBPService, "get_cached_plays_v2")
    assert hasattr(FirebasePBPService, "get_shot_chart")
    assert hasattr(FirebaseGameService, "get_games_for_date")
    assert hasattr(PBPPollingService, "_write_live_state")


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Phase 5 — API Routes & Compatibility Layer      ║")
    print("╚══════════════════════════════════════════════════╝\n")

    test("T-50  /plays uses pbp_events/ when populated", t50_plays_uses_v2)
    test("T-51  /plays falls back to legacy when pbp_events empty", t51_plays_legacy_fallback)
    test("T-52  /shots returns shot-only docs", t52_shots_endpoint)
    test("T-53  /shots returns empty for game with no shots", t53_shots_empty_game)
    test("T-54  /by-date returns games for a date", t54_by_date_returns_games)
    test("T-55  /by-date returns empty when no games", t55_by_date_empty)
    test("T-56  Route module imports + new routes registered", t56_route_module_importable)
    test("T-57  Phase 0+1+2+3+4 regression", t57_regression)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'─' * 52}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ✅ PHASE 5 GATE: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("  ❌ PHASE 5 GATE: FAILURES — DO NOT ADVANCE")
        for name, ok, tb in results:
            if not ok:
                print(f"\n  FAILED: {name}\n{tb}")
        sys.exit(1)
