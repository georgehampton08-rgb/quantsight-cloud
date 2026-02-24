from nba_api.live.nba.endpoints import scoreboard
import json

try:
    sb = scoreboard.ScoreBoard()
    data = sb.games.get_dict()
    print(f"NBA API: OK - {len(data)} games today")
    if data:
        g = data[0]
        print(f"  First game: {g.get('awayTeam',{}).get('teamTricode','?')} @ {g.get('homeTeam',{}).get('teamTricode','?')} - Status: {g.get('gameStatus','?')}")
except Exception as e:
    print(f"NBA API ERROR: {e}")
