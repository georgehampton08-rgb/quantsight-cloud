"""
Comprehensive Box Score Endpoint Test Suite
- ASCII-only output (no emoji) for Windows cp1252 compatibility
- Always run as: python comprehensive_boxscore_test.py
"""
import sys
import re
sys.path.insert(0, '.')
from services.firebase_admin_service import FirebaseAdminService

svc = FirebaseAdminService()
passed = 0
total = 0

def test(name, ok, detail=''):
    global passed, total
    total += 1
    if ok:
        passed += 1
    mark = 'PASS' if ok else 'FAIL'
    suffix = f' -> {detail}' if detail else ''
    print(f'  [{mark}]  {name}{suffix}')

def section(title):
    print(f'\n{"="*60}')
    print(f'  {title}')
    print('='*60)

# ── 1. get_game_dates() ──────────────────────────────────────
section('1. get_game_dates() -- pulse_stats source')
dates = svc.get_game_dates()
test('Returns list', isinstance(dates, list))
test('Has >=1 date', len(dates) >= 1, f'count={len(dates)}')
test('Sorted descending', dates == sorted(dates, reverse=True))
test('All YYYY-MM-DD format', all(re.match(r'^20\d{2}-(0[1-9]|1[0-2])-\d{2}$', d) for d in dates), str(dates))
test('No game-week IDs (0022-*)', all('0022' not in d for d in dates))
print(f'  Dates returned: {dates}')

# ── 2. get_box_scores_for_date() with FINAL data (2026-02-28) ─
section('2. get_box_scores_for_date(2026-02-28) -- expects FINAL')
games28 = svc.get_box_scores_for_date('2026-02-28')
test('Returns list', isinstance(games28, list))
test('Has >=1 game', len(games28) >= 1, f'count={len(games28)}')
for g in games28:
    matchup = g.get('matchup', '?')
    test(f'{matchup} has score', g.get('home_score', 0) > 0 or g.get('away_score', 0) > 0)
    test(f'{matchup} status=FINAL', g.get('status') == 'FINAL', g.get('status'))
    test(f'{matchup} winner present', bool(g.get('winner')))
    test(f'{matchup} has_final=True', g.get('has_final') is True)
    print(f'    {matchup:22s} {g.get("away_score")}-{g.get("home_score")} | {g.get("status")} | winner={g.get("winner")}')

# ── 3. get_box_scores_for_date() with partial data (2026-02-27) ─
section('3. get_box_scores_for_date(2026-02-27) -- expects fallback (no FINAL)')
games27 = svc.get_box_scores_for_date('2026-02-27')
test('Returns list', isinstance(games27, list))
test('Has >=1 game', len(games27) >= 1, f'count={len(games27)}')
for g in games27:
    matchup = g.get('matchup', '?')
    test(f'{matchup} has score (fallback)', g.get('home_score', 0) > 0 or g.get('away_score', 0) > 0)
    test(f'{matchup} has_final=False (pre-Feb28)', g.get('has_final') is False, str(g.get('has_final')))
    print(f'    {matchup:22s} {g.get("away_score")}-{g.get("home_score")} | {g.get("status")} | has_final={g.get("has_final")}')

# ── 4. Player stats from FINAL quarter ──────────────────────
section('4. Player stats in pulse_stats/2026-02-28/FINAL quarter')
if games28:
    gid   = games28[0]['game_id']
    home  = games28[0]['home_team']
    away  = games28[0]['away_team']
    print(f'  Game: {gid} ({games28[0]["matchup"]})')
    qs = {
        q.id: q.to_dict() or {}
        for q in svc.db.collection('pulse_stats').document('2026-02-28')
                        .collection('games').document(gid)
                        .collection('quarters').stream()
    }
    test('FINAL quarter exists', 'FINAL' in qs, f'found quarters: {sorted(qs.keys())}')
    if 'FINAL' in qs:
        q = qs['FINAL']
        players = q.get('players', {})
        test('players dict non-empty', len(players) > 0, f'count={len(players)}')
        home_ct = sum(1 for p in players.values() if isinstance(p, dict) and p.get('team') == home)
        away_ct = sum(1 for p in players.values() if isinstance(p, dict) and p.get('team') == away)
        test(f'home ({home}) >= 5 players', home_ct >= 5, f'count={home_ct}')
        test(f'away ({away}) >= 5 players', away_ct >= 5, f'count={away_ct}')
        sample = next((p for p in players.values() if isinstance(p, dict)), {})
        for field in ['pts', 'reb', 'ast', 'stl', 'blk', 'name', 'team', 'ts_pct', 'plus_minus']:
            test(f'player has field [{field}]', field in sample)
        # Top scorers
        top = sorted(
            [(pid, p) for pid, p in players.items() if isinstance(p, dict)],
            key=lambda x: x[1].get('pts', 0), reverse=True
        )[:3]
        print(f'  Top scorers:')
        for pid, p in top:
            name = p.get('name', '?')
            team = p.get('team', '?')
            ts   = p.get('ts_pct', 0)
            print(f'    {name:24s} {team:4s}  {p.get("pts",0):2}pts {p.get("reb",0):2}reb '
                  f'{p.get("ast",0):2}ast  TS%={ts:.1%}  +/-={p.get("plus_minus",0)}')

# ── 5. Edge cases ────────────────────────────────────────────
section('5. Edge Cases')
test('Empty for no-data date', svc.get_box_scores_for_date('2020-01-01') == [])
test('Today date returns list', isinstance(svc.get_box_scores_for_date('2026-03-02'), list))
test('get_game_dates always returns list', isinstance(svc.get_game_dates(), list))

# ── 6. New endpoint route correctness check  ─────────────────
section('6. API route sanity: game_logs_routes.py has /api/box-scores/players')
try:
    import ast, pathlib
    src = pathlib.Path('api/game_logs_routes.py').read_text()
    test('/api/box-scores/players route defined', '/api/box-scores/players' in src)
    test('quarter_used in response', 'quarter_used' in src)
    test('home_players in response', 'home_players' in src)
    test('away_players in response', 'away_players' in src)
except Exception as e:
    test('route file readable', False, str(e))

# ── Summary ──────────────────────────────────────────────────
section(f'SUMMARY: {passed}/{total} passed ({100*passed//total if total else 0}%)')
if passed == total:
    print('  ALL TESTS PASSED!')
else:
    print('  SOME FAILURES - see above')
    for _n, ok, detail in [
        (n, ok, detail) for n, ok, detail in
        zip(
            [t[0] for t in [(name, o, d) for name, o, d in [(name, ok, detail)
             for name, ok, detail in [(name, ok, detail) for name, ok, detail in []]]]]
        , [], [])
    ]:
        pass

# Simple failure report
if passed < total:
    print('\n  Failed tests:')
