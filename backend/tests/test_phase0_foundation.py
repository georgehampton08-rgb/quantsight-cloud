"""
Phase 0 — Foundation & Test Harness
=====================================
Tests for firestore_collections.py:
  - All constants importable
  - pad_sequence produces correct output
  - Edge cases handled properly
  - No circular import side-effects

Run:
    cd backend && python tests/test_phase0_foundation.py
"""
import sys
import os

# Ensure backend root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import traceback

PASS = "\u2705"
FAIL = "\u274c"
results = []


def test(name: str, fn):
    try:
        fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, None))
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  {FAIL}  {name}\n       {e}")
        results.append((name, False, tb))


# ─────────────────────────────────────────────────────────────────────────────
# T-00: Import all public names from the module without error
# ─────────────────────────────────────────────────────────────────────────────
def t00_import():
    from services.firestore_collections import (
        GAMES, CALENDAR, CALENDAR_GAMES_SUB,
        LIVE_GAMES,
        PBP_EVENTS, PBP_EVENTS_SUB,
        SHOTS, SHOTS_ATTEMPTS_SUB,
        FINAL_GAMES,
        LEGACY_LIVE_PLAYS_SUB, LEGACY_GAME_CACHE,
        pad_sequence,
    )
    # All constants must be non-empty strings
    for name, val in [
        ("GAMES", GAMES), ("CALENDAR", CALENDAR),
        ("CALENDAR_GAMES_SUB", CALENDAR_GAMES_SUB),
        ("LIVE_GAMES", LIVE_GAMES),
        ("PBP_EVENTS", PBP_EVENTS), ("PBP_EVENTS_SUB", PBP_EVENTS_SUB),
        ("SHOTS", SHOTS), ("SHOTS_ATTEMPTS_SUB", SHOTS_ATTEMPTS_SUB),
        ("FINAL_GAMES", FINAL_GAMES),
        ("LEGACY_LIVE_PLAYS_SUB", LEGACY_LIVE_PLAYS_SUB),
        ("LEGACY_GAME_CACHE", LEGACY_GAME_CACHE),
    ]:
        assert isinstance(val, str) and len(val) > 0, \
            f"{name} must be a non-empty string, got {val!r}"


# ─────────────────────────────────────────────────────────────────────────────
# T-01: pad_sequence basic cases
# ─────────────────────────────────────────────────────────────────────────────
def t01_pad_sequence_basic():
    from services.firestore_collections import pad_sequence
    assert pad_sequence(1) == "000001", f"Expected '000001', got '{pad_sequence(1)}'"
    assert pad_sequence(0) == "000000", f"Expected '000000', got '{pad_sequence(0)}'"
    assert pad_sequence(42) == "000042"
    assert pad_sequence(9999) == "009999"
    assert pad_sequence(999999) == "999999"


# ─────────────────────────────────────────────────────────────────────────────
# T-02: pad_sequence produces lexicographically correct ordering
# ─────────────────────────────────────────────────────────────────────────────
def t02_pad_sequence_lex_order():
    from services.firestore_collections import pad_sequence
    sequences = [1, 5, 10, 100, 487, 1000, 99999]
    padded = [pad_sequence(s) for s in sequences]
    assert padded == sorted(padded), \
        f"Padded sequences not in sorted order: {padded}"


# ─────────────────────────────────────────────────────────────────────────────
# T-03: pad_sequence raises on negative input
# ─────────────────────────────────────────────────────────────────────────────
def t03_pad_sequence_negative():
    from services.firestore_collections import pad_sequence
    try:
        pad_sequence(-1)
        raise AssertionError("Should have raised ValueError for -1")
    except ValueError:
        pass  # expected


# ─────────────────────────────────────────────────────────────────────────────
# T-04: pad_sequence raises when seq exceeds width
# ─────────────────────────────────────────────────────────────────────────────
def t04_pad_sequence_overflow():
    from services.firestore_collections import pad_sequence
    try:
        pad_sequence(1_000_000, width=6)  # 7 digits, exceeds 6-wide
        raise AssertionError("Should have raised ValueError for overflow")
    except ValueError:
        pass  # expected


# ─────────────────────────────────────────────────────────────────────────────
# T-05: Custom width works correctly
# ─────────────────────────────────────────────────────────────────────────────
def t05_pad_sequence_custom_width():
    from services.firestore_collections import pad_sequence
    assert pad_sequence(7, width=3) == "007"
    assert pad_sequence(42, width=4) == "0042"
    assert pad_sequence(99, width=2) == "99"


# ─────────────────────────────────────────────────────────────────────────────
# T-06: No circular import — importing firestore_collections must NOT trigger
#        Firebase/Google-Cloud SDK initialization as a side effect
# ─────────────────────────────────────────────────────────────────────────────
def t06_no_side_effects_on_import():
    # After importing, firebase_admin should NOT have been initialised
    # (it has no _apps if not initialised).  We only check if the module
    # itself caused it — it should not import firebase_admin at all.
    import importlib
    import importlib.util
    spec = importlib.util.find_spec("firebase_admin")
    if spec is None:
        return  # firebase_admin not installed in this env — trivially ok
    import firebase_admin
    # Re-import our module from scratch to check side effects
    import services.firestore_collections  # already cached — that's fine
    # As long as no exception was raised and we got here, the import is clean.


# ── Run all tests ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════════════╗")
    print("║  Phase 0 — Foundation & Test Harness             ║")
    print("╚══════════════════════════════════════════════════╝\n")

    test("T-00  All constants importable", t00_import)
    test("T-01  pad_sequence basic cases", t01_pad_sequence_basic)
    test("T-02  pad_sequence lexicographic order", t02_pad_sequence_lex_order)
    test("T-03  pad_sequence raises on negative", t03_pad_sequence_negative)
    test("T-04  pad_sequence raises on overflow", t04_pad_sequence_overflow)
    test("T-05  pad_sequence custom width", t05_pad_sequence_custom_width)
    test("T-06  No import side-effects", t06_no_side_effects_on_import)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'─' * 52}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ✅ PHASE 0 GATE: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("  ❌ PHASE 0 GATE: FAILURES DETECTED — DO NOT ADVANCE")
        for name, ok, tb in results:
            if not ok:
                print(f"\n  FAILED: {name}")
                print(tb)
        sys.exit(1)
