import urllib.request, json
with urllib.request.urlopen('https://quantsight-cloud-nucvdwqo6q-uc.a.run.app/v1/games/dates/2026-03-11') as url:
    data = json.loads(url.read().decode())
    print('COUNT:', data.get('count'))
    for g in data.get('games', []):
        print(f"{g['gameId']} ({g['nbaId']}) - {g['awayTeam']}@{g['homeTeam']} - pbp:{g['hasPbp']}")
