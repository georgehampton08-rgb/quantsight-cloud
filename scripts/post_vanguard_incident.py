#!/usr/bin/env python3
"""
Post Vanguard Incident
========================
Reusable script to post structured incidents to Vanguard admin API.
Used by drift_oracle, perf_baseline, and dependency_audit workflows.

Usage:
  python post_vanguard_incident.py \
    --type SCHEMA_DRIFT \
    --severity HIGH \
    --message "Breaking change: field 'name' removed from GET /teams" \
    --metadata '{"path": "/teams", "field": "name"}'

Environment:
  VANGUARD_BASE_URL: Base URL of the backend (default: Cloud Run URL)
"""

import json
import os
import sys
import urllib.request
import ssl
import hashlib
from datetime import datetime, timezone

DEFAULT_BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def post_incident(incident_type: str, severity: str, message: str, metadata: dict = None):
    base_url = os.environ.get("VANGUARD_BASE_URL", DEFAULT_BASE_URL)
    url = f"{base_url}/vanguard/admin/incidents/ingest"

    # Generate fingerprint from type + message
    fingerprint = hashlib.sha256(f"{incident_type}:{message}".encode()).hexdigest()[:16]

    payload = {
        "fingerprint": f"ci_{incident_type.lower()}_{fingerprint}",
        "severity": severity.upper(),
        "error_type": incident_type,
        "error_message": message,
        "metadata": metadata or {},
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10, context=_ctx)
        print(f"✅ Incident posted: {incident_type} ({severity})")
        print(f"   Response: {resp.read().decode()}")
    except Exception as e:
        print(f"⚠️  Failed to post incident (non-fatal): {e}", file=sys.stderr)


def main():
    args = sys.argv[1:]
    incident_type = "UNKNOWN"
    severity = "AMBER"
    message = ""
    metadata = {}

    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            incident_type = args[i + 1]; i += 2
        elif args[i] == "--severity" and i + 1 < len(args):
            severity = args[i + 1]; i += 2
        elif args[i] == "--message" and i + 1 < len(args):
            message = args[i + 1]; i += 2
        elif args[i] == "--metadata" and i + 1 < len(args):
            try:
                metadata = json.loads(args[i + 1])
            except json.JSONDecodeError:
                metadata = {"raw": args[i + 1]}
            i += 2
        else:
            i += 1

    if not message:
        print("Usage: post_vanguard_incident.py --type TYPE --severity SEVERITY --message MSG", file=sys.stderr)
        sys.exit(1)

    post_incident(incident_type, severity, message, metadata)


if __name__ == "__main__":
    main()
