"""
Vanguard Backend Incident Verification
=======================================
Trigger real errors on actual backend endpoints and verify incident capture.
"""
import requests
import json
import time
from datetime import datetime

BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

print("=" * 80)
print("VANGUARD BACKEND INCIDENT VERIFICATION")
print("=" * 80)
print(f"Target: {BASE_URL}")
print(f"Time: {datetime.now().isoformat()}")
print("=" * 80)

# Track results
results = []

# TEST 1: Invalid player ID (should cause 404 or 500)
print("\n[1/6] Testing invalid player ID...")
try:
    r = requests.get(f"{BASE_URL}/player/INVALID_PLAYER_999999")
    results.append({
        "test": "Invalid Player ID",
        "endpoint": "/player/INVALID_PLAYER_999999",
        "status": r.status_code,
        "request_id": r.headers.get("X-Request-ID"),
        "captured": r.status_code in [404, 500]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"test": "Invalid Player ID", "error": str(e)})

time.sleep(2)

# TEST 2: Invalid team abbreviation
print("\n[2/6] Testing invalid team abbreviation...")
try:
    r = requests.get(f"{BASE_URL}/teams/INVALID_TEAM")
    results.append({
        "test": "Invalid Team",
        "endpoint": "/teams/INVALID_TEAM",
        "status": r.status_code,
        "request_id": r.headers.get("X-Request-ID"),
        "captured": r.status_code in [404, 500]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"test": "Invalid Team", "error": str(e)})

time.sleep(2)

# TEST 3: Invalid roster ID
print("\n[3/6] Testing invalid roster ID...")
try:
    r = requests.get(f"{BASE_URL}/roster/999999")
    results.append({
        "test": "Invalid Roster",
        "endpoint": "/roster/999999",
        "status": r.status_code,
        "request_id": r.headers.get("X-Request-ID"),
        "captured": r.status_code in [404, 500]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"test": "Invalid Roster", "error": str(e)})

time.sleep(2)

# TEST 4: Invalid boxscore game ID
print("\n[4/6] Testing invalid boxscore game ID...")
try:
    r = requests.get(f"{BASE_URL}/boxscore/INVALID_GAME_ID")
    results.append({
        "test": "Invalid Boxscore",
        "endpoint": "/boxscore/INVALID_GAME_ID",
        "status": r.status_code,
        "request_id": r.headers.get("X-Request-ID"),
        "captured": r.status_code in [404, 500]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"test": "Invalid Boxscore", "error": str(e)})

time.sleep(2)

# TEST 5: POST with invalid JSON to matchup endpoint
print("\n[5/6] Testing invalid POST to matchup endpoint...")
try:
    r = requests.post(
        f"{BASE_URL}/matchup/analyze",
        json={"invalid": "data", "missing_required_fields": True}
    )
    results.append({
        "test": "Invalid Matchup POST",
        "endpoint": "/matchup/analyze",
        "status": r.status_code,
        "request_id": r.headers.get("X-Request-ID"),
        "captured": r.status_code in [400, 404, 422, 500]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"test": "Invalid Matchup POST", "error": str(e)})

time.sleep(2)

# TEST 6: Non-existent endpoint
print("\n[6/6] Testing non-existent endpoint...")
try:
    r = requests.get(f"{BASE_URL}/api/this/endpoint/does/not/exist")
    results.append({
        "test": "Non-existent Endpoint",
        "endpoint": "/api/this/endpoint/does/not/exist",
        "status": r.status_code,
        "request_id": r.headers.get("X-Request-ID"),
        "captured": r.status_code == 404
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"test": "Non-existent Endpoint", "error": str(e)})

# Wait for incidents to be processed
print("\n" + "=" * 80)
print("Waiting 10 seconds for Vanguard to process incidents...")
print("=" * 80)
time.sleep(10)

# Check Vanguard health for incident counts
print("\n[VERIFICATION] Checking Vanguard health endpoint...")
try:
    r = requests.get(f"{BASE_URL}/vanguard/health")
    health = r.json()
    
    print(f"\nVanguard Status: {health.get('status')}")
    print(f"Mode: {health.get('mode')}")
    print(f"Redis Connected: {health.get('bootstrap', {}).get('redis_connected')}")
    
    incidents = health.get('incidents', {})
    print(f"\nINCIDENT COUNTS:")
    print(f"  Total: {incidents.get('total', 0)}")
    print(f"  Active: {incidents.get('active', 0)}")
    print(f"  Resolved: {incidents.get('resolved', 0)}")
    
    subsystems = health.get('subsystems', {})
    print(f"\nSUBSYSTEMS:")
    print(f"  Profiler: {subsystems.get('profiler', {}).get('enabled')} ({subsystems.get('profiler', {}).get('model')})")
    print(f"  Surgeon: {subsystems.get('surgeon', {}).get('enabled')}")
    print(f"  Archivist: {subsystems.get('archivist', {}).get('enabled')}")
    
except Exception as e:
    print(f"  Error checking health: {e}")

# Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

captured_count = sum(1 for r in results if r.get("captured", False))
print(f"Tests run: {len(results)}")
print(f"Errors triggered: {captured_count}")
print(f"Request IDs generated: {sum(1 for r in results if r.get('request_id'))}")

# Save results
with open("backend_incident_verification.json", "w") as f:
    json.dump({
        "test_run": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "total_tests": len(results),
        "errors_captured": captured_count,
        "results": results,
        "vanguard_health": health if 'health' in locals() else None
    }, f, indent=2)

print(f"\nResults saved to: backend_incident_verification.json")

# Print each result
print("\n" + "=" * 80)
print("DETAILED RESULTS")
print("=" * 80)
for i, result in enumerate(results, 1):
    print(f"\n{i}. {result.get('test', 'UNKNOWN')}")
    print(f"   Endpoint: {result.get('endpoint', 'N/A')}")
    print(f"   Status: {result.get('status', 'ERROR')}")
    print(f"   Request ID: {result.get('request_id', 'N/A')}")
    print(f"   Captured: {'✅' if result.get('captured') else '❌'}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
