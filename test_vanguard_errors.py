"""
Vanguard Error Simulation Script
=================================
Trigger 5 different error types to test Vanguard's incident response.
"""
import requests
import time
import json
from datetime import datetime

BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

print("=" * 70)
print("VANGUARD ERROR SIMULATION TEST")
print("=" * 70)
print(f"Target: {BASE_URL}")
print(f"Time: {datetime.now().isoformat()}")
print("=" * 70)

# Track results
results = []

# ERROR TYPE 1: 404 Not Found
print("\n[1/5] Testing 404 Not Found...")
try:
    r = requests.get(f"{BASE_URL}/api/nonexistent/route/test")
    results.append({
        "error_type": "404_NOT_FOUND",
        "status": r.status_code,
        "timestamp": datetime.now().isoformat(),
        "request_id": r.headers.get("X-Request-ID", "N/A"),
        "captured": r.status_code == 404
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"error_type": "404_NOT_FOUND", "captured": False, "error": str(e)})

time.sleep(2)

# ERROR TYPE 2: Invalid Endpoint (expecting 400 or 422)
print("\n[2/5] Testing Invalid Parameters...")
try:
    r = requests.post(
        f"{BASE_URL}/api/matchup",
        json={"invalid": "data", "missing": "required_fields"}
    )
    results.append({
        "error_type": "INVALID_PARAMS",
        "status": r.status_code,
        "timestamp": datetime.now().isoformat(),
        "request_id": r.headers.get("X-Request-ID", "N/A"),
        "response_preview": r.text[:100] if r.text else "Empty",
        "captured": r.status_code in [400, 404, 422]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"error_type": "INVALID_PARAMS", "captured": False, "error": str(e)})

time.sleep(2)

# ERROR TYPE 3: Rapid Requests (potential rate limit/resource exhaustion)
print("\n[3/5] Testing Rapid Requests (Resource Pressure)...")
request_times = []
try:
    for i in range(10):
        start = time.perf_counter()
        r = requests.get(f"{BASE_URL}/health")
        duration = (time.perf_counter() - start) * 1000
        request_times.append(duration)
    
    avg_time = sum(request_times) / len(request_times)
    results.append({
        "error_type": "RESOURCE_PRESSURE",
        "avg_response_ms": round(avg_time, 2),
        "requests": 10,
        "timestamp": datetime.now().isoformat(),
        "captured": True,
        "anomaly_detected": avg_time > 500  # >500ms considered slow
    })
    print(f"  Average response: {avg_time:.2f}ms")
    print(f"  Anomaly detected: {avg_time > 500}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"error_type": "RESOURCE_PRESSURE", "captured": False, "error": str(e)})

time.sleep(2)

# ERROR TYPE 4: Missing Headers/Auth (403 or 401 expected on protected routes)
print("\n[4/5] Testing Missing Headers...")
try:
    r = requests.get(
        f"{BASE_URL}/api/matchup/protected",
        headers={"X-Test": "invalid"}
    )
    results.append({
        "error_type": "MISSING_AUTH",
        "status": r.status_code,
        "timestamp": datetime.now().isoformat(),
        "request_id": r.headers.get("X-Request-ID", "N/A"),
        "captured": r.status_code in [401, 403, 404]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"error_type": "MISSING_AUTH", "captured": False, "error": str(e)})

time.sleep(2)

# ERROR TYPE 5: Malformed JSON (should cause 422)
print("\n[5/5] Testing Malformed Request Body...")
try:
    r = requests.post(
        f"{BASE_URL}/api/pulse",
        data="this is not json",
        headers={"Content-Type": "application/json"}
    )
    results.append({
        "error_type": "MALFORMED_REQUEST",
        "status": r.status_code,
        "timestamp": datetime.now().isoformat(),
        "request_id": r.headers.get("X-Request-ID", "N/A"),
        "captured": r.status_code in [400, 404, 422]
    })
    print(f"  Status: {r.status_code}")
    print(f"  Request ID: {r.headers.get('X-Request-ID', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")
    results.append({"error_type": "MALFORMED_REQUEST", "captured": False, "error": str(e)})

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

captured_count = sum(1 for r in results if r.get("captured", False))
print(f"Errors triggered: {len(results)}")
print(f"Errors captured: {captured_count}")

# Save results
with open("vanguard_error_test_results.json", "w") as f:
    json.dump({
        "test_run": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "total_tests": len(results),
        "captured": captured_count,
        "results": results
    }, f, indent=2)

print(f"\nResults saved to: vanguard_error_test_results.json")

# Print each result
for i, result in enumerate(results, 1):
    print(f"\n{i}. {result.get('error_type', 'UNKNOWN')}")
    print(f"   Captured: {'✅' if result.get('captured') else '❌'}")
    if 'status' in result:
        print(f"   Status: {result['status']}")
    if 'request_id' in result:
        print(f"   Request ID: {result['request_id']}")

print("\n" + "=" * 70)
