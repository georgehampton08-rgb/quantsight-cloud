"""
Phase 2 — PBP Event Stream & Shot Chart Writer
================================================
Tests for firebase_pbp_service.py v2 methods.
Uses an in-memory Firestore mock — completely offline.

Run:
    cd backend && python tests/test_phase2_pbp_refactor.py
"""
import sys
import os
import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback

PASS = "\u2705"
FAIL = "\u274c"
results = []


# ─────────────────────────────────────────────────────────────────────────────
# In-memory Firestore mock (reusable across phases)
# ─────────────────────────────────────────────────────────────────────────────

class _MockBatch:
    """Accumulates writes and commits them to the store atomically."""
    def __init__(self, store):
        self._store = store
        self._ops: List[tuple] = []

    def set(self, ref, data: Dict, merge: bool = False):
        self._ops.append(("set", ref._path, data, merge))

    def commit(self):
        for op, path, data, merge in self._ops:
            if merge and path in self._store._docs:
                merged = {**self._store._docs[path], **data}
                self._store._docs[path] = merged
            else:
                self._store._docs[path] = copy.deepcopy(data)
        self._ops.clear()


class _MockDoc:
    def __init__(self, data=None):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data) if self._data else {}


class _MockCollection:
    def __init__(self, store, path: str):
        self._store = store
        self._path = path

    def document(self, doc_id: str) -> "_MockRef":
        return _MockRef(self._store, f"{self._path}/{doc_id}")

    def limit(self, n: int) -> "_MockQuery":
        return _MockQuery(self._store, self._path, limit=n)

    def stream(self):
        return _MockQuery(self._store, self._path).stream()

    def order_by(self, field: str) -> "_MockQuery":
        return _MockQuery(self._store, self._path, order_field=field)


class _MockQuery:
    def __init__(self, store, path: str, limit: int = 9999, order_field: str = None):
        self._store = store
        self._path = path
        self._limit = limit
        self._order = order_field

    def limit(self, n: int) -> "_MockQuery":
        self._limit = n
        return self

    def order_by(self, field: str) -> "_MockQuery":
        self._order = field
        return self

    def stream(self):
        prefix = self._path + "/"
        docs = []
        for k, v in self._store._docs.items():
            if k.startswith(prefix) and "/" not in k[len(prefix):]:
                docs.append((k, v))
        if self._order:
            docs.sort(key=lambda x: x[1].get(self._order, 0))
        else:
            docs.sort(key=lambda x: x[0])  # lexicographic by doc path = correct for padded IDs
        for k, v in docs[: self._limit]:
            yield _MockDoc(v)


class _MockRef:
    def __init__(self, store, path: str):
        self._store = store
        self._path = path

    def collection(self, name: str) -> _MockCollection:
        return _MockCollection(self._store, f"{self._path}/{name}")

    def get(self) -> _MockDoc:
        return _MockDoc(self._store._docs.get(self._path))

    def set(self, data: Dict, merge: bool = False):
        if merge and self._path in self._store._docs:
            merged = {**self._store._docs[self._path], **data}
            self._store._docs[self._path] = merged
        else:
            self._store._docs[self._path] = copy.deepcopy(data)


class _MockStore:
    def __init__(self):
        self._docs: Dict[str, Dict] = {}

    def collection(self, name: str) -> _MockCollection:
        return _MockCollection(self, name)

    def batch(self) -> _MockBatch:
        return _MockBatch(self)


# ─────────────────────────────────────────────────────────────────────────────
# PlayEvent factory helpers
# ─────────────────────────────────────────────────────────────────────────────

from services.nba_pbp_service import PlayEvent

GAME_ID = "0022500789"

def make_play(seq: int, is_shot: bool = False, is_scoring: bool = False) -> PlayEvent:
    return PlayEvent(
        playId=f"play_{seq}",
        sequenceNumber=seq,
        eventType="Three Point Jumper" if is_shot else "Substitution",
        description=f"Play {seq}",
        period=2,
        clock="5:00",
        homeScore=50 + seq if is_shot else 50,
        awayScore=48,
        teamId="1610612744",
        teamTricode="GSW",
        primaryPlayerId="201939" if is_shot else None,
        primaryPlayerName="Stephen Curry" if is_shot else None,
        isScoringPlay=is_scoring,
        isShootingPlay=is_shot,
        pointsValue=3 if (is_shot and is_scoring) else 0,
        coordinateX=23.5 if is_shot else None,
        coordinateY=8.2 if is_shot else None,
        source="espn",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────────────

def test(name, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, None))
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  {FAIL}  {name}\n       {e}")
        results.append((name, False, tb))


