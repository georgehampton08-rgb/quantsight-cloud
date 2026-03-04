"""
Phase 7 — Master Integration Test
====================================
End-to-end pipeline test exercising the complete flow:
  1. Create canonical game + calendar index
  2. Write 10 PBP events (3 with shots)
  3. Write live state with cursor
  4. Read plays via v2 → correct count + order
  5. Read shot chart → 3 shots
  6. Finalize game → final_games/ created, live marked done
  7. Read games by date → returns the game
  8. Re-finalize (idempotency) → no data loss

ALL tests are offline (in-memory mock DB).

Run:
    cd backend && python tests/test_phase7_integration.py
"""
import sys
import os
import copy
import time
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback

PASS = "\u2705"
FAIL = "\u274c"
results = []


# ── Shared mock DB (reused, consistent with all prior phases) ─────────────────

class _MockDoc:
    def __init__(self, data=None, doc_id=""):
        self._data = data
        self.id = doc_id
        self.exists = data is not None
    def to_dict(self):
        return copy.deepcopy(self._data) if self._data else {}

class _MockBatch:
    def __init__(self, store):
        self._store = store
        self._ops = []
    def set(self, ref, data, merge=False):
        self._ops.append(("set", ref._path, data, merge))
    def commit(self):
        for _, path, data, merge in self._ops:
            if merge and path in self._store._docs:
                self._store._docs[path] = {**self._store._docs[path], **data}
            else:
                self._store._docs[path] = copy.deepcopy(data)
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
        docs = [(k, v) for k, v in self._store._docs.items()
                if k.startswith(prefix) and "/" not in k[len(prefix):]]
        docs.sort(key=lambda x: x[0])
        for k, v in docs[:self._limit]:
            yield _MockDoc(v, k.split("/")[-1])

class _MockCollection:
    def __init__(self, store, path):
        self._store = store
        self._path = path
    def document(self, doc_id):
        return _MockRef(self._store, f"{self._path}/{doc_id}")
    def stream(self):
        return _MockQuery(self._store, self._path).stream()
    def limit(self, n):
        return _MockQuery(self._store, self._path, limit=n)
    def order_by(self, f):
        return _MockQuery(self._store, self._path)

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
SEASON = "2025-26"
HOME = {"tricode": "LAL", "name": "Los Angeles Lakers", "teamId": "1610612747"}
AWAY = {"tricode": "BOS", "name": "Boston Celtics", "teamId": "1610612738"}


# ── Build shared state ─────────────────────────────────────────────────────────

