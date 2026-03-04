"""
Full Phase Test Suite Runner
==============================
Runs all phase test files (0-7) in order, reports pass/fail per phase.
Exit code 0 = all phases passed, 1 = any failures.

Run:
    cd backend && python tests/run_all_phases.py
"""
import sys
import os
import subprocess
import copy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PHASES = [
    ("Phase 0 — Foundation & Test Harness",       "tests/test_phase0_foundation.py"),
    ("Phase 1 — Game Service & Calendar Index",   "tests/test_phase1_game_service.py"),
    ("Phase 2 — PBP Event Stream & Shot Chart",   "tests/test_phase2_pbp_refactor.py"),
    ("Phase 3 — Live State & Polling Refactor",   "tests/test_phase3_polling.py"),
    ("Phase 4 — Game Finalization",               "tests/test_phase4_finalization.py"),
    ("Phase 5 — API Routes & Compatibility",      "tests/test_phase5_routes.py"),
    ("Phase 6 — Migration Script",                "tests/test_phase6_migration.py"),
    ("Phase 7 — Master Integration",              "tests/test_phase7_integration.py"),
]

PASS = "\u2705"
FAIL = "\u274c"

summary = []

print("\n" + "="*62)
print("  QuantSight Firestore Schema — Full Phase Test Suite")
print("="*62 + "\n")

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for label, path in PHASES:
    full_path = os.path.join(backend_dir, path)
    try:
        result = subprocess.run(
            [sys.executable, full_path],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=120,
        )
        passed = result.returncode == 0
        icon = PASS if passed else FAIL
        status = "PASS" if passed else "FAIL"
        print(f"  {icon}  {label}")
        if not passed:
            # Print only the last meaningful lines from stdout
            lines = [l for l in result.stdout.splitlines() if l.strip()]
            for line in lines[-5:]:
                print(f"       {line}")
            if result.stderr.strip():
                for line in result.stderr.splitlines()[-3:]:
                    print(f"       STDERR: {line}")
        summary.append((label, passed))
    except subprocess.TimeoutExpired:
        print(f"  {FAIL}  {label}  [TIMEOUT]")
        summary.append((label, False))
    except Exception as e:
        print(f"  {FAIL}  {label}  [{e}]")
        summary.append((label, False))

passed_count = sum(1 for _, ok in summary if ok)
total = len(summary)

print(f"\n{'─'*62}")
print(f"  Result: {passed_count}/{total} phases passed")
print()

if passed_count == total:
    print("  ✅ ALL PHASES PASSED — SCHEMA REFACTOR COMPLETE")
    sys.exit(0)
else:
    print("  ❌ FAILURES DETECTED:")
    for label, ok in summary:
        if not ok:
            print(f"     ❌ {label}")
    sys.exit(1)
