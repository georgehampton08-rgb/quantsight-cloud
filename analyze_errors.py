"""
Analyze Cloud Run Error Logs
"""
import json
from collections import defaultdict

# Load logs
with open('cloud_errors.json', 'r') as f:
    logs = json.load(f)

print(f"Total logs found: {len(logs)}")
print("=" * 60)

# Categorize by severity
severities = defaultdict(int)
for log in logs:
    sev = log.get('severity', 'UNKNOWN')
    severities[sev] += 1

print("\nBy Severity:")
for sev, count in sorted(severities.items()):
    print(f"  {sev}: {count}")

# Group errors by type
error_types = defaultdict(list)
for log in logs:
    msg = log.get('textPayload', '')
    if not msg:
        json_payload = log.get('jsonPayload', {})
        msg = json_payload.get('message', str(json_payload))
    
    # Categorize errors
    if 'PORT' in msg or 'port' in msg:
        error_types['PORT Configuration'].append(msg[:150])
    elif '404' in msg or 'Not Found' in msg:
        error_types['404 Not Found'].append(msg[:150])
    elif '500' in msg or 'Internal' in msg:
        error_types['500 Internal Error'].append(msg[:150])
    elif 'import' in msg.lower() or 'module' in msg.lower():
        error_types['Import/Module Errors'].append(msg[:150])
    elif 'redis' in msg.lower():
        error_types['Redis Issues'].append(msg[:150])
    elif 'timeout' in msg.lower():
        error_types['Timeout Issues'].append(msg[:150])
    elif 'container' in msg.lower():
        error_types['Container Issues'].append(msg[:150])
    elif log.get('severity') == 'ERROR':
        error_types['Other Errors'].append(msg[:150])
    elif log.get('severity') == 'WARNING':
        error_types['Warnings'].append(msg[:150])

print("\n" + "=" * 60)
print("ERRORS BY CATEGORY:")
print("=" * 60)

for category, messages in sorted(error_types.items()):
    print(f"\n### {category} ({len(messages)} occurrences)")
    unique_msgs = list(set(messages))[:5]  # Show max 5 unique
    for msg in unique_msgs:
        if msg.strip():
            print(f"  - {msg[:100]}...")

# Generate summary report
print("\n" + "=" * 60)
print("SUMMARY REPORT")
print("=" * 60)

report = {
    "total_logs": len(logs),
    "severities": dict(severities),
    "categories": {k: len(v) for k, v in error_types.items()}
}

with open('error_analysis_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print(f"\nReport saved to: error_analysis_report.json")
