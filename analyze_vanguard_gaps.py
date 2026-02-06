"""
Vanguard Integration Gap Analysis
==================================
Check all subsystem integrations to identify missing connections.
"""

import os
from pathlib import Path

# Define expected integrations
EXPECTED_INTEGRATIONS = {
    "Inquisitor → Archivist": {
        "file": "vanguard/inquisitor/middleware.py",
        "should_import": "from ..archivist.storage import get_incident_storage",
        "should_call": "await storage.store(incident)",
        "description": "Middleware must persist incidents to Archivist storage"
    },
    "Inquisitor → Profiler": {
        "file": "vanguard/inquisitor/middleware.py",
        "should_import": "from ..profiler.llm_client import get_llm_client",
        "should_call": "await llm_client.classify_incident",
        "description": "Middleware should trigger LLM analysis for RED severity incidents"
    },
    "Profiler → Surgeon": {
        "file": "vanguard/profiler/llm_client.py",
        "should_import": "from ..surgeon.remediation import get_surgeon",
        "should_call": "surgeon.decide_remediation",
        "description": "Profiler should pass analysis to Surgeon for remediation decisions"
    },
    "Health API → Archivist": {
        "file": "vanguard/api/health.py",
        "should_import": "from ..archivist.storage import get_incident_storage",
        "should_call": "storage.list_incidents()",
        "description": "Health endpoint must report incident counts from Archivist"
    },
    "Bootstrap → All Subsystems": {
        "file": "vanguard/bootstrap/lifespan.py",
        "should_import": "subsystem initializations",
        "should_call": "initialize monitoring, profiler, surgeon",
        "description": "Lifespan should initialize all subsystems on startup"
    }
}

print("=" * 70)
print("VANGUARD INTEGRATION GAP ANALYSIS")
print("=" * 70)

backend_path = Path("backend")
gaps_found = []

for integration_name, details in EXPECTED_INTEGRATIONS.items():
    print(f"\n[Checking] {integration_name}")
    
    file_path = backend_path / details["file"]
    
    if not file_path.exists():
        print(f"  ❌ File missing: {details['file']}")
        gaps_found.append({
            "integration": integration_name,
            "issue": "File not found",
            "file": details["file"]
        })
        continue
    
    content = file_path.read_text()
    
    # Check import
    import_found = details["should_import"] in content or "SKIP_IMPORT_CHECK" in details["should_import"]
    # Check call
    call_found = details["should_call"] in content or "SKIP_CALL_CHECK" in details["should_call"]
    
    if import_found and call_found:
        print(f"  ✅ INTEGRATED")
    elif not import_found:
        print(f"  ⚠️  Missing import: {details['should_import']}")
        gaps_found.append({
            "integration": integration_name,
            "issue": "Missing import",
            "expected": details["should_import"],
            "file": details["file"]
        })
    elif not call_found:
        print(f"  ⚠️  Missing call: {details['should_call']}")
        gaps_found.append({
            "integration": integration_name,
            "issue": "Missing function call",
            "expected": details["should_call"],
            "file": details["file"]
        })

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total integrations checked: {len(EXPECTED_INTEGRATIONS)}")
print(f"Gaps found: {len(gaps_found)}")

if gaps_found:
    print("\n⚠️  GAPS DETECTED:")
    for i, gap in enumerate(gaps_found, 1):
        print(f"\n{i}. {gap['integration']}")
        print(f"   Issue: {gap['issue']}")
        print(f"   File: {gap['file']}")
        if 'expected' in gap:
            print(f"   Expected: {gap['expected']}")
else:
    print("\n✅ NO GAPS FOUND - All integrations present!")

# Save to file
import json
with open("vanguard_gap_analysis.json", "w") as f:
    json.dump({
        "total_checks": len(EXPECTED_INTEGRATIONS),
        "gaps_found": len(gaps_found),
        "gaps": gaps_found
    }, f, indent=2)

print(f"\nResults saved to: vanguard_gap_analysis.json")
