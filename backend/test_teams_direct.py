"""Quick test of teams query directly"""
import requests

# Direct test
url = "https://quantsight-cloud-458498663186.us-central1.run.app/teams"
try:
    response = requests.get(url, timeout=15)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