def build_full_scenario():
    """
    Returns (db, plays) representing a complete game scenario:
      - 10 plays total: plays 3, 6, 9 are shots
      - Live state pre-populated (needed for finalize)
    """
    db = _MockStore()

    from services.nba_pbp_service import PlayEvent

    plays = []
    for i in range(1, 11):
        is_shot = (i % 3 == 0)
        p = PlayEvent(
            playId=f"play_{i}",
            sequenceNumber=i,
            eventType="Three Point Jumper" if is_shot else "Substitution",
            description=f"Event {i}",
            period=2 if i <= 5 else 3,
            clock=f"5:{60-i:02d}",
            homeScore=50 + i,
            awayScore=48,
            teamId="1610612747",
            teamTricode="LAL",
            primaryPlayerId="2544" if is_shot else None,
            primaryPlayerName="LeBron James" if is_shot else None,
            isShootingPlay=is_shot,
            isScoringPlay=is_shot,
            pointsValue=3 if is_shot else 0,
            coordinateX=10.0 + i if is_shot else None,
            coordinateY=5.0 if is_shot else None,
            source="espn",
        )
        plays.append(p)

    # Pre-populate live doc for finalize
    db._docs[f"live_games/{GAME_ID}"] = {
        "gameId": GAME_ID,
        "gameDate": GAME_DATE,
        "season": SEASON,
        "homeTeam": HOME,
        "awayTeam": AWAY,
        "status": "In Progress",
        "homeScore": 112,
        "awayScore": 108,
        "period": 4,
        "clock": "0:00",
        "lastSequenceNumber": 0,
        "trackingEnabled": True,
        "startTime": f"{GAME_DATE}T19:30:00Z",
    }

    return db, plays


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: canonical game + calendar index
# ─────────────────────────────────────────────────────────────────────────────
def step1_canonical_and_calendar():
    from services.firebase_game_service import FirebaseGameService

    db, _ = build_full_scenario()
    with patch("services.firebase_game_service.get_firestore_db", return_value=db):
        FirebaseGameService.upsert_canonical_game(
            GAME_ID, GAME_DATE, SEASON, HOME, AWAY, "In Progress",
            f"{GAME_DATE}T19:30:00Z"
        )
        FirebaseGameService.upsert_calendar_index(
            GAME_ID, GAME_DATE, "In Progress", HOME["tricode"], AWAY["tricode"],
            f"{GAME_DATE}T19:30:00Z"
        )

    assert f"games/{GAME_ID}" in db._docs, "Canonical game doc missing"
    assert f"calendar/{GAME_DATE}/games/{GAME_ID}" in db._docs, "Calendar doc missing"

    # Validate canonical fields
    g = db._docs[f"games/{GAME_ID}"]
    assert g["gameDate"] == GAME_DATE
    assert g["season"] == SEASON

    # Validate calendar is thin
    c = db._docs[f"calendar/{GAME_DATE}/games/{GAME_ID}"]
    assert c["refPath"] == f"games/{GAME_ID}"
    assert "season" not in c


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: write 10 PBP events (3 shots)
# ─────────────────────────────────────────────────────────────────────────────
def step2_write_pbp_and_shots():
    from services.firebase_pbp_service import FirebasePBPService

    db, plays = build_full_scenario()
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        n = FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)

    assert n == 10, f"Expected 10 plays written, got {n}"

    pbp_keys = [k for k in db._docs if k.startswith(f"pbp_events/{GAME_ID}/events/")]
    shot_keys = [k for k in db._docs if k.startswith(f"shots/{GAME_ID}/attempts/")]
    assert len(pbp_keys) == 10, f"Expected 10 pbp docs, got {len(pbp_keys)}"
    assert len(shot_keys) == 3, f"Expected 3 shot docs (seqs 3,6,9), got {len(shot_keys)}"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: write live state with cursor
# ─────────────────────────────────────────────────────────────────────────────
def step3_write_live_state():
    from services.firebase_pbp_service import FirebasePBPService
    from services.pbp_polling_service import PBPPollingService
    from services.nba_pbp_service import PlayEvent

    db, plays = build_full_scenario()
    last_play = plays[-1]

    with patch("services.pbp_polling_service.get_firestore_db", return_value=db):
        PBPPollingService._write_live_state(GAME_ID, 10, last_play)

    live = db._docs.get(f"live_games/{GAME_ID}")
    assert live is not None
    assert live["lastSequenceNumber"] == 10, f"cursor wrong: {live.get('lastSequenceNumber')}"
    assert live["trackingEnabled"] is True


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: read plays via v2 — correct count + ascending order
# ─────────────────────────────────────────────────────────────────────────────
def step4_read_plays_v2():
    from services.firebase_pbp_service import FirebasePBPService

    db, plays = build_full_scenario()
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        fetched = FirebasePBPService.get_cached_plays_v2(GAME_ID)

    assert len(fetched) == 10, f"Expected 10 plays, got {len(fetched)}"
    seqs = [p["sequenceNumber"] for p in fetched]
    assert seqs == sorted(seqs), f"Plays not in order: {seqs}"
    assert seqs[0] == 1 and seqs[-1] == 10


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: read shot chart → exactly 3 shots
# ─────────────────────────────────────────────────────────────────────────────
def step5_read_shot_chart():
    from services.firebase_pbp_service import FirebasePBPService

    db, plays = build_full_scenario()
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db):
        FirebasePBPService.save_plays_batch_v2(GAME_ID, plays)
        shots = FirebasePBPService.get_shot_chart(GAME_ID)

    assert len(shots) == 3, f"Expected 3 shots, got {len(shots)}"
    shot_seqs = sorted(s["sequenceNumber"] for s in shots)
    assert shot_seqs == [3, 6, 9], f"Wrong shot sequences: {shot_seqs}"

    for s in shots:
        assert s["x"] is not None, "Shot x-coord missing"
        assert s["made"] is True, "All test shots are scoring"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: finalize game → final_games/ created, live marked done
