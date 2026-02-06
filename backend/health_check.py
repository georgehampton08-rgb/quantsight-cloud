import requests

print("=" * 60)
print("QUANTSIGHT HEALTH CHECK")
print("=" * 60)

tests = {
    'Backend Health': 'http://localhost:5000/aegis/health',
    'Frontend': 'http://localhost:5173',
    'Schedule': 'http://localhost:5000/schedule',
    'Players Search': 'http://localhost:5000/players/search?q=',
    'Simulations': 'http://localhost:5000/aegis/simulate/1628389?opponent_id=1610612741',
    'Matchup Lab': 'http://localhost:5000/matchup-lab/games',
    'Injuries': 'http://localhost:5000/injuries/current',
}

passed = 0
failed = 0

for name, url in tests.items():
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            status = "✅"
            passed += 1
        else:
            status = f"❌ {r.status_code}"
            failed += 1
        print(f"{status} {name}")
    except Exception as e:
        print(f"❌ {name} - {str(e)[:50]}")
        failed += 1

print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if passed == len(tests):
    print("🎉 All systems operational!")
else:
    print(f"⚠️  {failed} issue(s) found")
print("=" * 60)
