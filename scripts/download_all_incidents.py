#!/usr/bin/env python3
"""
Download All Vanguard Incidents from Firestore
===============================================
Exports every document in the 'vanguard_incidents' collection
(plus 'vanguard_metadata') into a single consolidated JSON file.

Usage:
    python download_all_incidents.py
    python download_all_incidents.py --output my_incidents.json
    python download_all_incidents.py --active-only

Output file is saved to quantsight_cloud_build/ by default.
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Load env
from dotenv import load_dotenv
load_dotenv(backend_path.parent / '.env')

import firebase_admin
from firebase_admin import credentials, firestore


def download_incidents(output_path: str = None, active_only: bool = False):
    """Download all Vanguard incidents from Firestore into a single JSON file."""

    # Initialize Firebase if needed
    if not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    print("=" * 70)
    print("VANGUARD INCIDENT DOWNLOAD")
    print("=" * 70)
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Mode: {'Active incidents only' if active_only else 'All incidents'}")
    print()

    # ── 1. Download all incidents ────────────────────────────────────────
    print("📥 Downloading incidents from 'vanguard_incidents' collection...")

    incidents = []
    query = db.collection('vanguard_incidents')

    if active_only:
        query = query.where(filter=firestore.FieldFilter('status', '==', 'active'))

    for doc in query.stream():
        data = doc.to_dict()
        data['_document_id'] = doc.id
        # Convert any non-serializable types
        incidents.append(_sanitize(data))

    print(f"   ✅ Downloaded {len(incidents)} incidents")

    # Count by status
    status_counts = {}
    for inc in incidents:
        status = inc.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    for status, count in sorted(status_counts.items()):
        print(f"      {status}: {count}")

    # ── 2. Download metadata ────────────────────────────────────────────
    print("\n📥 Downloading 'vanguard_metadata' collection...")

    metadata = {}
    for doc in db.collection('vanguard_metadata').stream():
        metadata[doc.id] = _sanitize(doc.to_dict())

    print(f"   ✅ Downloaded {len(metadata)} metadata documents")

    # ── 3. Build consolidated output ────────────────────────────────────
    output = {
        "export_info": {
            "exported_at": datetime.now().isoformat(),
            "source": "Firestore vanguard_incidents",
            "filter": "active_only" if active_only else "all",
            "total_incidents": len(incidents),
            "status_breakdown": status_counts,
        },
        "metadata": metadata,
        "incidents": incidents,
    }

    # ── 4. Write to file ────────────────────────────────────────────────
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(backend_path / f"vanguard_incidents_export_{timestamp}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    file_size_kb = os.path.getsize(output_path) / 1024
    print(f"\n💾 Saved to: {output_path}")
    print(f"   Size: {file_size_kb:.1f} KB")

    # ── 5. Summary ──────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("EXPORT SUMMARY")
    print("=" * 70)
    print(f"   Incidents:  {len(incidents)}")
    print(f"   Metadata:   {len(metadata)} documents")
    print(f"   File:       {output_path}")
    print(f"   Size:       {file_size_kb:.1f} KB")

    # Top endpoints
    endpoint_counts = {}
    for inc in incidents:
        ep = inc.get('endpoint', 'unknown')
        endpoint_counts[ep] = endpoint_counts.get(ep, 0) + 1

    if endpoint_counts:
        print(f"\n   Top endpoints:")
        for ep, count in sorted(endpoint_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"      {count:3d}x  {ep}")

    print("=" * 70)
    return output_path


def _sanitize(data: dict) -> dict:
    """Convert Firestore-specific types to JSON-serializable types."""
    clean = {}
    for key, value in data.items():
        if hasattr(value, 'isoformat'):
            clean[key] = value.isoformat()
        elif hasattr(value, '__iter__') and not isinstance(value, (str, list, dict)):
            clean[key] = str(value)
        elif isinstance(value, dict):
            clean[key] = _sanitize(value)
        elif isinstance(value, list):
            clean[key] = [_sanitize(v) if isinstance(v, dict) else
                          v.isoformat() if hasattr(v, 'isoformat') else v
                          for v in value]
        else:
            clean[key] = value
    return clean


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Download all Vanguard incidents from Firestore into a single JSON file'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output file path (default: vanguard_incidents_export_<timestamp>.json)'
    )
    parser.add_argument(
        '--active-only',
        action='store_true',
        help='Only download active (unresolved) incidents'
    )
    args = parser.parse_args()

    download_incidents(output_path=args.output, active_only=args.active_only)