from unittest.mock import patch


def with_mock(fn):
    db = _MockStore()
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        fn(db)


# ─────────────────────────────────────────────────────────────────────────────
# T-20: save_plays_batch_v2 writes to pbp_events/ with pad_sequence doc IDs
# ─────────────────────────────────────────────────────────────────────────────
def t20_v2_writes_to_pbp_events():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        plays = [make_play(1), make_play(42), make_play(100)]
        n = FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        assert n == 3, f"Expected 3 written, got {n}"

        # Check doc IDs are correctly padded
        assert f"pbp_events/{GAME_ID}/events/000001" in db._docs
        assert f"pbp_events/{GAME_ID}/events/000042" in db._docs
        assert f"pbp_events/{GAME_ID}/events/000100" in db._docs

        # Verify content
        doc = db._docs[f"pbp_events/{GAME_ID}/events/000042"]
        assert doc["sequenceNumber"] == 42
        assert doc["playId"] == "play_42"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-21: save_plays_batch_v2 extracts shots to shots/ collection
# ─────────────────────────────────────────────────────────────────────────────
def t21_v2_extracts_shots():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # 2 shot plays + 1 non-shot
        plays = [
            make_play(10, is_shot=True, is_scoring=True),
            make_play(20, is_shot=False),
            make_play(30, is_shot=True, is_scoring=False),
        ]
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)

        # shots/ should only have seqs 10 and 30
        assert f"shots/{GAME_ID}/attempts/000010" in db._docs, "Shot at seq 10 missing"
        assert f"shots/{GAME_ID}/attempts/000030" in db._docs, "Shot at seq 30 missing"
        assert f"shots/{GAME_ID}/attempts/000020" not in db._docs, \
            "Non-shot seq 20 must NOT be in shots/"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-22: Non-shooting plays do NOT appear in shots/
# ─────────────────────────────────────────────────────────────────────────────
def t22_non_shot_not_in_shots():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        plays = [make_play(i, is_shot=False) for i in range(1, 6)]
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)

        shot_keys = [k for k in db._docs if k.startswith(f"shots/{GAME_ID}")]
        assert len(shot_keys) == 0, f"Expected 0 shot docs, found: {shot_keys}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-23: save_plays_batch_v2 is idempotent (same batch twice = same count)
# ─────────────────────────────────────────────────────────────────────────────
def t23_v2_idempotent():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        plays = [make_play(i, is_shot=(i % 2 == 0)) for i in range(1, 11)]
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        pbp_count_1 = len([k for k in db._docs if k.startswith(f"pbp_events/{GAME_ID}")])
        shot_count_1 = len([k for k in db._docs if k.startswith(f"shots/{GAME_ID}")])

        # Write same batch again
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        pbp_count_2 = len([k for k in db._docs if k.startswith(f"pbp_events/{GAME_ID}")])
        shot_count_2 = len([k for k in db._docs if k.startswith(f"shots/{GAME_ID}")])

        assert pbp_count_1 == pbp_count_2, \
            f"PBP count changed: {pbp_count_1} -> {pbp_count_2}"
        assert shot_count_1 == shot_count_2, \
            f"Shot count changed: {shot_count_1} -> {shot_count_2}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-24: extract_shot_doc returns correct lean fields
# ─────────────────────────────────────────────────────────────────────────────
def t24_extract_shot_doc_fields():
    from services.firebase_pbp_service import FirebasePBPService

    play = make_play(42, is_shot=True, is_scoring=True)
    shot = FirebasePBPService.extract_shot_doc(play)

    required = {
        "sequenceNumber", "playerId", "playerName", "teamId", "teamTricode",
        "shotType", "distance", "made", "period", "clock", "x", "y",
        "pointsValue", "ts",
    }
    missing = required - set(shot.keys())
    assert not missing, f"Shot doc missing fields: {missing}"

    # Check values
    assert shot["sequenceNumber"] == 42
    assert shot["made"] == True  # isScoringPlay -> made
    assert shot["x"] == 23.5
    assert shot["playerId"] == "201939"

    # Must NOT contain full rawData or other heavy fields
    assert "rawData" not in shot, "Shot doc must not contain rawData"
    assert "description" not in shot, "Shot doc must not contain description"


# ─────────────────────────────────────────────────────────────────────────────
# T-25: get_cached_plays_v2 returns plays in ascending sequence order
# ─────────────────────────────────────────────────────────────────────────────
def t25_get_cached_plays_v2_ordered():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # Write out of order
        plays = [make_play(100), make_play(1), make_play(50)]
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)

        fetched = FirebasePBPService.get_cached_plays_v2(GAME_ID)
        seqs = [p["sequenceNumber"] for p in fetched]
        assert seqs == sorted(seqs), \
            f"Plays not in sorted order: {seqs}"
        assert seqs == [1, 50, 100], f"Wrong sequences: {seqs}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-26: get_cached_plays_v2 falls back to legacy when pbp_events is empty
