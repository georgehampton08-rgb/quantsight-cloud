"""Check teams table structure via admin endpoint"""
import requests

# Test init-schema to see what columns are created
url = "https://quantsight-cloud-458498663186.us-central1.run.app/admin/init-schema"
try:
    response = requests.post(url, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
