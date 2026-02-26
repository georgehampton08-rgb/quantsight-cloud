#!/usr/bin/env python3
"""
Performance Smoke Test
========================
Measures P95 latency for critical endpoints and compares against baseline.

Exit codes:
  0 = all within tolerance
  1 = AMBER warning (>15% regression on any endpoint)
  2 = RED critical (>40% regression on any endpoint)

Usage:
  python perf_smoke.py [--base-url URL] [--baseline perf_baseline.json]
"""

import json
import os
import sys
import time
import urllib.request
import ssl

DEFAULT_BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"
DEFAULT_BASELINE = os.path.join(os.path.dirname(__file__), "perf_baseline.json")
SAMPLE_COUNT = 10
WARN_THRESHOLD = 0.15   # 15%
FAIL_THRESHOLD = 0.40   # 40%

CRITICAL_ENDPOINTS = [
    "GET /teams",
    "GET /players/search?q=lebron",
    "GET /health/deps",
    "GET /vanguard/health",
    "GET /status",
    "GET /health",
]

# Allow self-signed certs for tagged revision URLs
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def measure_p95(base_url: str, path: str, count: int = SAMPLE_COUNT) -> float:
    """Measure P95 latency in ms for an endpoint."""
    url = f"{base_url}{path}"
    times = []
    for _ in range(count):
        start = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "perf-smoke/1.0"})
            urllib.request.urlopen(req, timeout=10, context=_ctx)
        except Exception:
            pass
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)

    times.sort()
    p95_idx = max(0, int(len(times) * 0.95) - 1)
    return round(times[p95_idx], 1)


def main():
    base_url = DEFAULT_BASE_URL
    baseline_path = DEFAULT_BASELINE

    # Simple arg parsing
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--base-url" and i + 1 < len(args):
            base_url = args[i + 1]
            i += 2
        elif args[i] == "--baseline" and i + 1 < len(args):
            baseline_path = args[i + 1]
            i += 2
        else:
            i += 1

    # Load baseline
    try:
        with open(baseline_path, "r") as f:
            baseline = json.load(f)
    except FileNotFoundError:
        print(f"⚠️  Baseline file not found: {baseline_path}", file=sys.stderr)
        baseline = {}

    results = {}
    max_severity = 0  # 0=ok, 1=warn, 2=fail

    for endpoint in CRITICAL_ENDPOINTS:
        method, path = endpoint.split(" ", 1)
        p95 = measure_p95(base_url, path)

        baseline_entry = baseline.get(endpoint, {})
        baseline_p95 = baseline_entry.get("p95_ms")

        status = "OK"
        drift_pct = 0.0

        if baseline_p95 and baseline_p95 > 0:
            drift_pct = (p95 - baseline_p95) / baseline_p95
            if drift_pct > FAIL_THRESHOLD:
                status = "RED"
                max_severity = max(max_severity, 2)
            elif drift_pct > WARN_THRESHOLD:
                status = "AMBER"
                max_severity = max(max_severity, 1)

        results[endpoint] = {
            "p95_ms": p95,
            "baseline_p95_ms": baseline_p95,
            "drift_pct": round(drift_pct * 100, 1),
            "status": status,
        }

        print(f"  {endpoint}: {p95}ms (baseline: {baseline_p95}ms, drift: {round(drift_pct*100,1)}%) [{status}]")

    # Output JSON report
    report = {
        "base_url": base_url,
        "results": results,
        "max_severity": ["OK", "AMBER", "RED"][max_severity],
    }
    print(json.dumps(report, indent=2))

    sys.exit(max_severity)


if __name__ == "__main__":
    main()
