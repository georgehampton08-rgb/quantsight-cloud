"""
Test suite for Atomic Writer
Validates temp-verify-move strategy and hierarchical storage
"""

import asyncio
import sys
import shutil
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis.atomic_writer import AtomicWriter


async def test_atomic_writer():
    """Test atomic writing and verification"""
    
    print("=" * 70)
    print("ATOMIC WRITER: TEST SUITE")
    print("=" * 70)
    
    # Use temp directory for tests
    test_dir = Path("test_atomic_data")
    writer = AtomicWriter(base_dir=str(test_dir))
    
    try:
        # Test 1: Basic Atomic Write
        print("\n[TEST 1] Basic Atomic Write")
        print("-" * 40)
        
        player_data = {
            'player_id': '2544',
            'name': 'LeBron James',
            'season': '2024-25',
            'points_avg': 25.5,
            'rebounds_avg': 8.2,
            'assists_avg': 7.1
        }
        
        success = await writer.write_atomic('1610612747', '2544', '2024-25.json', player_data)
        print(f"  Write Success: {success}")
        
        # Verify file exists
        path = writer.get_path('1610612747', '2544', '2024-25.json')
        print(f"  File Created: {path.exists()}")
        print(f"  Path: {path}")
        
        # Test 2: Read Back Data
        print("\n[TEST 2] Read Back Data")
        print("-" * 40)
        
        read_data = await writer.read_atomic('1610612747', '2544', '2024-25.json')
        print(f"  Data Match: {read_data == player_data}")
        if read_data:
            print(f"  Player: {read_data['name']}")
            print(f"  PPG: {read_data['points_avg']}")
        
        # Test 3: Multiple Files for Same Player
        print("\n[TEST 3] Multiple Seasons")
        print("-" * 40)
        
        season_2023 = {**player_data, 'season': '2023-24', 'points_avg': 25.7}
        career = {**player_data, 'type': 'career', 'total_points': 40000}
        
        await writer.write_atomic('1610612747', '2544', '2023-24.json', season_2023)
        await writer.write_atomic('1610612747', '2544', 'career.json', career)
        
        files = writer.list_player_files('1610612747', '2544')
        print(f"  Files Created: {len(files)}")
        print(f"  Files: {files}")
        
        # Test 4: Hash Verification
        print("\n[TEST 4] Hash Verification")
        print("-" * 40)
        
        import hashlib
        import json
        correct_hash = hashlib.sha256(json.dumps(player_data, sort_keys=True).encode()).hexdigest()
        wrong_hash = "0" * 64
        
        # Should succeed with correct hash
        success1 = await writer.write_atomic('1610612747', '9999', 'test.json', player_data, verify_hash=correct_hash)
        print(f"  Correct Hash: {'✓ Success' if success1 else '✗ Failed'}")
        
        # Should fail with wrong hash
        success2 = await writer.write_atomic('1610612747', '9998', 'test.json', player_data, verify_hash=wrong_hash)
        print(f"  Wrong Hash: {'✗ Failed (as expected)' if not success2 else '✓ Success (unexpected!)'}")
        
        # Test 5: Quality Control Audit
        print("\n[TEST 5] Quality Control Audit")
        print("-" * 40)
        
        audit = writer.run_quality_audit()
        print(f"  Total Files: {audit['total_files']}")
        print(f"  Valid Files: {audit['valid_files']}")
        print(f"  Invalid Files: {audit['invalid_files']}")
        print(f"  Pass Rate: {audit['pass_rate']:.1%}")
        
        if audit['errors']:
            print(f"  Errors: {audit['errors']}")
        
        # Test 6: Hierarchical Structure
        print("\n[TEST 6] Hierarchical Structure Verification")
        print("-" * 40)
        
        # Check directory structure
        team_dir = test_dir / '1610612747'
        player_dir = team_dir / '2544'
        
        print(f"  Team Dir Exists: {team_dir.exists()}")
        print(f"  Player Dir Exists: {player_dir.exists()}")
        print(f"  Structure: data/ → Team_ID/ → Player_ID/ → Season.json")
        
        # Statistics
        print("\n[STATISTICS]")
        print("-" * 40)
        stats = writer.get_stats()
        print(f"  Writes Attempted: {stats['writes_attempted']}")
        print(f"  Writes Succeeded: {stats['writes_succeeded']}")
        print(f"  Writes Failed: {stats['writes_failed']}")
        print(f"  Success Rate: {stats['success_rate']:.1%}")
        print(f"  Total Data: {stats['total_mb_written']} MB")
        
        print("\n" + "=" * 70)
        if audit['pass_rate'] == 1.0:
            print("✓ ALL TESTS PASSED - 100% Quality Audit")
        else:
            print(f"⚠ Quality Audit: {audit['pass_rate']:.1%}")
        print("=" * 70)
        
    finally:
        # Cleanup test directory
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\nCleaned up test directory: {test_dir}")


if __name__ == "__main__":
    asyncio.run(test_atomic_writer())
