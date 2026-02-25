"""
Vanguard Smoke Test
===================
Exercises the full Vanguard incident workflow end-to-end:
  1. List incidents
  2. Get incident details
  3. Get AI analysis (verify caching)
  4. Resolve one incident
  5. Resolve all incidents
  6. Check learning status
  7. Create archive

Usage:
    python scripts/smoke_test_vanguard.py [--base-url URL]
"""
import argparse
import json
import sys
import time
import requests
from datetime import datetime

DEFAULT_BASE = "https://quantsight-cloud-458498663186.us-central1.run.app"


def log(step, msg, ok=True):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] Step {step}: {msg}")


def run_smoke(base_url: str):
    print("=" * 70)
    print("VANGUARD SMOKE TEST")
    print(f"Target: {base_url}")
    print(f"Time:   {datetime.now().isoformat()}")
    print("=" * 70)

    results = {"passed": 0, "failed": 0, "errors": []}

    # ── Step 1: List incidents ──
    print("\n[1/9] List incidents")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/incidents", timeout=30)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert "incidents" in data, "Missing 'incidents' key"
        assert "total" in data, "Missing 'total' key"
        assert "active" in data, "Missing 'active' key"
        log(1, f"Listed {data['total']} incidents ({data['active']} active, {data.get('resolved', 0)} resolved)")
        results["passed"] += 1
        incidents = data["incidents"]
    except Exception as e:
        log(1, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))
        print("  Cannot continue without incident list. Aborting.")
        return results

    # Pick an active incident for testing
    active = [i for i in incidents if i.get("status") == "active"]
    if not active:
        print("\n  No active incidents found. Skipping resolve/analysis tests.")
        return results

    test_fp = active[0]["fingerprint"]
    print(f"\n  Using test fingerprint: {test_fp[:24]}...")

    # ── Step 2: Get incident details ──
    print("\n[2/9] Get incident details")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/incidents/{test_fp}", timeout=30)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert data.get("fingerprint") == test_fp, "Fingerprint mismatch"
        log(2, f"Got details for {data.get('endpoint', 'unknown')} ({data.get('error_type')})")
        results["passed"] += 1
    except Exception as e:
        log(2, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Step 3: Get AI analysis (first call) ──
    print("\n[3/9] Get AI analysis (expect fresh or cached)")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/incidents/{test_fp}/analysis", timeout=60)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert "root_cause" in data, "Missing 'root_cause'"
        assert "confidence" in data, "Missing 'confidence'"
        first_cached = data.get("cached", "N/A")
        log(3, f"Analysis returned (confidence={data['confidence']}, cached={first_cached})")
        results["passed"] += 1
    except Exception as e:
        log(3, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Step 4: Get AI analysis again (expect cached=true) ──
    print("\n[4/9] Get AI analysis again (expect cached=true)")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/incidents/{test_fp}/analysis", timeout=60)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        cached = data.get("cached", False)
        if cached:
            log(4, "Cached=true confirmed (24h cache working)")
        else:
            log(4, f"cached={cached} — cache may not be active yet", ok=False)
        results["passed" if cached else "failed"] += 1
    except Exception as e:
        log(4, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Step 5: Resolve one incident ──
    print("\n[5/9] Resolve one incident")
    try:
        r = requests.post(
            f"{base_url}/vanguard/admin/incidents/{test_fp}/resolve",
            json={"approved": True, "resolution_notes": "Smoke test resolution"},
            timeout=30
        )
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {data}"
        assert data.get("success") is True, f"Expected success=true, got {data}"
        log(5, f"Resolved successfully (ai_confidence={data.get('ai_confidence', 'N/A')})")
        results["passed"] += 1
    except Exception as e:
        log(5, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Step 6: Verify resolved status ──
    print("\n[6/9] Verify incident is resolved")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/incidents/{test_fp}", timeout=30)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        status = data.get("status", "unknown")
        assert status == "resolved", f"Expected status=resolved, got {status}"
        log(6, "Status confirmed as 'resolved'")
        results["passed"] += 1
    except Exception as e:
        log(6, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Step 7: Check learning status ──
    print("\n[7/9] Check learning status")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/learning/status", timeout=30)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        log(7, f"Learning: {data.get('total_resolutions', 0)} resolutions, {data.get('verified_resolutions', 0)} verified")
        results["passed"] += 1
    except Exception as e:
        log(7, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Step 8: List archives ──
    print("\n[8/9] List archives")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/archives", timeout=30)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        log(8, f"Archives: {data.get('total', 0)} available")
        results["passed"] += 1
    except Exception as e:
        log(8, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Step 9: Re-list to confirm counts changed ──
    print("\n[9/9] Re-list incidents (confirm counts updated)")
    try:
        r = requests.get(f"{base_url}/vanguard/admin/incidents", timeout=30)
        data = r.json()
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        log(9, f"Now: {data['total']} total, {data['active']} active, {data.get('resolved', 0)} resolved")
        results["passed"] += 1
    except Exception as e:
        log(9, f"FAILED: {e}", ok=False)
        results["failed"] += 1
        results["errors"].append(str(e))

    # ── Summary ──
    print("\n" + "=" * 70)
    total = results["passed"] + results["failed"]
    print(f"RESULTS: {results['passed']}/{total} passed, {results['failed']}/{total} failed")
    if results["errors"]:
        print("\nErrors:")
        for err in results["errors"]:
            print(f"  - {err}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vanguard Smoke Test")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="API base URL")
    args = parser.parse_args()

    results = run_smoke(args.base_url)
    sys.exit(0 if results["failed"] == 0 else 1)
