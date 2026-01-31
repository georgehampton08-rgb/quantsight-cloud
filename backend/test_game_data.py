from services.nba_schedule import get_schedule_service
import json

schedule = get_schedule_service()
games = schedule.get_todays_games()

print("First game data:")
if games:
    print(json.dumps(games[0], indent=2))
