"""
404 Incident Classification Report
===================================
Cross-references 404 incidents from the export file against registered
FastAPI routes to classify each as:
  - WRONG_METHOD: Path exists but method mismatches
  - WRONG_PREFIX: Path exists under a different prefix
  - MISSING_ROUTE: Completely absent from route index
  - STALE_CALLER:  Obviously outdated / invalid caller pattern

Usage:
    python scripts/classify_404_incidents.py [export_file]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Import the route table
sys.path.insert(0, str(Path(__file__).parent))
from dump_registered_routes import REGISTERED_ROUTES


def _normalize(path: str) -> str:
    """Strip trailing slash and lower-case for comparison."""
    return path.rstrip("/").lower()


def _strip_ids(path: str) -> str:
    """Replace path-segment IDs with {id} for fuzzy matching."""
    # Replace segments that look like numeric IDs or hex fingerprints
    parts = path.strip("/").split("/")
    normalized = []
    for p in parts:
        if re.fullmatch(r"\d{4,}", p):          # numeric player/game ID
            normalized.append("{id}")
        elif re.fullmatch(r"[0-9a-f]{16,}", p):  # hex fingerprint
            normalized.append("{fp}")
        elif p == "[object Object]":
            normalized.append("{OBJECT_BUG}")
        else:
            normalized.append(p)
    return "/" + "/".join(normalized)


def classify(export_path: str):
    # Load export
    with open(export_path) as f:
        data = json.load(f)

    incidents = data.get("incidents", [])
    four04s = [i for i in incidents if i.get("error_type") == "HTTPError404"]

    # Build lookup structures from registered routes
    route_paths = set()          # exact normalised paths
    route_methods = {}           # path -> set of methods
    route_stripped = {}          # id-stripped -> original path
    route_prefixes = set()       # first path segments

    for r in REGISTERED_ROUTES:
        np = _normalize(r["path"])
        route_paths.add(np)
        route_methods.setdefault(np, set()).add(r["method"])
        sp = _strip_ids(np)
        route_stripped[sp] = np
        prefix = "/" + np.strip("/").split("/")[0] if np != "/" else "/"
        route_prefixes.add(prefix)

    # Classify each 404
    classifications = []
    for inc in four04s:
        ep = inc.get("endpoint", "unknown")
        method = inc.get("context_vector", {}).get("method", "GET")
        occ = inc.get("occurrence_count", 1)
        nep = _normalize(ep)
        sep = _strip_ids(nep)

        result = {
            "endpoint": ep,
            "method": method,
            "occurrences": occ,
            "fingerprint": inc.get("fingerprint", "")[:16],
        }

        # 1. Exact match -> wrong method
        if nep in route_paths:
            if method not in route_methods.get(nep, set()):
                result["class"] = "WRONG_METHOD"
                result["detail"] = f"Path exists but only accepts {route_methods[nep]}"
            else:
                result["class"] = "ROUTE_EXISTS"
                result["detail"] = "Route registered -- 404 may be runtime import failure"
        # 2. ID-stripped match -> path exists with different params
        elif sep in route_stripped:
            result["class"] = "WRONG_PREFIX"
            result["detail"] = f"Similar route: {route_stripped[sep]}"
        # 3. Check if prefix exists
        else:
            first_seg = "/" + nep.strip("/").split("/")[0] if nep != "/" else "/"
            if first_seg in route_prefixes:
                result["class"] = "MISSING_ROUTE"
                result["detail"] = f"Prefix '{first_seg}' exists but no matching route"
            else:
                # Check for [object Object] bug
                if "[object" in ep.lower():
                    result["class"] = "STALE_CALLER"
                    result["detail"] = "Frontend serialization bug: [object Object] in URL"
                else:
                    result["class"] = "MISSING_ROUTE"
                    result["detail"] = f"No route or prefix matches '{first_seg}'"

        classifications.append(result)

    # Sort by occurrences descending
    classifications.sort(key=lambda x: x["occurrences"], reverse=True)

    # Print report
    print("=" * 80)
    print("404 INCIDENT CLASSIFICATION REPORT")
    print(f"Export: {export_path}")
    print(f"Total 404 incidents: {len(four04s)}")
    print("=" * 80)

    class_counts = Counter(c["class"] for c in classifications)
    print("\n--- Classification Summary ---")
    for cls, count in class_counts.most_common():
        print(f"  {cls:20s}: {count}")

    print(f"\n--- Detailed Classifications (top 30 by occurrences) ---")
    print(f"{'Occ':>6}  {'Class':20s}  {'Method':6s}  {'Endpoint'}")
    print("-" * 80)
    for c in classifications[:30]:
        print(f"{c['occurrences']:6d}  {c['class']:20s}  {c['method']:6s}  {c['endpoint']}")
        if c.get("detail"):
            print(f"         {c['detail']}")

    # Action items
    print(f"\n--- Action Items ---")
    route_exists = [c for c in classifications if c["class"] == "ROUTE_EXISTS"]
    wrong_method = [c for c in classifications if c["class"] == "WRONG_METHOD"]
    missing = [c for c in classifications if c["class"] == "MISSING_ROUTE"]
    stale = [c for c in classifications if c["class"] == "STALE_CALLER"]
    wrong_prefix = [c for c in classifications if c["class"] == "WRONG_PREFIX"]

    if route_exists:
        print(f"\n  ROUTE_EXISTS ({len(route_exists)}): Routes are registered but still 404ing.")
        print("  -> Likely router import failure at runtime or conditional registration.")
        for c in route_exists:
            print(f"    - {c['endpoint']} ({c['occurrences']} hits)")

    if wrong_method:
        print(f"\n  WRONG_METHOD ({len(wrong_method)}): Path exists but wrong HTTP method.")
        for c in wrong_method:
            print(f"    - {c['method']} {c['endpoint']} -> {c['detail']}")

    if wrong_prefix:
        print(f"\n  WRONG_PREFIX ({len(wrong_prefix)}): Caller using wrong path variant.")
        for c in wrong_prefix:
            print(f"    - {c['endpoint']} -> {c['detail']}")

    if stale:
        print(f"\n  STALE_CALLER ({len(stale)}): Frontend bugs producing invalid URLs.")
        for c in stale:
            print(f"    - {c['endpoint']}")

    if missing:
        print(f"\n  MISSING_ROUTE ({len(missing)}): No registered route matches.")
        # Group by prefix
        by_prefix = {}
        for c in missing:
            first = "/" + c["endpoint"].strip("/").split("/")[0]
            by_prefix.setdefault(first, []).append(c)
        for prefix, items in sorted(by_prefix.items(), key=lambda x: -sum(i["occurrences"] for i in x[1])):
            total_occ = sum(i["occurrences"] for i in items)
            print(f"    Prefix {prefix} ({len(items)} routes, {total_occ} total hits):")
            for c in sorted(items, key=lambda x: -x["occurrences"])[:5]:
                print(f"      - {c['method']} {c['endpoint']} ({c['occurrences']} hits)")

    print("\n" + "=" * 80)
    return classifications


if __name__ == "__main__":
    default = Path(__file__).parent.parent / "vanguard_incidents_export_20260224_081601.json"
    path = sys.argv[1] if len(sys.argv) > 1 else str(default)
    classify(path)
