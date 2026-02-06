#!/usr/bin/env python3
"""
Investigate Current Vanguard Incidents
Shows what's actually happening right now
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vanguard.archivist import VanguardArchivist
from datetime import datetime

def main():
    print("🔍 Investigating current Vanguard incidents...")
    print()
    
    archivist = VanguardArchivist()
    
    # Get all active incidents
    incidents = archivist.get_recent_incidents(hours=24, limit=100)
    
    print(f"📊 Total incidents: {len(incidents)}")
    print()
    
    if not incidents:
        print("✅ No incidents! System is healthy.")
        return
    
    # Group by endpoint
    by_endpoint = {}
    for inc in incidents:
        endpoint = inc.endpoint if hasattr(inc, 'endpoint') else 'unknown'
        if endpoint not in by_endpoint:
            by_endpoint[endpoint] = []
        by_endpoint[endpoint].append(inc)
    
    print("📋 Incidents by endpoint:")
    print()
    
    for endpoint, incident_list in sorted(by_endpoint.items(), key=lambda x: -len(x[1])):
        count = sum(inc.count if hasattr(inc, 'count') else 1 for inc in incident_list)
        print(f"   {endpoint}: {count} incidents")
        
        for inc in incident_list[:3]:  # Show first 3
            error_type = inc.error_type if hasattr(inc, 'error_type') else 'unknown'
            http_status = inc.http_status if hasattr(inc, 'http_status') else 0
            severity = inc.severity if hasattr(inc, 'severity') else 'medium'
            print(f"      - {http_status} {error_type} [{severity}]")
        
        if len(incident_list) > 3:
            print(f"      ... and {len(incident_list) - 3} more")
        print()
    
    print("🎯 Top incident patterns:")
    print()
    
    patterns = {}
    for inc in incidents:
        endpoint = inc.endpoint if hasattr(inc, 'endpoint') else 'unknown'
        error_type = inc.error_type if hasattr(inc, 'error_type') else 'unknown'
        http_status = inc.http_status if hasattr(inc, 'http_status') else 0
        
        pattern = f"{endpoint} {http_status} {error_type}"
        count = inc.count if hasattr(inc, 'count') else 1
        
        if pattern in patterns:
            patterns[pattern] += count
        else:
            patterns[pattern] = count
    
    for pattern, count in sorted(patterns.items(), key=lambda x: -x[1])[:10]:
        print(f"   {count:3d}x  {pattern}")
    
    print()
    print("💡 Analysis:")
    
    # Check if Nexus incidents still exist
    nexus_count = sum(count for pattern, count in patterns.items() if '/nexus/' in pattern)
    if nexus_count > 0:
        print(f"   ⚠️  {nexus_count} Nexus incidents still occurring!")
        print("       Expected 0 after fix deployment")
    else:
        print("   ✅ No Nexus incidents - fix successful!")
    
    # Check for new patterns
    print()
    print(f"   Total unique patterns: {len(patterns)}")
    print(f"   Total incident count: {sum(patterns.values())}")

if __name__ == "__main__":
    main()
