"""
QuantSight PWA Diagnostic Script
Tests all critical endpoints and provides fix recommendations
"""
import requests
import json

CLOUD_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

def test_endpoint(path, method="GET", description=""):
    """Test an endpoint and report status"""
    url = f"{CLOUD_URL}{path}"
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    
    try:
        if method == "GET":
            resp = requests.get(url, timeout=10)
        else:
            resp = requests.post(url, timeout=10)
        
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ SUCCESS")
            try:
                data = resp.json()
                print(f"Response: {json.dumps(data, indent=2)[:500]}")
            except:
                print(f"Response: {resp.text[:200]}")
        else:
            print(f"❌ FAILED")
            print(f"Response: {resp.text[:200]}")
            
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

print("="*60)
print(" QUANTSIGHT CLOUD BACKEND DIAGNOSTIC")
print("="*60)

# Test critical endpoints
results = {}

results['health'] = test_endpoint("/health", description="Health Check")
results['status'] = test_endpoint("/status", description="Status Check")
results['db_status'] = test_endpoint("/admin/db-status", description="Database Status")
results['teams'] = test_endpoint("/teams", description="Teams List")
results['schedule'] = test_endpoint("/schedule", description="Schedule")
results['injuries'] = test_endpoint("/injuries", description="Injuries")

# Summary
print(f"\n{'='*60}")
print(" SUMMARY")
print("="*60)

working = sum(1 for v in results.values() if v)
total = len(results)

print(f"\nWorking: {working}/{total} endpoints")
print("\nStatus by Endpoint:")
for endpoint, status in results.items():
    icon = "✅" if status else "❌"
    print(f"  {icon} {endpoint}")

# Recommendations
print(f"\n{'='*60}")
print(" RECOMMENDATIONS")
print("="*60)

if not results.get('teams'):
    print("\n❌ /teams endpoint failing")
    print("   → Cloud backend missing team seeding or route")
    print("   → Check if admin routes are properly loaded")

if not results.get('schedule'):
    print("\n❌ /schedule endpoint failing")
    print("   → This endpoint may not exist on cloud backend")
    print("   → Desktop-only endpoint needs cloud migration")

print("\n")
