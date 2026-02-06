"""Reseed teams to ensure proper columns"""
import requests

url = "https://quantsight-cloud-458498663186.us-central1.run.app/admin/seed-teams"
try:
    response = requests.post(url, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Now test /teams
print("\nTesting /teams endpoint:")
url2 = "https://quantsight-cloud-458498663186.us-central1.run.app/teams"
try:
    response2 = requests.get(url2, timeout=15)
    print(f"Status: {response2.status_code}")
    if response2.status_code == 200:
        teams = response2.json()
        print(f"✅ Got {len(teams)} teams")
        if teams:
            print(f"Sample: {teams[0]}")
    else:
        print(f"Error: {response2.text[:300]}")
except Exception as e:
    print(f"Error: {e}")
