"""
Vanguard Incidents Export Audit
===============================
Parses the Vanguard incidents export JSON and produces summary tables.

Usage:
    python scripts/audit_incidents_export.py [path_to_export.json]
"""
import json
import sys
from collections import Counter
from pathlib import Path


def audit_export(file_path: str):
    with open(file_path, "r") as f:
        data = json.load(f)

    export_info = data.get("export_info", {})
    incidents = data.get("incidents", [])

    print("=" * 70)
    print("VANGUARD INCIDENTS EXPORT AUDIT")
    print(f"File: {file_path}")
    print(f"Exported at: {export_info.get('exported_at', 'unknown')}")
    print(f"Source: {export_info.get('source', 'unknown')}")
    print("=" * 70)

    # ── Summary ──
    total = len(incidents)
    print(f"\nTotal incidents: {total}")

    # ── Severity breakdown ──
    severity_counts = Counter(i.get("severity", "UNKNOWN") for i in incidents)
    print("\n--- Severity Breakdown ---")
    for sev, count in severity_counts.most_common():
        pct = count / total * 100
        print(f"  {sev:10s}: {count:4d} ({pct:.1f}%)")

    # ── Status breakdown ──
    status_counts = Counter(i.get("status", "unknown") for i in incidents)
    print("\n--- Status Breakdown ---")
    for st, count in status_counts.most_common():
        pct = count / total * 100
        print(f"  {st:10s}: {count:4d} ({pct:.1f}%)")

    # ── Error type breakdown ──
    error_counts = Counter(i.get("error_type", "unknown") for i in incidents)
    print("\n--- Error Type Breakdown ---")
    for et, count in error_counts.most_common():
        pct = count / total * 100
        print(f"  {et:20s}: {count:4d} ({pct:.1f}%)")

    # ── Top endpoints by occurrence_count ──
    endpoints = []
    for i in incidents:
        endpoints.append((
            i.get("endpoint", "unknown"),
            i.get("occurrence_count", 1),
            i.get("error_type", ""),
            i.get("severity", "")
        ))
    endpoints.sort(key=lambda x: x[1], reverse=True)

    print("\n--- Top 20 Endpoints (by total occurrences) ---")
    for ep, count, et, sev in endpoints[:20]:
        print(f"  {count:6d} hits | {sev:6s} | {et:16s} | {ep}")

    # ── Service breakdown ──
    service_counts = Counter(
        i.get("labels", {}).get("service", "unknown") for i in incidents
    )
    print("\n--- Service Breakdown ---")
    for svc, count in service_counts.most_common():
        pct = count / total * 100
        print(f"  {svc:20s}: {count:4d} ({pct:.1f}%)")

    # ── Error category breakdown ──
    error_cat_counts = Counter(
        i.get("labels", {}).get("error_category", "unknown") for i in incidents
    )
    print("\n--- Error Category Breakdown ---")
    for cat, count in error_cat_counts.most_common():
        pct = count / total * 100
        print(f"  {cat:20s}: {count:4d} ({pct:.1f}%)")

    # ── Root cause buckets ──
    print("\n--- Root Cause Buckets ---")

    missing_routes = [i for i in incidents if i.get("error_type") == "HTTPError404"]
    admin_resolve = [i for i in incidents
                     if "admin/resolve" in i.get("endpoint", "")
                     and i.get("error_type") == "HTTPError400"]
    server_errors = [i for i in incidents if i.get("error_type") == "HTTPError500"]
    object_object = [i for i in incidents if "[object Object]" in i.get("endpoint", "")]
    permission = [i for i in incidents if i.get("error_type") in ("HTTPError403", "HTTPError503")]

    print(f"  Missing routes (404):         {len(missing_routes)}")
    print(f"  Broken admin resolve (400):   {len(admin_resolve)}")
    print(f"  Server errors (500):          {len(server_errors)}")
    print(f"  [object Object] bug:          {len(object_object)}")
    print(f"  Permission/unavailable:       {len(permission)}")

    # ── Incidents with AI analysis ──
    has_analysis = [i for i in incidents if i.get("ai_analysis")]
    print(f"\n--- AI Analysis Coverage ---")
    print(f"  With analysis:    {len(has_analysis)}/{total}")
    print(f"  Without analysis: {total - len(has_analysis)}/{total}")

    if has_analysis:
        confidences = [i["ai_analysis"].get("confidence", 0) for i in has_analysis]
        avg_conf = sum(confidences) / len(confidences)
        ready = sum(1 for i in has_analysis if i["ai_analysis"].get("ready_to_resolve"))
        print(f"  Avg confidence:   {avg_conf:.1f}")
        print(f"  Ready to resolve: {ready}/{len(has_analysis)}")

    # ── Resolved incidents ──
    resolved = [i for i in incidents if i.get("status") == "resolved"]
    if resolved:
        print(f"\n--- Resolved Incidents ({len(resolved)}) ---")
        for i in resolved:
            print(f"  {i['fingerprint'][:16]}... | {i.get('endpoint', '?')} | resolved_at: {i.get('resolved_at', '?')}")

    print("\n" + "=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    default_path = Path(__file__).parent.parent / "vanguard_incidents_export_20260224_081601.json"

    if len(sys.argv) > 1:
        path = sys.argv[1]
    elif default_path.exists():
        path = str(default_path)
    else:
        print(f"Usage: python {sys.argv[0]} <path_to_export.json>")
        print(f"Default path not found: {default_path}")
        sys.exit(1)

    audit_export(path)
