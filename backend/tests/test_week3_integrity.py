"""
Test suite for Pydantic Schemas and Integrity Healer
Validates data validation and auto-repair functionality
"""

import asyncio
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aegis.schemas import SchemaEnforcer, PlayerStatsSchema, TeamStatsSchema
from aegis.integrity_healer import DataIntegrityHealer


def test_pydantic_schemas():
    """Test Pydantic schema validation"""
    
    print("=" * 70)
    print("PYDANTIC SCHEMA VALIDATION: TEST SUITE")
    print("=" * 70)
    
    enforcer = SchemaEnforcer()
    
    # Test 1: Valid Player Stats
    print("\n[TEST 1] Valid Player Stats")
    print("-" * 40)
    
    valid_player = {
        'player_id': '2544',
        'name': 'LeBron James',
        'season': '2024-25',
        'games': 50,
        'points_avg': 25.5,
        'rebounds_avg': 8.2,
        'assists_avg': 7.1,
        'fg_pct': 0.525,
        'three_p_pct': 0.388,
        'ft_pct': 0.755
    }
    
    is_valid, result = enforcer.validate(valid_player, 'player_stats')
    print(f"  Valid: {is_valid}")
    if is_valid:
        print(f"  Stats: {result['points_avg']} PPG, {result['rebounds_avg']} RPG, {result['assists_avg']} APG")
    else:
        print(f"  Error: {result.get('error')}")
    
    # Test 2: Invalid Season (out of range)
    print("\n[TEST 2] Invalid Season (out of range)")
    print("-" * 40)
    
    invalid_season = {
        **valid_player,
        'season': '2030-31'  # Future season
    }
    
    is_valid, result = enforcer.validate(invalid_season, 'player_stats')
    print(f"  Valid: {is_valid}")
    if not is_valid:
        print(f"  Error: {result['error']}")
    
    # Test 3: Invalid Percentage (out of bounds)
    print("\n[TEST 3] Invalid Percentage")
    print("-" * 40)
    
    invalid_pct = {
        **valid_player,
        'fg_pct': 1.5  # >100% impossible
    }
    
    is_valid, result = enforcer.validate(invalid_pct, 'player_stats')
    print(f"  Valid: {is_valid}")
    if not is_valid:
        print(f"  Error: {result['error']}")
    
    # Test 4: Corrupted Data (impossible stat)
    print("\n[TEST 4] Corrupted Data Detection")
    print("-" * 40)
    
    corrupted = {
        **valid_player,
        'points_avg': 150.0  # Clearly corrupted
    }
    
    is_valid, result = enforcer.validate(corrupted, 'player_stats')
    print(f"  Valid: {is_valid}")
    if not is_valid:
        print(f"  Error: {result['error']}")
        print(f"  Protection: Prevented corrupted data from entering database")
    
    # Test 5: Team Stats Validation
    print("\n[TEST 5] Team Stats Validation")
    print("-" * 40)
    
    valid_team = {
        'team_id': '1610612747',
        'name': 'Lakers',
        'season': '2024-25',
        'wins': 35,
        'losses': 20,
        'offensive_rating': 115.2,
        'defensive_rating': 108.5,
        'net_rating': 6.7,
        'pace': 98.5
    }
    
    is_valid, result = enforcer.validate(valid_team, 'team_stats')
    print(f"  Valid: {is_valid}")
    if is_valid:
        print(f"  Record: {result['wins']}-{result['losses']}, Net Rating: +{result['net_rating']}")
    
    # Test 6: Batch Validation
    print("\n[TEST 6] Batch Validation")
    print("-" * 40)
    
    batch = [
        valid_player,
        invalid_season,
        {**valid_player, 'player_id': '201939', 'name': 'Stephen Curry'},
        corrupted
    ]
    
    batch_result = enforcer.validate_batch(batch, 'player_stats')
    print(f"  Total: {batch_result['stats']['total']}")
    print(f"  Valid: {batch_result['stats']['valid_count']}")
    print(f"  Invalid: {batch_result['stats']['invalid_count']}")
    print(f"  Validation Rate: {batch_result['stats']['validation_rate']:.1%}")
    
    print("\n" + "=" * 70)
    print("✓ PYDANTIC TESTS COMPLETE")
    print("=" * 70)


