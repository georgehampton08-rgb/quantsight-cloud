#!/usr/bin/env python3
"""
Direct test of Vanguard AI Analysis endpoint
Tests the analysis generation with detailed error reporting
"""
import requests
import json
import sys

API_BASE = "https://quantsight-cloud-458498663186.us-central1.run.app"

def test_ai_analysis():
    """Test AI analysis endpoint and print detailed response"""
    
    # First, get a real incident fingerprint
    print("📋 Step 1: Fetching active incidents...")
    incidents_url = f"{API_BASE}/vanguard/admin/incidents"
    
    try:
        incidents_resp = requests.get(incidents_url, timeout=10)
        incidents_resp.raise_for_status()
        incidents_data = incidents_resp.json()
        
        if not incidents_data.get("incidents"):
            print("❌ No incidents found!")
            return
        
        # Get first incident
        incident = incidents_data["incidents"][0]
        fingerprint = incident["fingerprint"]
        endpoint = incident["endpoint"]
        error_type = incident["error_type"]
        
        print(f"✅ Found incident:")
        print(f"   Fingerprint: {fingerprint[:32]}...")
        print(f"   Endpoint: {endpoint}")
        print(f"   Error: {error_type}")
        print()
        
        # Test AI analysis
        print("🤖 Step 2: Testing AI Analysis endpoint...")
        analysis_url = f"{API_BASE}/vanguard/admin/incidents/{fingerprint}/analysis"
        
        analysis_resp = requests.get(analysis_url, timeout=30)
        
        print(f"   Status Code: {analysis_resp.status_code}")
        print(f"   Headers: {dict(analysis_resp.headers)}")
        print()
        
        if analysis_resp.status_code == 200:
            analysis_data = analysis_resp.json()
            print("✅ AI Analysis Response:")
            print(json.dumps(analysis_data, indent=2))
            
            # Check if it's fallback
            confidence = analysis_data.get("confidence", 0)
            if confidence == 0:
                print("\n⚠️  WARNING: Returned fallback analysis (0% confidence)")
                print(f"   Root Cause: {analysis_data.get('root_cause')}")
        else:
            print(f"❌ Request failed with status {analysis_resp.status_code}")
            print(f"   Response: {analysis_resp.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(test_ai_analysis())
