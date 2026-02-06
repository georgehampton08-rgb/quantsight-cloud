"""
Production Deployment Validation Script
========================================
Tests both player search and AI Analysis endpoints
"""

import requests
import json
from datetime import datetime

BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

print("\n" + "="*70)
print("🧪 PRODUCTION ENDPOINT VALIDATION")
print("="*70 + "\n")

# Test 1: Health Check
print("1️⃣ Health Check...")
try:
    res = requests.get(f"{BASE_URL}/health", timeout=10)
    if res.status_code == 200:
        print("   ✅ PASS - Service is running")
    else:
        print(f"   ❌ FAIL - Status {res.status_code}")
except Exception as e:
    print(f"   ❌ ERROR - {e}")

# Test 2: Player Search (Empty Query)
print("\n2️⃣ Player Search - Empty Query...")
try:
    res = requests.get(f"{BASE_URL}/players/search?q=", timeout=10)
    if res.status_code == 200:
        data = res.json()
        count = len(data)
        print(f"   ✅ PASS - Returned {count} players")
        if count > 0:
            print(f"   Sample: {data[0].get('name', 'N/A')}")
    else:
        print(f"   ❌ FAIL - Status {res.status_code}")
        print(f"   Response: {res.text[:200]}")
except Exception as e:
    print(f"   ❌ ERROR - {e}")

# Test 3: Player Search (With Query)
print("\n3️⃣ Player Search - With Query 'lebron'...")
try:
    res = requests.get(f"{BASE_URL}/players/search?q=lebron", timeout=10)
    if res.status_code == 200:
        data = res.json()
        count = len(data)
        print(f"   ✅ PASS - Found {count} result(s)")
        if count > 0:
            print(f"   Player: {data[0].get('name', 'N/A')}")
    else:
        print(f"   ❌ FAIL - Status {res.status_code}")
except Exception as e:
    print(f"   ❌ ERROR - {e}")

# Test 4: AI Analysis (Aegis Simulate)
print("\n4️⃣ AI Analysis - Aegis Simulation...")
try:
    # LeBron James = 2544, vs Celtics = 1610612738
    res = requests.get(
        f"{BASE_URL}/aegis/simulate/2544?opponent_id=1610612738",
        timeout=15
    )
    if res.status_code == 200:
        data = res.json()
        print("   ✅ PASS - Simulation returned successfully")
        print(f"   Player ID: {data.get('player_id', 'N/A')}")
        print(f"   Confidence: {data.get('confidence', 'N/A')}")
        
        if 'projections' in data:
            proj = data['projections']
            pts = proj.get('pts', {})
            print(f"   Points: {pts.get('floor', '?')} / {pts.get('expected_value', '?')} / {pts.get('ceiling', '?')}")
    elif res.status_code == 404:
        print(f"   ❌ FAIL - Endpoint not found (router not mounted)")
        print(f"   Response: {res.text[:200]}")
    else:
        print(f"   ❌ FAIL - Status {res.status_code}")
        print(f"   Response: {res.text[:500]}")
except Exception as e:
    print(f"   ❌ ERROR - {e}")

# Test 5: Vanguard Health (Bonus)
print("\n5️⃣ Vanguard Health...")
try:
    res = requests.get(f"{BASE_URL}/vanguard/health", timeout=10)
    if res.status_code == 200:
        data = res.json()
        print(f"   ✅ PASS - Status: {data.get('status', 'N/A')}")
    else:
        print(f"   ⚠️  Status {res.status_code} (may not be deployed)")
except Exception as e:
    print(f"   ⚠️  Not available")

print("\n" + "="*70)
print("📋 VALIDATION SUMMARY")
print("="*70)
print("\n Expected Results:")
print("   [✅] Health check passes")
print("   [✅] Player search returns results")
print("   [✅] AI Analysis returns projections")
print("\n If AI Analysis fails with 404:")
print("   → Router not mounted in main.py")
print("   → Check deployment logs")
print("\n" + "="*70 + "\n")