# ─────────────────────────────────────────────────────────────────────────────
def step6_finalize_game():
    from services.firebase_pbp_service import FirebasePBPService

    db, _ = build_full_scenario()
    # live_games doc has complete scores (from build_full_scenario)
    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db), \
         patch("services.firebase_game_service.get_firestore_db", return_value=db):
        result = FirebasePBPService.finalize_game(GAME_ID)

    assert result is True, f"finalize_game returned {result}"
    assert f"final_games/{GAME_ID}" in db._docs, "final_games doc missing"

    final = db._docs[f"final_games/{GAME_ID}"]
    assert final["homeScore"] == 112
    assert final["awayScore"] == 108
    assert final["status"] == "Final"
    assert "pbp_events" in final["pbpPath"]
    assert "shots" in final["shotsPath"]

    live = db._docs[f"live_games/{GAME_ID}"]
    assert live["trackingEnabled"] is False
    assert live["status"] == "final"


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7: calendar returns the game for the date
# ─────────────────────────────────────────────────────────────────────────────
def step7_games_by_date():
    from services.firebase_game_service import FirebaseGameService

    db, _ = build_full_scenario()
    with patch("services.firebase_game_service.get_firestore_db", return_value=db):
        FirebaseGameService.upsert_calendar_index(
            GAME_ID, GAME_DATE, "Final", "LAL", "BOS", f"{GAME_DATE}T19:30:00Z"
        )
        games = FirebaseGameService.get_games_for_date(GAME_DATE)

    assert len(games) == 1, f"Expected 1 game, got {len(games)}"
    assert games[0]["gameId"] == GAME_ID


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8: re-finalize → idempotent, no data loss
# ─────────────────────────────────────────────────────────────────────────────
def step8_re_finalize_idempotent():
    from services.firebase_pbp_service import FirebasePBPService

    db, _ = build_full_scenario()

    with patch("services.firebase_pbp_service.get_firestore_db", return_value=db), \
         patch("services.firebase_game_service.get_firestore_db", return_value=db):
        FirebasePBPService.finalize_game(GAME_ID)
        first_created = db._docs[f"final_games/{GAME_ID}"]["createdAt"]

        time.sleep(0.01)
        FirebasePBPService.finalize_game(GAME_ID)
        second_created = db._docs[f"final_games/{GAME_ID}"]["createdAt"]

    assert first_created == second_created, \
        f"createdAt changed on re-finalize: {first_created} != {second_created}"

    final = db._docs[f"final_games/{GAME_ID}"]
    assert final["homeScore"] == 112, "homeScore lost on re-finalize"
    assert final["status"] == "Final"


# ── FULL SUITE RUNNER ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Phase 7 — Master Integration Test               ║")
    print("╚══════════════════════════════════════════════════╝\n")

    test("Step 1  Canonical game + calendar index created", step1_canonical_and_calendar)
    test("Step 2  10 PBP events written (3 shots extracted)", step2_write_pbp_and_shots)
    test("Step 3  Live state written with cursor=10", step3_write_live_state)
    test("Step 4  Plays read back in ascending order", step4_read_plays_v2)
    test("Step 5  Shot chart returns exactly 3 shots (seqs 3,6,9)", step5_read_shot_chart)
    test("Step 6  Finalize → final_games created, live marked done", step6_finalize_game)
    test("Step 7  Calendar returns game for date", step7_games_by_date)
    test("Step 8  Re-finalize is idempotent (no data loss)", step8_re_finalize_idempotent)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'─' * 52}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ✅ PHASE 7 GATE: ALL TESTS PASSED")
        print("  ✅ FULL PIPELINE INTEGRATION VERIFIED")
        sys.exit(0)
    else:
        print("  ❌ PHASE 7 GATE: FAILURES — DO NOT DEPLOY")
        for name, ok, tb in results:
            if not ok:
                print(f"\n  FAILED: {name}\n{tb}")
        sys.exit(1)