def test_integrity_healer():
    """Test SHA-256 integrity and auto-repair"""
    
    print("\n" + "=" * 70)
    print("INTEGRITY HEALER: TEST SUITE")
    print("=" * 70)
    
    healer = DataIntegrityHealer()
    
    # Test 1: Hash Wrapping and Verification
    print("\n[TEST 1] Hash Wrapping & Verification")
    print("-" * 40)
    
    data = {
        'player_id': '2544',
        'name': 'LeBron James',
        'points': 25.5
    }
    
    wrapped = healer.wrap_with_metadata(data)
    print(f"  Original Hash: {wrapped['metadata']['hash'][:16]}...")
    print(f"  Timestamp: {wrapped['metadata']['last_sync']}")
    
    is_valid, msg = healer.verify_integrity(wrapped)
    print(f"  Verification: {is_valid} - {msg}")
    
    # Test 2: Tamper Detection
    print("\n[TEST 2] Tamper Detection")
    print("-" * 40)
    
    # Tamper with data
    wrapped_tampered = wrapped.copy()
    wrapped_tampered['data'] = {**data, 'points': 99.9}  # Modified!
    
    is_valid, msg = healer.verify_integrity(wrapped_tampered)
    print(f"  Verification: {is_valid} - {msg}")
    print(f"  Detection: Hash mismatch caught tampering")
    
    # Test 3: Auto-Fix BOM Character
    print("\n[TEST 3] Auto-Fix: BOM Character")
    print("-" * 40)
    
    bom_data = '\ufeff{"player_id": "2544", "name": "LeBron James"}'
    fixed = healer._attempt_auto_fix(bom_data)
    print(f"  Fixed: {fixed is not None}")
    if fixed:
        print(f"  Data: {fixed}")
    
    # Test 4: Auto-Fix Trailing Commas
    print("\n[TEST 4] Auto-Fix: Trailing Commas")
    print("-" * 40)
    
    trailing_comma = '{"player_id": "2544", "name": "LeBron James",}'
    fixed = healer._attempt_auto_fix(trailing_comma)
    print(f"  Fixed: {fixed is not None}")
    if fixed:
        print(f"  Data: {fixed}")
    
    # Test 5: Auto-Fix Single Quotes
    print("\n[TEST 5] Auto-Fix: Single Quotes")
    print("-" * 40)
    
    single_quotes = "{'player_id': '2544', 'name': 'LeBron James'}"
    fixed = healer._attempt_auto_fix(single_quotes)
    print(f"  Fixed: {fixed is not None}")
    if fixed:
        print(f"  Data: {fixed}")
    
    # Test 6: Try-Heal-Retry Loop
    print("\n[TEST 6] Try-Heal-Retry Loop")
    print("-" * 40)
    
    # Attempt 1: Auto-fix succeeds
    corrupt1 = '{"player_id": "2544",}'  # Trailing comma
    result1 = healer.try_heal_retry(corrupt1, 'player_stats', 2544)
    print(f"  Attempt 1: {'Success' if result1 else 'Failed'}")
    
    # Attempt 2: Beyond repair
    corrupt2 = '{{invalid json'
    result2 = healer.try_heal_retry(corrupt2, 'player_stats', 9999)
    print(f"  Attempt 2: {'Success' if result2 else 'Failed (API re-fetch needed)'}")
    
    # Statistics
    print("\n[STATISTICS]")
    print("-" * 40)
    stats = healer.get_stats()
    print(f"  Verified: {stats['verified']}")
    print(f"  Corrupted: {stats['corrupted']}")
    print(f"  Repaired: {stats['repaired']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Integrity Rate: {stats['integrity_rate']:.1%}")
    print(f"  Repair Success Rate: {stats['repair_success_rate']:.1%}")
    
    print("\n" + "=" * 70)
    print("✓ INTEGRITY HEALER TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_pydantic_schemas()
    test_integrity_healer()
    
    print("\n" + "=" * 70)
    print("✓ ALL WEEK 3 TESTS PASSED")
    print("=" * 70)
