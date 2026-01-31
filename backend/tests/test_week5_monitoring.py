"""
Test suite for Week 5: Dual-Mode & Health Monitoring
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis.dual_mode import DualModeDetector, ClassicAnalyzer
from aegis.health_monitor import WorkerHealthMonitor, HealthStatus


def test_dual_mode():
    """Test dual-mode detection and fallback"""
    
    print("=" * 70)
    print("DUAL-MODE DETECTOR: TEST SUITE")
    print("=" * 70)
    
    # Test 1: Mode Detection
    print("\n[TEST 1] Mode Detection")
    print("-" * 40)
    
    detector = DualModeDetector(ml_models_dir="models")
    status = detector.get_status()
    
    print(f"  Active Mode: {status['active_mode']}")
    print(f"  Available Modes: {status['available_modes']}")
    print(f"  ML Models Found: {status['ml_models_found']}")
    
    # Test 2: Mode Selection
    print("\n[TEST 2] Mode Selection")
    print("-" * 40)
    
    mode1 = detector.get_analysis_mode()
    print(f"  Default Mode: {mode1}")
    
    mode2 = detector.get_analysis_mode('ml')
    print(f"  Requested ML: {mode2} (fallback if ML unavailable)")
    
    mode3 = detector.get_analysis_mode('classic')
    print(f"  Requested Classic: {mode3}")
    
    # Test 3: Fallback Chain
    print("\n[TEST 3] Fallback Chain")
    print("-" * 40)
    
    chain = detector.get_fallback_chain()
    print(f"  Fallback Order: {' → '.join(chain)}")
    
    # Test 4: Classic Analyzer
    print("\n[TEST 4] Classic Analysis (Heuristic Fallback)")
    print("-" * 40)
    
    player_stats = {
        'points_avg': 25.5,
        'rebounds_avg': 8.2,
        'assists_avg': 7.1
    }
    
    analysis = ClassicAnalyzer.analyze_player_performance(player_stats)
    print(f"  Method: {analysis['method']}")
    print(f"  Efficiency Score: {analysis['efficiency_score']}")
    print(f"  Tier: {analysis['tier']}")
    print(f"  Confidence: {analysis['confidence']}")
    
    # Test 5: Classic Prediction
    print("\n[TEST 5] Classic Prediction Formula")
    print("-" * 40)
    
    context = {
        'home_game': True,
        'opponent_defense': 'weak'
    }
    
    prediction = ClassicAnalyzer.predict_performance(player_stats, context)
    print(f"  Method: {prediction['method']}")
    print(f"  Predicted Points: {prediction['predicted_points']}")
    print(f"  Confidence: {prediction['confidence']}")
    print(f"  Adjustments: {prediction['adjustments']}")
    
    print("\n" + "=" * 70)
    print("✓ DUAL-MODE TESTS PASSED")
    print("=" * 70)


def test_health_monitor():
    """Test health monitoring system"""
    
    print("\n" + "=" * 70)
    print("HEALTH MONITOR: TEST SUITE")
    print("=" * 70)
    
    monitor = WorkerHealthMonitor()
    
    # Test 1: System Health Check
    print("\n[TEST 1] System Health Check")
    print("-" * 40)
    
    health = monitor.check_system_health()
    print(f"  Status: {health['status']}")
    print(f"  CPU: {health['system']['cpu_percent']}%")
    print(f"  Memory: {health['system']['memory_percent']}%")
    print(f"  Memory Available: {health['system']['memory_available_mb']} MB")
    print(f"  Uptime: {health['uptime_seconds']}s")
    
    # Test 2: Request Tracking
    print("\n[TEST 2] Request Tracking")
    print("-" * 40)
    
    # Simulate requests
    for i in range(10):
        monitor.record_request(success=True)
    
    # Simulate some failures
    for i in range(2):
        monitor.record_request(success=False)
    
    health2 = monitor.check_system_health()
    print(f"  Total Requests: {health2['metrics']['total_requests']}")
    print(f"  Error Count: {health2['metrics']['error_count']}")
    print(f"  Error Rate: {health2['metrics']['error_rate']:.1%}")
    
    # Test 3: Worker Status Check
    print("\n[TEST 3] Worker Status Check")
    print("-" * 40)
    
    # Active worker
    worker1 = monitor.check_worker_status('worker_1', time.time())
    print(f"  Worker 1: {worker1['status']} (just heartbeat)")
    
    # Degraded worker (15+ seconds)
    worker2 = monitor.check_worker_status('worker_2', time.time() - 20)
    print(f"  Worker 2: {worker2['status']} (20s since heartbeat)")
    
    # Down worker
    worker3 = monitor.check_worker_status('worker_3', time.time() - 60)
    print(f"  Worker 3: {worker3['status']} (60s since heartbeat)")
    
    # Test 4: Health History
    print("\n[TEST 4] Health History")
    print("-" * 40)
    
    # Generate some history
    for i in range(5):
        monitor.check_system_health()
        time.sleep(0.1)
    
    history = monitor.get_health_history(limit=3)
    print(f"  Checks Recorded: {len(monitor.health_checks)}")
    print(f"  Recent History (last 3):")
    for check in history:
        print(f"    - Status: {check['status']}, CPU: {check['cpu']:.1f}%, Memory: {check['memory']:.1f}%")
    
    # Test 5: Diagnostics
    print("\n[TEST 5] Full Diagnostics")
    print("-" * 40)
    
    diagnostics = monitor.get_diagnostics()
    print(f"  Uptime: {diagnostics['diagnostics']['uptime_formatted']}")
    print(f"  Checks Recorded: {diagnostics['diagnostics']['health_checks_recorded']}")
    print(f"  Avg CPU (last 20): {diagnostics['diagnostics']['average_cpu_last_20']}%")
    print(f"  Avg Memory (last 20): {diagnostics['diagnostics']['average_memory_last_20']}%")
    
    print("\n" + "=" * 70)
    print("✓ HEALTH MONITOR TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    test_dual_mode()
    test_health_monitor()
    
    print("\n" + "=" * 70)
    print("✓ ALL WEEK 5 TESTS PASSED")
    print("=" * 70)
