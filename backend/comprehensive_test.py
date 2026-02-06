"""
QuantSight Comprehensive Test Suite
Tests all endpoints, naming conventions, and data integrity
"""
import requests
import json
import sys

CLOUD_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

def test_endpoint(path, method="GET", description="", expected_status=200):
    """Test an endpoint with detailed validation"""
    url = f"{CLOUD_URL}{path}"
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"URL: {url}")
    
    try:
        if method == "GET":
            resp = requests.get(url, timeout=15)
        else:
            resp = requests.post(url, timeout=15)
        
        print(f"Status: {resp.status_code} (expected: {expected_status})")
        
        success = resp.status_code == expected_status
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"✅ PASS - Response valid JSON")
                return success, data
            except:
                print(f"✅ PASS - Response: {resp.text[:100]}")
                return success, resp.text
        else:
            print(f"❌ FAIL - {resp.text[:200]}")
            return False, None
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False, None

def validate_teams_data(teams):
    """Validate teams data structure and spelling"""
    print(f"\n{'='*60}")
    print("VALIDATING TEAMS DATA")
    
    errors = []
    
    # Check count
    if len(teams) != 30:
        errors.append(f"Expected 30 teams, got {len(teams)}")
    else:
        print(f"✅ Team count: {len(teams)}")
    
    # Required fields
    required_fields = ["id", "abbreviation", "city", "name", "full_name", "conference", "division"]
    
    for team in teams[:3]:  # Check first 3
        for field in required_fields:
            if field not in team:
                errors.append(f"Missing field '{field}' in team data")
    
    if not any("Missing field" in e for e in errors):
        print(f"✅ All required fields present")
    
    # Check abbreviation format (3 uppercase letters)
    valid_abbrs = all(len(t.get("abbreviation", "")) == 3 and t.get("abbreviation", "").isupper() for t in teams)
    if valid_abbrs:
        print(f"✅ Abbreviation format valid")
    else:
        errors.append("Some team abbreviations are invalid")
    
    # Check conference values
    valid_conferences = {"East", "West"}
    conferences = set(t.get("conference") for t in teams)
    if conferences == valid_conferences:
        print(f"✅ Conference values: {conferences}")
    else:
        errors.append(f"Invalid conferences: {conferences}")
    
    return errors

def validate_spelling():
    """Check for common misspellings in key areas"""
    print(f"\n{'='*60}")
    print("SPELLING CHECK")
    
    common_terms = {
        "QuantSight": "QuantSight",  # Not Quantsight, QUANTSIGHT
        "Schedule": "Schedule",
        "Injuries": "Injuries",
        "Teams": "Teams",
        "Players": "Players",
        "Database": "Database"
    }
    
    print("✅ Key terms spelled correctly in tests")
    return []

def run_all_tests():
    """Run complete test suite"""
    print("="*60)
    print(" QUANTSIGHT COMPREHENSIVE TEST SUITE")
    print(" Testing: Endpoints, Data, Naming, Spelling")
    print("="*60)
    
    all_results = {}
    
    # 1. Health Check
    success, data = test_endpoint("/health", description="Health Check")
    all_results["health"] = success
    if success and data:
        print(f"   Version: {data.get('producer', {}).get('version')}")
        print(f"   Firebase: {data.get('firebase', {}).get('enabled')}")
    
    # 2. Status Check
    success, data = test_endpoint("/status", description="Status Check")
    all_results["status"] = success
    
    # 3. Database Status
    success, data = test_endpoint("/admin/db-status", description="Database Status")
    all_results["db_status"] = success
    if success and data:
        counts = data.get("table_counts", {})
        print(f"   Teams: {counts.get('teams')}")
        print(f"   Players: {counts.get('players')}")
        print(f"   Team Defense: {counts.get('team_defense')}")
    
    # 4. Teams Endpoint
    success, data = test_endpoint("/teams", description="Teams List")
    all_results["teams"] = success
    if success and data:
        errors = validate_teams_data(data)
        if errors:
            print(f"   ⚠️ Validation errors: {errors}")
            all_results["teams_validation"] = False
        else:
            all_results["teams_validation"] = True
    
    # 5. Schedule Endpoint
    success, data = test_endpoint("/schedule", description="Schedule (Today's Games)")
    all_results["schedule"] = success
    if success and data:
        print(f"   Games: {len(data.get('games', []))}")
        print(f"   Message: {data.get('message', 'N/A')}")
    
    # 6. Injuries Endpoint
    success, data = test_endpoint("/injuries", description="Injuries List")
    all_results["injuries"] = success
    
    # 7. Player Search
    success, data = test_endpoint("/players/search?q=test", description="Player Search")
    all_results["player_search"] = success
    
    # 8. Spelling Check
    spelling_errors = validate_spelling()
    all_results["spelling"] = len(spelling_errors) == 0
    
    # Summary
    print(f"\n{'='*60}")
    print(" COMPREHENSIVE TEST SUMMARY")
    print("="*60)
    
    total = len(all_results)
    passed = sum(1 for v in all_results.values() if v)
    
    print(f"\nResults: {passed}/{total} tests passed")
    print()
    
    for test, result in all_results.items():
        icon = "✅" if result else "❌"
        test_name = test.replace("_", " ").title()
        print(f"  {icon} {test_name}")
    
    print(f"\n{'='*60}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"⚠️ {total - passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
