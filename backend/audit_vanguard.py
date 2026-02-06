import sys
sys.path.insert(0, r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\backend')

from vanguard.archivist import VanguardArchivist
from collections import defaultdict

# Initialize Vanguard
v = VanguardArchivist()

# Get all incidents from last 7 days
incidents = v.get_recent_incidents(hours=168)

print(f"\n{'='*80}")
print(f"VANGUARD INCIDENT AUDIT - Last 7 Days")
print(f"{'='*80}\n")
print(f"Total Incidents: {len(incidents)}\n")

# Categorize by severity
by_severity = defaultdict(list)
by_type = defaultdict(list)
by_endpoint = defaultdict(list)

for inc in incidents:
    by_severity[inc['severity']].append(inc)
    by_type[inc['incident_type']].append(inc)
    by_endpoint[inc['endpoint']].append(inc)

# Print by severity
print(f"\n{'='*80}")
print("INCIDENTS BY SEVERITY")
print(f"{'='*80}\n")

for severity in ['P0', 'P1', 'P2', 'P3']:
    incidents_list = by_severity.get(severity, [])
    if incidents_list:
        print(f"\n[{severity}] - {len(incidents_list)} incidents")
        print("-" * 80)
        for inc in sorted(incidents_list, key=lambda x: -x['occurrence_count'])[:10]:  # Top 10
            print(f"  {inc['incident_type']} | {inc['endpoint']}")
            print(f"  Message: {inc['message']}")
            print(f"  Occurrences: {inc['occurrence_count']} | First: {inc['first_seen']} | Last: {inc['last_seen']}")
            print()

# Print by type
print(f"\n{'='*80}")
print("INCIDENTS BY TYPE")
print(f"{'='*80}\n")

for inc_type, incidents_list in sorted(by_type.items(), key=lambda x: -len(x[1])):
    print(f"\n{inc_type}: {len(incidents_list)} incidents")
    total_occurrences = sum(i['occurrence_count'] for i in incidents_list)
    print(f"  Total occurrences: {total_occurrences}")
    
    # Show top 3 endpoints for this type
    endpoint_counts = defaultdict(int)
    for inc in incidents_list:
        endpoint_counts[inc['endpoint']] += inc['occurrence_count']
    
    print("  Top affected endpoints:")
    for endpoint, count in sorted(endpoint_counts.items(), key=lambda x: -x[1])[:3]:
        print(f"    - {endpoint}: {count} occurrences")

# Print most problematic endpoints
print(f"\n{'='*80}")
print("MOST PROBLEMATIC ENDPOINTS")
print(f"{'='*80}\n")

endpoint_stats = []
for endpoint, incidents_list in by_endpoint.items():
    total_occurrences = sum(i['occurrence_count'] for i in incidents_list)
    p0_count = len([i for i in incidents_list if i['severity'] == 'P0'])
    p1_count = len([i for i in incidents_list if i['severity'] == 'P1'])
    
    endpoint_stats.append({
        'endpoint': endpoint,
        'total_incidents': len(incidents_list),
        'total_occurrences': total_occurrences,
        'p0_count': p0_count,
        'p1_count': p1_count
    })

for stat in sorted(endpoint_stats, key=lambda x: (-x['p0_count'], -x['p1_count'], -x['total_occurrences']))[:15]:
    print(f"\n{stat['endpoint']}")
    print(f"  Total incidents: {stat['total_incidents']} | Occurrences: {stat['total_occurrences']}")
    print(f"  P0: {stat['p0_count']} | P1: {stat['p1_count']}")

print(f"\n{'='*80}\n")
