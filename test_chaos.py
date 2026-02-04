"""
CHAOS TEST: Stress testing the matchup system
==============================================
Tries to break the system with:
1. Invalid inputs
2. Missing data scenarios
3. Concurrent requests
4. Edge cases
"""

import sqlite3
import json
import sys
import random
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup paths
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from data_paths import get_db_path, get_data_health
from services.defense_matrix import DefenseMatrix
from services.nemesis_engine import NemesisEngine
from services.pace_engine import PaceEngine


class ChaosTest:
    """Chaos testing suite"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def test(self, name, func):
        """Run a single test"""
        try:
            result = func()
            if result:
                print(f"  ✅ {name}")
                self.passed += 1
                return True
            else:
                print(f"  ❌ {name}")
                self.failed += 1
                return False
        except Exception as e:
            print(f"  💥 {name}: {e}")
            self.failed += 1
            self.errors.append((name, str(e)))
            return False
    
    def run_all(self):
        """Run all chaos tests"""
        print("\n" + "="*60)
        print("🔥 CHAOS TEST SUITE")
        print("="*60)
        
        # Category 1: Invalid Team Codes
        print("\n--- Invalid Team Codes ---")
        self.test("Empty team code", lambda: DefenseMatrix.get_profile("").get('available') == False)
        self.test("Fake team ZZZZ", lambda: DefenseMatrix.get_profile("ZZZZ").get('available') == False)
        self.test("Numeric team 12345", lambda: DefenseMatrix.get_profile("12345").get('available') == False)
        self.test("Special chars !@#$", lambda: DefenseMatrix.get_profile("!@#$").get('available') == False)
        self.test("Very long team name", lambda: DefenseMatrix.get_profile("A"*1000).get('available') == False)
        self.test("Unicode team", lambda: DefenseMatrix.get_profile("日本語").get('available') == False)
        
        # Category 2: Invalid Player IDs
        print("\n--- Invalid Player IDs ---")
        self.test("Negative player ID", lambda: NemesisEngine.analyze_head_to_head("-1", "LAL", 20.0).get('available') == False)
        self.test("Zero player ID", lambda: NemesisEngine.analyze_head_to_head("0", "LAL", 20.0).get('available') == False)
        self.test("Very large player ID", lambda: NemesisEngine.analyze_head_to_head("9999999999", "LAL", 20.0).get('available') == False)
        self.test("String player ID", lambda: NemesisEngine.analyze_head_to_head("not_a_number", "LAL", 20.0).get('available') == False)
        
        # Category 3: Edge Case PPG Values
        print("\n--- Edge Case PPG Values ---")
        self.test("Zero PPG", lambda: NemesisEngine.analyze_head_to_head("12345", "LAL", 0.0).get('delta_percent') == 0.0)
        self.test("Negative PPG", lambda: NemesisEngine.analyze_head_to_head("12345", "LAL", -10.0) is not None)
        self.test("Very high PPG (100)", lambda: NemesisEngine.analyze_head_to_head("12345", "LAL", 100.0) is not None)
        
        # Category 4: Pace Edge Cases
        print("\n--- Pace Engine Edge Cases ---")
        self.test("Same team vs itself", lambda: PaceEngine.calculate_multiplier("LAL", "LAL") in [0.88, 1.0, 1.12])
        self.test("Invalid team pace", lambda: PaceEngine.calculate_multiplier("FAKE1", "FAKE2") == 1.0)
        self.test("Empty team vs valid", lambda: PaceEngine.calculate_multiplier("", "LAL") == 1.0)
        
        # Category 5: Database Stress
        print("\n--- Database Stress Test ---")
        self.test("Rapid profile reads (50x)", self._stress_defense_matrix)
        self.test("Rapid nemesis reads (50x)", self._stress_nemesis_engine)
        self.test("Rapid pace reads (50x)", self._stress_pace_engine)
        
        # Category 6: Concurrent Access
        print("\n--- Concurrent Access Test ---")
        self.test("20 concurrent defense checks", self._concurrent_defense)
        self.test("20 concurrent nemesis checks", self._concurrent_nemesis)
        
        # Category 7: Cache Manipulation
        print("\n--- Cache Manipulation ---")
        self.test("Clear defense cache", self._test_cache_clear)
        self.test("Re-read after cache clear", lambda: DefenseMatrix.get_profile("BOS").get('available') == True)
        
        # Category 8: Real Data Verification
        print("\n--- Real Data Sanity Checks ---")
        self.test("BOS def_rating in range", self._check_bos_defense)
        self.test("LAL pace in range", self._check_lal_pace)
        
        # Summary
        print("\n" + "="*60)
        print(f"🏁 CHAOS TEST RESULTS")
        print(f"   Passed: {self.passed}")
        print(f"   Failed: {self.failed}")
        print(f"   Error Rate: {self.failed/(self.passed+self.failed)*100:.1f}%")
        
        if self.errors:
            print(f"\n   💥 Errors encountered:")
            for name, err in self.errors[:5]:
                print(f"      - {name}: {err[:50]}...")
        
        if self.failed == 0:
            print(f"\n   🎉 CHAOS TEST PASSED - System is resilient!")
        else:
            print(f"\n   ⚠️  {self.failed} tests failed - review above")
        
        return self.failed == 0
    
    def _stress_defense_matrix(self):
        """Rapid reads"""
        teams = ["LAL", "BOS", "GSW", "MIA", "CLE"]
        for _ in range(50):
            team = random.choice(teams)
            DefenseMatrix.get_profile(team)
        return True
    
    def _stress_nemesis_engine(self):
        """Rapid nemesis reads"""
        for _ in range(50):
            NemesisEngine.analyze_head_to_head(str(random.randint(1, 999999)), "LAL", 20.0)
        return True
    
    def _stress_pace_engine(self):
        """Rapid pace reads"""
        teams = ["LAL", "BOS", "GSW", "MIA", "CLE"]
        for _ in range(50):
            t1 = random.choice(teams)
            t2 = random.choice(teams)
            PaceEngine.calculate_multiplier(t1, t2)
        return True
    
    def _concurrent_defense(self):
        """Concurrent defense checks"""
        def check(team):
            return DefenseMatrix.get_profile(team)
        
        teams = ["LAL", "BOS", "GSW", "MIA", "CLE", "NYK", "CHI", "DAL", "PHX", "DEN"] * 2
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check, t) for t in teams]
            results = [f.result() for f in as_completed(futures)]
        
        return len(results) == 20
    
    def _concurrent_nemesis(self):
        """Concurrent nemesis checks"""
        def check(player_id):
            return NemesisEngine.analyze_head_to_head(player_id, "LAL", 20.0)
        
        ids = [str(i) for i in range(1000, 1020)]
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(check, pid) for pid in ids]
            results = [f.result() for f in as_completed(futures)]
        
        return len(results) == 20
    
    def _test_cache_clear(self):
        """Test cache clearing"""
        # Load something into cache
        DefenseMatrix.get_profile("BOS")
        # Clear cache
        DefenseMatrix.clear_cache()
        # Should still work
        result = DefenseMatrix.get_profile("BOS")
        return result is not None
    
    def _check_bos_defense(self):
        """Sanity check BOS defense data"""
        profile = DefenseMatrix.get_profile("BOS")
        if not profile.get('available'):
            return False
        # BOS is a good defensive team, should have low opp_pts
        opp_pts = profile.get('opp_pts', 0)
        return 100 < opp_pts < 130  # Reasonable range
    
    def _check_lal_pace(self):
        """Sanity check LAL pace data"""
        pace = PaceEngine.get_team_pace("LAL")
        if pace is None:
            return False
        # NBA pace is usually 95-105
        return 90 < pace < 110


if __name__ == '__main__':
    chaos = ChaosTest()
    success = chaos.run_all()
    
    # Save results
    output_file = SCRIPT_DIR / 'data' / 'chaos_test_results.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'passed': chaos.passed,
            'failed': chaos.failed,
            'errors': chaos.errors,
            'success': success
        }, f, indent=2)
    
    print(f"\n   📁 Results saved to: {output_file}")
    
    sys.exit(0 if success else 1)
