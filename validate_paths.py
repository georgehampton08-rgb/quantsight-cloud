#!/usr/bin/env python3
"""
Cloud Build Path Validation Script
===================================
Validates all API endpoint paths between frontend and backend in cloud build.
"""

import re
from pathlib import Path
from typing import Set, Dict, List
import json

# Paths
CLOUD_BUILD_ROOT = Path(r"c:\Users\georg\quantsight_engine\quantsight_cloud_build")
FRONTEND_SRC = CLOUD_BUILD_ROOT / "src"
BACKEND_SERVER = CLOUD_BUILD_ROOT / "backend" / "server.py"

# Results
frontend_endpoints: Set[str] = set()
backend_endpoints: Set[str] = set()
issues: List[Dict[str, str]] = []


def extract_frontend_endpoints():
    """Extract all API endpoint calls from frontend code."""
    print("\n🔍 Scanning Frontend for API Calls...")
    
    # Patterns to match
    patterns = [
        r'fetch\([\'"`]([^\'"`]+)[\'"`]',  # fetch('url')
        r'fetch\(`([^`]+)`\)',  # fetch(`url`)
        r'API_BASE\s*\+\s*[\'"`]([^\'"`]+)[\'"`]',  # API_BASE + '/endpoint'
        r'http://localhost:5000([^\'"` \)]+)',  # Direct localhost URLs
    ]
    
    for ts_file in FRONTEND_SRC.rglob("*.ts*"):
        try:
            content = ts_file.read_text(encoding='utf-8')
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # Clean up the endpoint
                    endpoint = match.strip()
                    if endpoint.startswith('http://localhost:5000'):
                        endpoint = endpoint.replace('http://localhost:5000', '')
                    
                    # Remove query parameters for comparison
                    if '?' in endpoint:
                        endpoint = endpoint.split('?')[0]
                    
                    # Skip if it's a variable or template
                    if '${' not in endpoint and endpoint.startswith('/'):
                        frontend_endpoints.add(endpoint)
                        print(f"  📍 {ts_file.name}: {endpoint}")
        except Exception as e:
            print(f"  ⚠️  Error reading {ts_file}: {e}")


def extract_backend_endpoints():
    """Extract all defined endpoints from backend server."""
    print("\n🔍 Scanning Backend for Endpoint Definitions...")
    
    if not BACKEND_SERVER.exists():
        print(f"  ❌ Backend server not found at {BACKEND_SERVER}")
        return
    
    content = BACKEND_SERVER.read_text(encoding='utf-8')
    
    # Match @app.get(), @app.post(), etc.
    pattern = r'@app\.(get|post|put|delete|patch)\([\'"`]([^\'"`]+)[\'"`]'
    matches = re.findall(pattern, content)
    
    for method, endpoint in matches:
        backend_endpoints.add(endpoint)
        print(f"  ✅ {method.upper()}: {endpoint}")


def validate_paths():
    """Compare frontend calls with backend definitions."""
    print("\n🔬 Validating Path Compatibility...")
    
    # Check for frontend calls without backend endpoints
    missing_backend = []
    for fe_endpoint in frontend_endpoints:
        # Try exact match first
        found = fe_endpoint in backend_endpoints
        
        # Try with parameter placeholder
        if not found:
            # Convert /player/123 to /player/{id}
            path_parts = fe_endpoint.split('/')
            if path_parts and path_parts[-1].isdigit():
                parameterized = '/'.join(path_parts[:-1]) + '/{id}'
                found = parameterized in backend_endpoints
        
        if not found:
            missing_backend.append(fe_endpoint)
            issues.append({
                "type": "missing_backend",
                "endpoint": fe_endpoint,
                "severity": "warning"
            })
    
    # Check for unused backend endpoints
    unused_backend = []
    for be_endpoint in backend_endpoints:
        # Simple heuristic - check if any frontend endpoint starts with this
        used = any(
            fe.startswith(be_endpoint) or be_endpoint.startswith(fe.rstrip('/'))
            for fe in frontend_endpoints
        )
        if not used:
            unused_backend.append(be_endpoint)
    
    return missing_backend, unused_backend


def print_report():
    """Print validation report."""
    print("\n" + "=" * 70)
    print("PATH VALIDATION REPORT")
    print("=" * 70)
    
    print(f"\n📊 Summary:")
    print(f"  Frontend API Calls: {len(frontend_endpoints)}")
    print(f"  Backend Endpoints: {len(backend_endpoints)}")
    
    missing_backend, unused_backend = validate_paths()
    
    if missing_backend:
        print(f"\n⚠️  Frontend calls WITHOUT backend endpoints ({len(missing_backend)}):")
        for endpoint in sorted(missing_backend):
            print(f"  ❌ {endpoint}")
    else:
        print("\n✅ All frontend calls have matching backend endpoints!")
    
    if unused_backend:
        print(f"\n💤 Unused backend endpoints ({len(unused_backend)}):")
        for endpoint in sorted(unused_backend):
            print(f"  • {endpoint}")
    
    # Critical path checks
    print("\n🎯 Critical Paths Validation:")
    critical_paths = [
        "/api/game-logs",
        "/live/stream",
        "/live/leaders",
        "/health",
        "/teams",
        "/players/search",
        "/schedule"
    ]
    
    for path in critical_paths:
        if path in backend_endpoints:
            print(f"  ✅ {path}")
        else:
            print(f"  ❌ {path} NOT FOUND")
            issues.append({
                "type": "critical_missing",
                "endpoint": path,
                "severity": "error"
            })
    
    # Save issues to file
    issues_file = CLOUD_BUILD_ROOT / "path_validation_report.json"
    issues_file.write_text(json.dumps({
        "frontend_endpoints": sorted(list(frontend_endpoints)),
        "backend_endpoints": sorted(list(backend_endpoints)),
        "missing_backend": sorted(missing_backend),
        "unused_backend": sorted(unused_backend),
        "issues": issues
    }, indent=2))
    
    print(f"\n📄 Full report saved to: {issues_file}")
    
    if any(issue["severity"] == "error" for issue in issues):
        print("\n❌ VALIDATION FAILED - Critical paths missing!")
        return 1
    elif issues:
        print("\n⚠️  VALIDATION PASSED with warnings")
        return 0
    else:
        print("\n✅ VALIDATION PASSED - All paths compatible!")
        return 0


def main():
    print("=" * 70)
    print("CLOUD BUILD PATH VALIDATOR")
    print("=" * 70)
    print(f"Frontend: {FRONTEND_SRC}")
    print(f"Backend: {BACKEND_SERVER}")
    
    extract_frontend_endpoints()
    extract_backend_endpoints()
    exit_code = print_report()
    
    return exit_code


if __name__ == "__main__":
    exit(main())
