#!/usr/bin/env python3
"""
OpenAPI Contract Drift Comparator
===================================
Compares two OpenAPI specs (local vs production) and detects breaking changes.

Exit codes:
  0 = clean (no breaking changes)
  1 = warnings only (additive changes)
  2 = breaking drift detected (removed endpoints, renamed fields, added required fields)

Usage:
  python compare_openapi.py openapi_local.json openapi_prod.json
"""

import json
import sys
from typing import Any


def load_spec(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_paths(local: dict, prod: dict) -> list:
    """Compare API paths between local and production specs."""
    issues = []
    local_paths = set(local.get("paths", {}).keys())
    prod_paths = set(prod.get("paths", {}).keys())

    # Removed endpoints = BREAKING
    removed = prod_paths - local_paths
    for p in sorted(removed):
        issues.append({"type": "REMOVED_ENDPOINT", "severity": "BREAKING", "path": p})

    # Added endpoints = ADDITIVE (OK)
    added = local_paths - prod_paths
    for p in sorted(added):
        issues.append({"type": "ADDED_ENDPOINT", "severity": "INFO", "path": p})

    return issues


def compare_methods(local: dict, prod: dict) -> list:
    """Compare HTTP methods for shared paths."""
    issues = []
    shared_paths = set(local.get("paths", {}).keys()) & set(prod.get("paths", {}).keys())

    for path in sorted(shared_paths):
        local_methods = set(local["paths"][path].keys()) - {"parameters", "summary", "description"}
        prod_methods = set(prod["paths"][path].keys()) - {"parameters", "summary", "description"}

        removed_methods = prod_methods - local_methods
        for m in sorted(removed_methods):
            issues.append({
                "type": "REMOVED_METHOD",
                "severity": "BREAKING",
                "path": path,
                "method": m.upper(),
            })

    return issues


def _resolve_ref(spec: dict, ref: str) -> dict:
    """Resolve a $ref pointer within the spec."""
    parts = ref.lstrip("#/").split("/")
    node = spec
    for part in parts:
        node = node.get(part, {})
    return node


def _get_schema(spec: dict, path: str, method: str) -> dict:
    """Extract the 200 response schema for an endpoint."""
    endpoint = spec.get("paths", {}).get(path, {}).get(method, {})
    resp_200 = endpoint.get("responses", {}).get("200", {})
    schema = resp_200.get("content", {}).get("application/json", {}).get("schema", {})

    if "$ref" in schema:
        return _resolve_ref(spec, schema["$ref"])
    return schema


def compare_schemas(local: dict, prod: dict) -> list:
    """Compare response schemas for shared path+method combinations."""
    issues = []
    shared_paths = set(local.get("paths", {}).keys()) & set(prod.get("paths", {}).keys())

    for path in sorted(shared_paths):
        local_methods = set(local["paths"][path].keys()) - {"parameters", "summary", "description"}
        prod_methods = set(prod["paths"][path].keys()) - {"parameters", "summary", "description"}
        shared_methods = local_methods & prod_methods

        for method in sorted(shared_methods):
            local_schema = _get_schema(local, path, method)
            prod_schema = _get_schema(prod, path, method)

            if not local_schema or not prod_schema:
                continue

            # Compare required fields
            local_required = set(local_schema.get("required", []))
            prod_required = set(prod_schema.get("required", []))

            # New required fields = BREAKING (clients may not send them)
            new_required = local_required - prod_required
            for field in sorted(new_required):
                issues.append({
                    "type": "ADDED_REQUIRED_FIELD",
                    "severity": "BREAKING",
                    "path": path,
                    "method": method.upper(),
                    "field": field,
                })

            # Compare property names
            local_props = set(local_schema.get("properties", {}).keys())
            prod_props = set(prod_schema.get("properties", {}).keys())

            removed_props = prod_props - local_props
            for prop in sorted(removed_props):
                issues.append({
                    "type": "REMOVED_FIELD",
                    "severity": "BREAKING",
                    "path": path,
                    "method": method.upper(),
                    "field": prop,
                })

            added_props = local_props - prod_props
            for prop in sorted(added_props):
                sev = "BREAKING" if prop in local_required else "INFO"
                issues.append({
                    "type": "ADDED_FIELD",
                    "severity": sev,
                    "path": path,
                    "method": method.upper(),
                    "field": prop,
                })

    return issues


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <local_spec.json> <prod_spec.json>")
        sys.exit(2)

    local_path, prod_path = sys.argv[1], sys.argv[2]
    local = load_spec(local_path)
    prod = load_spec(prod_path)

    all_issues = []
    all_issues.extend(compare_paths(local, prod))
    all_issues.extend(compare_methods(local, prod))
    all_issues.extend(compare_schemas(local, prod))

    # Categorize
    breaking = [i for i in all_issues if i["severity"] == "BREAKING"]
    warnings = [i for i in all_issues if i["severity"] == "INFO"]

    report = {
        "breaking_count": len(breaking),
        "warning_count": len(warnings),
        "breaking": breaking,
        "warnings": warnings,
    }

    print(json.dumps(report, indent=2))

    if breaking:
        print(f"\n❌ {len(breaking)} BREAKING changes detected!", file=sys.stderr)
        sys.exit(2)
    elif warnings:
        print(f"\n⚠️  {len(warnings)} additive changes (non-breaking)", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n✅ No drift detected", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
