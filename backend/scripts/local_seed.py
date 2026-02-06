"""
Seed Schedule and Players via Admin API
Fetches from NBA API locally (works) and posts to Cloud Run
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

# NBA API headers
NBA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Accept-Language': 'en-US,en;q=0.9'
}

def fetch_players():
    """Fetch all active NBA players from NBA API"""
    print("Fetching players from NBA API...")
    
    url = "https://stats.nba.com/stats/commonallplayers"
    params = {
        'LeagueID': '00',
        'Season': '2024-25',
        'IsOnlyCurrentSeason': '1'
    }
    
    try:
        response = requests.get(url, headers=NBA_HEADERS, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        players_data = data['resultSets'][0]
        headers = players_data['headers']
        rows = players_data['rowSet']
        
        print(f"Got {len(rows)} players from NBA API")
        return [(
            row[headers.index('PERSON_ID')],
            row[headers.index('DISPLAY_FIRST_LAST')],
            row[headers.index('TEAM_ID')],
            row[headers.index('TEAM_ABBREVIATION')]
        ) for row in rows if row[headers.index('TEAM_ID')]]
    except Exception as e:
        print(f"Error fetching players: {e}")
        return []

def fetch_schedule():
    """Fetch NBA schedule for today and upcoming games"""
    print("Fetching schedule from NBA API...")
    
    # Get today's date
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Use scoreboard endpoint for today's games
    url = f"https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    
    try:
        response = requests.get(url, headers=NBA_HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        games = data.get('scoreboard', {}).get('games', [])
        print(f"Got {len(games)} games from schedule")
        
        schedule = []
        for game in games:
            schedule.append({
                'game_id': game.get('gameId'),
                'game_date': game.get('gameTimeUTC', '')[:10],
                'home_team': game.get('homeTeam', {}).get('teamTricode'),
                'away_team': game.get('awayTeam', {}).get('teamTricode'),
                'home_score': game.get('homeTeam', {}).get('score', 0),
                'away_score': game.get('awayTeam', {}).get('score', 0),
                'status': game.get('gameStatus', 1),  # 1=upcoming, 2=live, 3=final
                'status_text': game.get('gameStatusText', 'Scheduled')
            })
        
        return schedule
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return []

def seed_players_via_api(players):
    """Upload players to Cloud SQL via admin endpoint"""
    print(f"\nSeeding {len(players)} players to Cloud SQL...")
    
    # Create a bulk insert endpoint call
    url = f"{BASE_URL}/admin/bulk-seed-players"
    
    player_data = [{
        'player_id': p[0],
        'full_name': p[1],
        'team_id': p[2],
        'team_abbreviation': p[3] or 'FA'
    } for p in players]
    
    try:
        response = requests.post(url, json={'players': player_data}, timeout=120)
        print(f"Response: {response.status_code}")
        if response.status_code == 200:
            print(f"SUCCESS: {response.json()}")
        else:
            print(f"Error: {response.text[:200]}")
    except Exception as e:
        print(f"Error seeding players: {e}")

def main():
    print("="*60)
    print(" NBA DATA SEEDER (Local to Cloud)")
    print("="*60)
    
    # Fetch schedule
    schedule = fetch_schedule()
    if schedule:
        print(f"\nToday's Games ({len(schedule)}):")
        for game in schedule:
            status = "FINAL" if game['status'] == 3 else "UPCOMING" if game['status'] == 1 else "LIVE"
            print(f"  {game['away_team']} @ {game['home_team']} - {status} ({game['status_text']})")
    
    # Fetch players
    players = fetch_players()
    if players:
        print(f"\nFetched {len(players)} active players")
        print(f"Sample: {players[0]}")
    
    print("\n" + "="*60)
    print(" SUMMARY")
    print("="*60)
    print(f"Schedule games: {len(schedule)}")
    print(f"Players: {len(players)}")
    
if __name__ == "__main__":
    main()
