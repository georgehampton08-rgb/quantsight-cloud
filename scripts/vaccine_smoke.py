#!/usr/bin/env python3
"""
Vaccine Smoke Test
==================
Validates the Vanguard Vaccine capability:
  1. Module imports (plan engine, patch applier, generator, routes)
  2. Plan engine: generate plan from mock incident
  3. Patch applier: preview + guardrails
  4. Config fields exist
  5. Route registration check

Usage:
  python scripts/vaccine_smoke.py
"""

import sys
import os
import time
import traceback

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

passed = 0
failed = 0
warnings = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def fail(msg):
    global failed
    failed += 1
    print(f"  ❌ {msg}")


def warn(msg):
    global warnings
    warnings += 1
    print(f"  ⚠️  {msg}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Module Imports
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1] Vaccine module imports")
try:
    from vanguard.vaccine.plan_engine import VaccinePlanEngine, get_plan_engine, VaccinePlan
    ok("plan_engine imports OK")
except Exception as e:
    fail(f"plan_engine import failed: {e}")

try:
    from vanguard.vaccine.patch_applier import VaccinePatchApplier, get_patch_applier, PatchSpec
    ok("patch_applier imports OK")
except Exception as e:
    fail(f"patch_applier import failed: {e}")

try:
    from vanguard.vaccine.generator import VaccineGenerator, get_vaccine, CodePatch
    ok("generator imports OK")
except Exception as e:
    fail(f"generator import failed: {e}")

try:
    from vanguard.api.vaccine_routes import router as vaccine_router
    ok(f"vaccine_routes imports OK ({len(vaccine_router.routes)} routes)")
except Exception as e:
    fail(f"vaccine_routes import failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Plan Engine — generate plan from mock incident
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2] VaccinePlanEngine → generate plan")
try:
    engine = get_plan_engine()
    ok(f"PlanEngine v{engine.VERSION} initialized")

    mock_incident = {
        "fingerprint": "test_fp_001",
        "error_type": "AttributeError",
        "error_message": "'NoneType' object has no attribute 'get_scores'",
        "endpoint": "/live/scoreboard",
        "severity": "RED",
        "traceback": (
            'Traceback (most recent call last):\n'
            '  File "/app/vanguard/api/admin_routes.py", line 189, in resolve_incident\n'
            '  File "/app/shared_core/adapters/nba_api_adapter.py", line 420, in fetch_scoreboard_async\n'
            "    results = session.get_scores()\n"
            "AttributeError: 'NoneType' object has no attribute 'get_scores'"
        ),
    }

    plan = engine.generate_plan(mock_incident)

    ok(f"root_cause_bucket: {plan.root_cause_bucket}")
    ok(f"fix_candidates: {len(plan.fix_candidates)}")
    ok(f"risk_score: {plan.risk_score:.2f}")
    ok(f"requires_human_approval: {plan.requires_human_approval}")

    # Verify stacktrace parsing extracted the right files
    files = [c.file for c in plan.fix_candidates]
    if any("nba_api_adapter.py" in f for f in files):
        ok(f"Stacktrace correctly parsed: {files}")
    else:
        warn(f"Stacktrace files unexpected: {files}")

    # Verify plan serialization
    plan_dict = plan.to_dict()
    assert "fingerprint" in plan_dict
    assert "verification_plan" in plan_dict
    assert "rollback_plan" in plan_dict
    ok("plan.to_dict() serialization OK")

except Exception as e:
    fail(f"Plan generation failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Patch Applier — preview (no side effects)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3] VaccinePatchApplier → preview")
try:
    applier = get_patch_applier()
    ok(f"PatchApplier v{applier.VERSION} repo_root={applier.repo_root}")

    preview = applier.preview(
        fingerprint="test_fp_001",
        file_patches=[{
            "path": "vanguard/api/admin_routes.py",
            "original": "def resolve_incident():\n    session.get_scores()\n",
            "patched": "def resolve_incident():\n    if session:\n        session.get_scores()\n",
        }],
        notes="Add null check before calling get_scores",
    )

    ok(f"guardrails_passed: {preview.guardrails_passed}")
    ok(f"diff_hash: {preview.diff_hash}")
    ok(f"files_changed: {len(preview.files_changed)}")
    ok(f"unified_diff length: {len(preview.unified_diff)} chars")

    # Verify to_dict works
    preview_dict = preview.to_dict()
    assert "unified_diff" in preview_dict
    assert "guardrails_passed" in preview_dict
    ok("preview.to_dict() serialization OK")

except Exception as e:
    fail(f"Preview generation failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Guardrails — reject forbidden path
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4] Guardrails enforcement")
try:
    preview_bad = applier.preview(
        fingerprint="test_fp_002",
        file_patches=[{
            "path": ".env",
            "original": "SECRET=old",
            "patched": "SECRET=new",
        }],
        notes="Should be rejected",
    )

    if not preview_bad.guardrails_passed:
        ok(f"Correctly rejected .env: {preview_bad.guardrails_reason}")
    else:
        fail("Guardrails SHOULD have rejected .env edit")

except Exception as e:
    fail(f"Guardrails test failed: {e}")

# Test apply without confirm
try:
    from vanguard.vaccine.patch_applier import PatchSpec, FileChange
    dummy_patch = PatchSpec(
        fingerprint="test_fp_003",
        files_changed=[],
        unified_diff="",
        notes="",
        guardrails_passed=True,
    )
    result = applier.apply(dummy_patch, confirm=False)
    if not result.success and "confirm" in result.message.lower():
        ok("Correctly refused apply without confirm=true")
    else:
        fail(f"Should have refused without confirm: {result.message}")
except Exception as e:
    fail(f"Confirm gate test failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Config Fields
# ══════════════════════════════════════════════════════════════════════════════
print("\n[5] Config fields")
try:
    from vanguard.core.config import VanguardConfig
    config = VanguardConfig()
    ok(f"vaccine_enabled: {config.vaccine_enabled}")
    ok(f"vaccine_max_daily_fixes: {config.vaccine_max_daily_fixes}")
    ok(f"vaccine_min_confidence: {config.vaccine_min_confidence}")
    ok(f"vaccine_repo: {config.vaccine_repo}")
    ok(f"vaccine_base_branch: {config.vaccine_base_branch}")
except Exception as e:
    fail(f"Config fields failed: {e}")
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Generator singleton
# ══════════════════════════════════════════════════════════════════════════════
print("\n[6] VaccineGenerator singleton")
try:
    gen = get_vaccine()
    ok(f"Generator v{gen.VERSION}")
    status = gen.get_status()
    ok(f"enabled={status['enabled']} daily={status['daily_fixes']}/{status['daily_limit']}")
    ok(f"min_confidence={status['min_confidence']}")
except Exception as e:
    fail(f"Generator singleton failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"Vaccine Smoke Test Results")
print(f"{'='*60}")
print(f"Passed:   {passed}")
print(f"Failed:   {failed}")
print(f"Warnings: {warnings}")
print()
if failed == 0:
    print("✅ ALL TESTS PASSED (warnings are informational)")
else:
    print(f"❌ {failed} FAILURE(S)")
sys.exit(0 if failed == 0 else 1)
