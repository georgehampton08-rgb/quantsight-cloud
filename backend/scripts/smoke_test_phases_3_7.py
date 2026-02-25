"""
Local smoke test for Phases 3-7 changes.
Run from: backend/ directory
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

errors = []

# Test 1: baseline_populator import fix
try:
    from services.baseline_populator import fetch_player_season_stats, fetch_team_season_stats
    print('✅ baseline_populator: fetch_player_season_stats + fetch_team_season_stats OK')
except ImportError as e:
    errors.append(f'baseline_populator: {e}')
    print(f'❌ baseline_populator: {e}')

# Test 2: nba_hardened_client
try:
    from services.nba_hardened_client import HardenedNBAClient, get_nba_client, CircuitOpenError
    c = HardenedNBAClient(timeout=5)
    status = c.get_circuit_status()
    assert status['circuit_open'] == False, "Circuit should start closed"
    print('✅ nba_hardened_client: HardenedNBAClient + circuit breaker OK')
except Exception as e:
    errors.append(f'nba_hardened_client: {e}')
    print(f'❌ nba_hardened_client: {e}')

# Test 3: vaccine defensive imports
try:
    from vanguard.vaccine import VaccineGenerator, get_vaccine
    print('✅ vanguard.vaccine: import OK')
except Exception as e:
    errors.append(f'vanguard.vaccine: {e}')
    print(f'❌ vanguard.vaccine: {e}')

# Test 4: sim_adapter normalizer (no Firestore needed)
try:
    from aegis.sim_adapter import FirestoreSimAdapter
    result = FirestoreSimAdapter._normalize_player_stats({'pts': 25.0, 'reb': 7.0, 'ast': 6.0})
    assert result['pts_ema'] == 25.0, f"Expected 25.0 got {result['pts_ema']}"
    assert result['reb_ema'] == 7.0
    print('✅ aegis.sim_adapter: FirestoreSimAdapter + normalizer OK')
except Exception as e:
    errors.append(f'aegis.sim_adapter: {e}')
    print(f'❌ aegis.sim_adapter: {e}')

# Test 5: schema v1 migration
try:
    from vanguard.core.incident_schema_v1 import migrate_incident_v0_to_v1, stamp_new_incident_v1
    v0 = {
        'fingerprint': 'abc',
        'timestamp': '2026-01-01T00:00:00Z',
        'severity': 'RED',
        'status': 'active',
        'error_type': 'ValueError',
        'error_message': 'test',
        'endpoint': '/test',
        'request_id': 'r1',
        'context_vector': {},
        'remediation_log': []
    }
    v1 = migrate_incident_v0_to_v1(v0)
    assert v1.get('schema_version') == 'v1', f"Expected v1 got {v1.get('schema_version')}"
    assert 'labels' in v1
    assert 'resolution' in v1
    print('✅ incident_schema_v1: v0->v1 migration OK')
except Exception as e:
    errors.append(f'incident_schema_v1: {e}')
    print(f'❌ incident_schema_v1: {e}')

# Test 6: types have AMBER + v1 fields
try:
    from vanguard.core.types import Severity, Incident
    assert hasattr(Severity, 'AMBER'), "AMBER severity missing"
    hints = Incident.__annotations__
    for field in ['schema_version', 'labels', 'resolution', 'remediation', 'ai_analysis']:
        assert field in hints, f"Missing field: {field}"
    print('✅ types: AMBER severity + v1 fields OK')
except Exception as e:
    errors.append(f'types: {e}')
    print(f'❌ types: {e}')

print()
if errors:
    print(f'❌ {len(errors)} FAILURE(S):')
    for err in errors:
        print(f'   • {err}')
    sys.exit(1)
else:
    print('=== ALL LOCAL PHASE 3-7 TESTS PASSED ===')