# ─────────────────────────────────────────────────────────────────────────────
def t26_get_cached_plays_v2_legacy_fallback():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # Manually write to legacy path only
        db._docs[f"live_games/{GAME_ID}/plays/play_5"] = {
            "playId": "play_5",
            "sequenceNumber": 5,
            "eventType": "Sub",
            "description": "legacy play",
            "period": 1,
            "clock": "11:00",
            "homeScore": 0,
            "awayScore": 0,
            "source": "espn",
        }

        # Mock the order_by fallback — our mock already supports it
        fetched = FirebasePBPService.get_cached_plays_v2(GAME_ID)
        assert len(fetched) == 1, f"Expected 1 legacy play, got {len(fetched)}"
        assert fetched[0]["sequenceNumber"] == 5

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-27: get_shot_chart returns only shot docs for a game
# ─────────────────────────────────────────────────────────────────────────────
def t27_get_shot_chart():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        plays = [
            make_play(1, is_shot=True),
            make_play(2, is_shot=False),
            make_play(3, is_shot=True),
            make_play(4, is_shot=True),
        ]
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        shots = FirebasePBPService.get_shot_chart(GAME_ID)
        assert len(shots) == 3, f"Expected 3 shots, got {len(shots)}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-28: large batch (600 plays) splits correctly and all plays written
# ─────────────────────────────────────────────────────────────────────────────
def t28_large_batch_splitting():
    from services.firebase_pbp_service import FirebasePBPService

    def run(db):
        # Every other play is a shot — 300 shots + 300 non-shots = 300*2 + 300 = 900 ops
        # Must split into at least 4 sub-batches of 225
        plays = [make_play(i, is_shot=(i % 2 == 0)) for i in range(1, 601)]
        n = FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        assert n == 600, f"Expected 600 written, got {n}"

        pbp_keys = [k for k in db._docs if k.startswith(f"pbp_events/{GAME_ID}/events/")]
        shot_keys = [k for k in db._docs if k.startswith(f"shots/{GAME_ID}/attempts/")]
        assert len(pbp_keys) == 600, f"Expected 600 pbp docs, got {len(pbp_keys)}"
        assert len(shot_keys) == 300, f"Expected 300 shot docs, got {len(shot_keys)}"

    with_mock(run)


# ─────────────────────────────────────────────────────────────────────────────
# T-29: Phase 0 + 1 regression
# ─────────────────────────────────────────────────────────────────────────────
def t29_regression_phases_0_1():
    from services.firestore_collections import pad_sequence, GAMES, CALENDAR
    from services.firebase_game_service import FirebaseGameService

    assert pad_sequence(7) == "000007"
    assert GAMES == "games"
    assert CALENDAR == "calendar"
    # FirebaseGameService importable — no crash
    assert hasattr(FirebaseGameService, "upsert_canonical_game")


# ── Run all ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Phase 2 — PBP Event Stream & Shot Chart         ║")
    print("╚══════════════════════════════════════════════════╝\n")

    test("T-20  save_plays_batch_v2 writes to pbp_events/", t20_v2_writes_to_pbp_events)
    test("T-21  save_plays_batch_v2 extracts shots", t21_v2_extracts_shots)
    test("T-22  Non-shooting plays NOT in shots/", t22_non_shot_not_in_shots)
    test("T-23  save_plays_batch_v2 is idempotent", t23_v2_idempotent)
    test("T-24  extract_shot_doc has correct lean fields", t24_extract_shot_doc_fields)
    test("T-25  get_cached_plays_v2 returns ordered plays", t25_get_cached_plays_v2_ordered)
    test("T-26  get_cached_plays_v2 legacy fallback", t26_get_cached_plays_v2_legacy_fallback)
    test("T-27  get_shot_chart returns shot docs only", t27_get_shot_chart)
    test("T-28  Large batch (600 plays) splits correctly", t28_large_batch_splitting)
    test("T-29  Phase 0+1 regression", t29_regression_phases_0_1)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'─' * 52}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ✅ PHASE 2 GATE: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("  ❌ PHASE 2 GATE: FAILURES — DO NOT ADVANCE")
        for name, ok, tb in results:
            if not ok:
                print(f"\n  FAILED: {name}\n{tb}")
        sys.exit(1)
