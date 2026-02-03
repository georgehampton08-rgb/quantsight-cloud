"""
Sync Recent Game Log Box Scores to Cloud SQL
Fetches today's completed games and box scores from NBA API
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"
NBA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com'
}

def get_todays_games():
    """Get today's NBA games from scoreboard"""
    print("Fetching today's games...")
    
    url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
    
    try:
        r = requests.get(url, headers=NBA_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        games = data.get('scoreboard', {}).get('games', [])
        print(f"Found {len(games)} games today")
        
        return games
    except Exception as e:
        print(f"Error fetching games: {e}")
        return []

def get_box_score(game_id):
    """Get detailed box score for a game"""
    print(f"  Fetching box score for game {game_id}...")
    
    # NBA box score endpoint
    url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
    
    try:
        r = requests.get(url, headers=NBA_HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    Error: {e}")
        return None

def format_player_stats(game_id, team_data, is_home):
    """Format player stats from box score"""
    players = []
    
    for player in team_data.get('players', []):
        stats = player.get('statistics', {})
        
        players.append({
            'game_id': game_id,
            'player_id': player.get('personId'),
            'player_name': player.get('name', ''),
            'team_tricode': team_data.get('teamTricode'),
            'is_home': is_home,
            'minutes': stats.get('minutes', ''),
            'points': stats.get('points', 0),
            'rebounds': stats.get('reboundsTotal', 0),
            'assists': stats.get('assists', 0),
            'steals': stats.get('steals', 0),
            'blocks': stats.get('blocks', 0),
            'turnovers': stats.get('turnovers', 0),
            'fgm': stats.get('fieldGoalsMade', 0),
            'fga': stats.get('fieldGoalsAttempted', 0),
            'fg_pct': stats.get('fieldGoalsPercentage', 0),
            'tpm': stats.get('threePointersMade', 0),
            'tpa': stats.get('threePointersAttempted', 0),
            'tp_pct': stats.get('threePointersPercentage', 0),
            'ftm': stats.get('freeThrowsMade', 0),
            'fta': stats.get('freeThrowsAttempted', 0),
            'ft_pct': stats.get('freeThrowsPercentage', 0),
            'plus_minus': stats.get('plusMinusPoints', 0)
        })
    
    return players

def upload_game_logs(game_logs):
    """Upload game logs via admin endpoint"""
    print(f"\nUploading {len(game_logs)} game logs to Cloud SQL...")
    
    url = f"{BASE_URL}/admin/bulk-seed-game-logs"
    
    try:
        r = requests.post(url, json={'game_logs': game_logs}, timeout=60)
        
        if r.status_code == 200:
            result = r.json()
            print(f"  SUCCESS: {result.get('message')}")
            return True
        else:
            print(f"  ERROR: {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def main():
    print("=" * 60)
    print(" NBA GAME LOG BOX SCORE SYNC")
    print(" " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # Get today's games
    games = get_todays_games()
    
    all_player_stats = []
    completed_games = 0
    
    for game in games:
        game_id = game.get('gameId')
        status = game.get('gameStatus')
        away_team = game.get('awayTeam', {}).get('teamTricode')
        home_team = game.get('homeTeam', {}).get('teamTricode')
        
        print(f"\n{away_team} @ {home_team} (Status: {status})")
        
        # Only fetch box scores for completed games (status = 3)
        if status == 3:
            box_score = get_box_score(game_id)
            
            if box_score:
                game_data = box_score.get('game', {})
                
                # Get home team stats
                home_data = game_data.get('homeTeam', {})
                home_players = format_player_stats(game_id, home_data, True)
                all_player_stats.extend(home_players)
                
                # Get away team stats
                away_data = game_data.get('awayTeam', {})
                away_players = format_player_stats(game_id, away_data, False)
                all_player_stats.extend(away_players)
                
                completed_games += 1
                print(f"  ✓ Got {len(home_players) + len(away_players)} player stats")
        else:
            status_text = game.get('gameStatusText', 'Unknown')
            print(f"  ⏭ Skipped ({status_text})")
    
    print("\n" + "=" * 60)
    print(f" SUMMARY")
    print("=" * 60)
    print(f"Total games today: {len(games)}")
    print(f"Completed games: {completed_games}")
    print(f"Player stats collected: {len(all_player_stats)}")
    
    # Save to JSON for inspection
    with open('game_logs_export.json', 'w') as f:
        json.dump(all_player_stats, f, indent=2)
    print(f"\nExported to: game_logs_export.json")
    
    # Upload to Cloud SQL (if endpoint exists)
    if all_player_stats:
        print("\nNote: Upload endpoint /admin/bulk-seed-game-logs needs to be created")
        print("Game logs saved locally for now")
    else:
        print("\nNo completed games to upload yet")

if __name__ == "__main__":
    main()
