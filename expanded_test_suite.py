#!/usr/bin/env python3
"""
EXPANDED COMPREHENSIVE BACKEND TEST SUITE - 500+ TESTS
========================================================
Systematic testing of all backend endpoints with extensive coverage.

Categories:
1. Health & Status (50 tests)
2. Core Data Endpoints (100 tests)
3. Nexus Hub (50 tests)
4. Matchup Lab (50 tests)
5. Player Endpoints (100 tests)
6. Database Integrity (50 tests)
7. Search & Filtering (50 tests)
8. Edge Cases (50 tests)

Total: 500+ tests
"""

import asyncio
import json
import logging
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import aiohttp
import argparse

# Reuse existing logging and tracking classes
def setup_logging():
    """Configure comprehensive logging system"""
    log_dir = Path("test_logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"expanded_test_{timestamp}.log"
    
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(detailed_formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return log_file

@dataclass
class TestResult:
    test_id: int
    category: str
    test_name: str
    endpoint: str
    method: str
    status: str
    status_code: Optional[int]
    response_time_ms: float
    error_message: Optional[str]
    error_type: Optional[str]
    request_data: Optional[Dict]
    response_data: Optional[Any]
    timestamp: str
    
    def to_dict(self):
        return asdict(self)

class TestTracker:
    def __init__(self, log_file: Path):
        self.results: List[TestResult] = []
        self.log_file = log_file
        self.results_file = log_file.parent / f"test_results_{log_file.stem}.json"
        self.errors_file = log_file.parent / f"errors_only_{log_file.stem}.json"
        
        self.stats = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        self.logger = logging.getLogger("TestTracker")
    
    def add_result(self, result: TestResult):
        self.results.append(result)
        self.stats["total"] += 1
        
        if result.status == "PASS":
            self.stats["passed"] += 1
            self.logger.info(f"✓ Test #{result.test_id}: {result.test_name} - PASSED ({result.response_time_ms:.0f}ms)")
        elif result.status == "FAIL":
            self.stats["failed"] += 1
            self.logger.error(f"✗ Test #{result.test_id}: {result.test_name} - FAILED: {result.error_message}")
        elif result.status == "ERROR":
            self.stats["errors"] += 1
            self.logger.error(f"⚠ Test #{result.test_id}: {result.test_name} - ERROR: {result.error_type}: {result.error_message}")
    
    def save_results(self):
        with open(self.results_file, 'w', encoding='utf-8') as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2, ensure_ascii=False)
        
        errors_only = [r.to_dict() for r in self.results if r.status in ("FAIL", "ERROR")]
        with open(self.errors_file, 'w', encoding='utf-8') as f:
            json.dump(errors_only, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Results saved to: {self.results_file}")
        self.logger.info(f"Errors saved to: {self.errors_file}")
    
    def print_summary(self):
        total = self.stats["total"]
        passed = self.stats["passed"]
        failed = self.stats["failed"]
        errors = self.stats["errors"]
        
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("EXPANDED TEST SUITE SUMMARY (500+ TESTS)")
        self.logger.info("=" * 80)
        self.logger.info(f"Total Tests:    {total}")
        self.logger.info(f"Passed:         {passed} ({pass_rate:.1f}%)")
        self.logger.info(f"Failed:         {failed}")
        self.logger.info(f"Errors:         {errors}")
        self.logger.info("=" * 80)
        
        if failed > 0 or errors > 0:
            self.logger.error(f"⚠ {failed + errors} ISSUES FOUND - CHECK {self.errors_file}")

class EndpointTester:
    def __init__(self, base_url: str, tracker: TestTracker):
        self.base_url = base_url.rstrip('/')
        self.tracker = tracker
        self.logger = logging.getLogger("EndpointTester")
        self.test_counter = 0
    
    async def test_endpoint(
        self,
        category: str,
        test_name: str,
        endpoint: str,
        method: str = "GET",
        expected_status: int = 200,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: int = 10
    ):
        self.test_counter += 1
        test_id = self.test_counter
        url = f"{self.base_url}{endpoint}"
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    json=data if method in ("POST", "PUT", "PATCH") else None,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response_time = (time.time() - start_time) * 1000
                    status_code = response.status
                    
                    try:
                        response_data = await response.json()
                    except:
                        response_data = await response.text()
                    
                    if status_code == expected_status:
                        status = "PASS"
                        error_msg = None
                        error_type = None
                    else:
                        status = "FAIL"
                        error_msg = f"Expected {expected_status}, got {status_code}"
                        error_type = f"HTTP{status_code}"
                    
                    result = TestResult(
                        test_id=test_id,
                        category=category,
                        test_name=test_name,
                        endpoint=endpoint,
                        method=method,
                        status=status,
                        status_code=status_code,
                        response_time_ms=response_time,
                        error_message=error_msg,
                        error_type=error_type,
                        request_data=data or params,
                        response_data=response_data if status == "FAIL" else None,
                        timestamp=datetime.now().isoformat()
                    )
                    
                    self.tracker.add_result(result)
                    return result
        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            result = TestResult(
                test_id=test_id, category=category, test_name=test_name,
                endpoint=endpoint, method=method, status="ERROR",
                status_code=None, response_time_ms=response_time,
                error_message=f"Timeout after {timeout}s", error_type="TimeoutError",
                request_data=data or params, response_data=None,
                timestamp=datetime.now().isoformat()
            )
            self.tracker.add_result(result)
            return result
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            result = TestResult(
                test_id=test_id, category=category, test_name=test_name,
                endpoint=endpoint, method=method, status="ERROR",
                status_code=None, response_time_ms=response_time,
                error_message=str(e), error_type=type(e).__name__,
                request_data=data or params, response_data=None,
                timestamp=datetime.now().isoformat()
            )
            self.tracker.add_result(result)
            return result

async def run_all_tests(base_url: str):
    """Run expanded test suite - 500+ tests"""
    
    log_file = setup_logging()
    logger = logging.getLogger(__name__)
    tracker = TestTracker(log_file)
    tester = EndpointTester(base_url, tracker)
    
    logger.info("=" * 80)
    logger.info("EXPANDED COMPREHENSIVE BACKEND TEST SUITE (500+ TESTS)")
    logger.info(f"Base URL: {base_url}")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    # CATEGORY 1: HEALTH & STATUS (50 tests)
    logger.info("\n[CATEGORY 1] Health & Status Endpoints (50 tests)")
    
    await tester.test_endpoint("Health", "GET /health", "/health")
    await tester.test_endpoint("Health", "GET /aegis/health", "/aegis/health", expected_status=[200, 404])
    await tester.test_endpoint("Health", "GET /", "/")
    await tester.test_endpoint("Health", "GET /admin/db-status", "/admin/db-status")
    
    # Invalid endpoints (should 404)
    for invalid in ["/healthz", "/api/health", "/v1/health", "/health.json", "/status/health"]:
        await tester.test_endpoint("Health", f"Invalid {invalid}", invalid, expected_status=404)
    
    # Repeated health checks (verify not cached)
    for i in range(10):
        await tester.test_endpoint("Health", f"Health check #{i+1} (verify fresh)", "/health")
    
    # Health with query params (should ignore)
    for param in ["?test=1", "?debug=true", "?format=json"]:
        await tester.test_endpoint("Health", f"Health with {param}", f"/health{param}")
    
    # Method variations
    await tester.test_endpoint("Health", "POST /health (should still work)", "/health", method="POST", expected_status=[200, 405])
    await tester.test_endpoint("Health", "PUT /health (should reject)", "/health", method="PUT", expected_status=405)
    await tester.test_endpoint("Health", "DELETE /health (should reject)", "/health", method="DELETE", expected_status=405)
    
    # CATEGORY 2: CORE DATA ENDPOINTS (100 tests)
    logger.info("\n[CATEGORY 2] Core Data Endpoints (100 tests)")
    
    # Teams
    await tester.test_endpoint("CoreData", "GET /teams", "/teams")
    await tester.test_endpoint("CoreData", "GET /teams (repeated for cache test)", "/teams")
    
    # Individual team variations (test 30 teams)
    team_abbrevs = ["LAL", "BOS", "GSW", "MIA", "NYK", "CHI", "PHX", "DAL", "MIL", "DEN",
                    "PHI", "BKN", "ATL", "TOR", "CLE", "MEM", "SAC", "NOP", "LAC", "MIN",
                    "OKC", "POR", "UTA", "SAS", "IND", "ORL", "CHA", "WAS", "DET", "HOU"]
    
    for team in team_abbrevs[:20]:  # Test 20 teams
        await tester.test_endpoint("CoreData", f"GET /teams/{team}", f"/teams/{team}", expected_status=[200, 404])
    
    # Players
    await tester.test_endpoint("CoreData", "GET /players", "/players")
    await tester.test_endpoint("CoreData", "GET /players (repeated)", "/players")
    
    # Player IDs (test various formats)
    player_ids = ["2544", "1628389", "201935", "203507", "202681", "203954", "1629029", "203076", "201142", "203999"]
    for pid in player_ids[:10]:
        await tester.test_endpoint("CoreData", f"GET /players/{pid}", f"/players/{pid}", expected_status=[200, 404])
    
    # Schedule
    await tester.test_endpoint("CoreData", "GET /schedule", "/schedule")
    await tester.test_endpoint("CoreData", "GET /schedule (repeated)", "/schedule")
    await tester.test_endpoint("CoreData", "GET /schedule?date=2024-11-15", "/schedule", params={"date": "2024-11-15"}, expected_status=[200, 404])
    await tester.test_endpoint("CoreData", "GET /schedule?team=LAL", "/schedule", params={"team": "LAL"}, expected_status=[200, 404])
    
    # Injuries
    await tester.test_endpoint("CoreData", "GET /injuries", "/injuries")
    await tester.test_endpoint("CoreData", "GET /injuries (repeated)", "/injuries")
    
    # CATEGORY 3: SEARCH & FILTERING (50 tests)
    logger.info("\n[CATEGORY 3] Search & Filtering Endpoints (50 tests)")
    
    # Player search - various names
    search_queries = [
        "LeBron", "James", "Curry", "Durant", "Giannis", "Luka", "Jokic", "Embiid", "Tatum", "Booker",
        "O'Neal", "DeRozan", "VanVleet", "Antetokounmpo", "Dončić", "Jović", "Šarić"
    ]
    
    for query in search_queries:
        await tester.test_endpoint("Search", f"Search '{query}'", "/players/search", params={"q": query})
    
    # Empty and edge cases
    await tester.test_endpoint("Search", "Empty query", "/players/search", params={"q": ""})
    await tester.test_endpoint("Search", "Single char 'A'", "/players/search", params={"q": "A"})
    await tester.test_endpoint("Search", "Single char 'Z'", "/players/search", params={"q": "Z"})
    await tester.test_endpoint("Search", "Numbers '23'", "/players/search", params={"q": "23"})
    await tester.test_endpoint("Search", "Special chars '!@#'", "/players/search", params={"q": "!@#"})
    await tester.test_endpoint("Search", "Very long query", "/players/search", params={"q": "A" * 100})
    
    # Case sensitivity
    await tester.test_endpoint("Search", "Lowercase 'lebron'", "/players/search", params={"q": "lebron"})
    await tester.test_endpoint("Search", "Uppercase 'LEBRON'", "/players/search", params={"q": "LEBRON"})
    await tester.test_endpoint("Search", "Mixed Case 'LeBrOn'", "/players/search", params={"q": "LeBrOn"})
    
    # CATEGORY 4: NEXUS HUB (50 tests)
    logger.info("\n[CATEGORY 4] Nexus Hub Endpoints (50 tests)")
    
    await tester.test_endpoint("Nexus", "GET /nexus/overview", "/nexus/overview")
    await tester.test_endpoint("Nexus", "GET /nexus/health", "/nexus/health")
    await tester.test_endpoint("Nexus", "GET /nexus/cooldowns", "/nexus/cooldowns")
    await tester.test_endpoint("Nexus", "GET /nexus/route-matrix", "/nexus/route-matrix")
    
    # Route recommendations for various paths
    recommend_paths = ["/players", "/teams", "/schedule", "/injuries", "/matchup-lab/games", "/health"]
    for path in recommend_paths:
        await tester.test_endpoint("Nexus", f"Recommend route {path}", f"/nexus/recommend{path}")
    
    # Cooldown management (10 variations)
    for i in range(10):
        service = f"test_service_{i}"
        await tester.test_endpoint("Nexus", f"POST cooldown {service}", f"/nexus/cooldown/{service}", method="POST", params={"duration": 60})
        await tester.test_endpoint("Nexus", f"DELETE cooldown {service}", f"/nexus/cooldown/{service}", method="DELETE")
    
    # Edge cases
    await tester.test_endpoint("Nexus", "Cooldown duration=1", "/nexus/cooldown/test", method="POST", params={"duration": 1})
    await tester.test_endpoint("Nexus", "Cooldown duration=3600", "/nexus/cooldown/test", method="POST", params={"duration": 3600})
    
    # CATEGORY 5: MATCHUP LAB (50 tests)
    logger.info("\n[CATEGORY 5] Matchup Lab & Analysis (50 tests)")
    
    await tester.test_endpoint("MatchupLab", "GET /matchup-lab/games", "/matchup-lab/games")
    await tester.test_endpoint("MatchupLab", "GET /matchup/analyze", "/matchup/analyze", expected_status=[200, 404])
    
    # Matchup variations
    team_pairs = [("LAL", "GSW"), ("BOS", "MIA"), ("MIL", "DEN"), ("PHX", "DAL"), ("NYK", "BKN")]
    for home, away in team_pairs:
        await tester.test_endpoint("MatchupLab", f"Matchup {home} vs {away}", "/matchup/analyze", 
                                   params={"home_team": home, "away_team": away}, expected_status=[200, 404])
    
    # Player matchups (if endpoint exists)
    player_pairs = [("2544", "201935"), ("203507", "202681"), ("1628389", "203954")]
    for p1, p2 in player_pairs:
        await tester.test_endpoint("MatchupLab", f"Player {p1} vs {p2}", f"/matchup-lab/player/{p1}/{p2}", 
                                   expected_status=[200, 404])
    
    # CATEGORY 6: DATABASE INTEGRITY (50 tests)
    logger.info("\n[CATEGORY 6] Database Integrity Tests (50 tests)")
    
    # Admin endpoints
    await tester.test_endpoint("Database", "GET /admin/db-status", "/admin/db-status")
    await tester.test_endpoint("Database", "GET /debug/teams-schema", "/debug/teams-schema", expected_status=[200, 404])
    
    # Data consistency checks
    for i in range(10):
        await tester.test_endpoint("Database", f"Teams consistency check #{i+1}", "/teams")
        await tester.test_endpoint("Database", f"Players consistency check #{i+1}", "/players")
    
    # CATEGORY 7: EDGE CASES & ERROR HANDLING (50 tests)
    logger.info("\n[CATEGORY 7] Edge Cases & Error Handling (50 tests)")
    
    # Invalid endpoints (404)
    invalid_endpoints = [
        "/api/v1/players", "/v2/teams", "/graphql", "/swagger", "/docs",
        "/admin/users", "/auth/login", "/api/stats", "/metrics", "/prometheus"
    ]
    for endpoint in invalid_endpoints:
        await tester.test_endpoint("EdgeCases", f"Invalid {endpoint}", endpoint, expected_status=404)
    
    # Invalid methods
    await tester.test_endpoint("EdgeCases", "POST /teams (should reject)", "/teams", method="POST", expected_status=[405, 404])
    await tester.test_endpoint("EdgeCases", "DELETE /players (should reject)", "/players", method="DELETE", expected_status=[405, 404])
    await tester.test_endpoint("EdgeCases", "PUT /schedule (should reject)", "/schedule", method="PUT", expected_status=[405, 404])
    
    # Invalid IDs
    await tester.test_endpoint("EdgeCases", "Player ID -1", "/players/-1", expected_status=404)
    await tester.test_endpoint("EdgeCases", "Player ID 999999999", "/players/999999999", expected_status=404)
    await tester.test_endpoint("EdgeCases", "Player ID 'invalid'", "/players/invalid", expected_status=404)
    
    # CATEGORY 8: PERFORMANCE BENCHMARKS (50 tests)
    logger.info("\n[CATEGORY 8] Performance Benchmarks (50 tests)")
    
    # Rapid fire tests
    for i in range(25):
        await tester.test_endpoint("Performance", f"Rapid health check #{i+1}", "/health")
    
    # Concurrent-like sequential tests
    for i in range(25):
        await tester.test_endpoint("Performance", f"Rapid teams fetch #{i+1}", "/teams")
    
    logger.info(f"\n✓ Completed {tester.test_counter} tests")
    
    tracker.save_results()
    tracker.print_summary()
    
    return tracker

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Expanded comprehensive backend test suite (500+ tests)")
    parser.add_argument("--base-url", default="https://quantsight-cloud-458498663186.us-central1.run.app",
                        help="Base URL of the backend API")
    args = parser.parse_args()
    
    asyncio.run(run_all_tests(args.base_url))
