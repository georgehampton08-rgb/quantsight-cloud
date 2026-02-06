"""
Fetch game logs for players playing TODAY only.
Only fetches for players who DON'T already have data in the database.
"""
import sqlite3
import requests
import time
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core.config import CURRENT_SEASON

DB_PATH = Path(__file__).parent / 'data' / 'nba_data.db'

# NBA API Settings
BASE_URL = "https://stats.nba.com/stats"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept-Language": "en-US,en;q=0.9"
}


def get_players_with_logs() -> Set[str]:
    """Get set of player IDs that already have game logs"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    players = set()
    
    # Check game_logs table
    try:
        cursor.execute("SELECT DISTINCT player_id FROM player_game_logs")
        for row in cursor.fetchall():
            players.add(str(row[0]))
    except:
        pass
    
    # Check player_game_logs table
    try:
        cursor.execute("SELECT DISTINCT player_id FROM player_game_logs")
        for row in cursor.fetchall():
            players.add(str(row[0]))
    except:
        pass
    
    conn.close()
    return players


def get_todays_games() -> List[Dict]:
    """Get today's games from NBA API"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Try NBA scoreboard API
    url = f"{BASE_URL}/scoreboardv2"
    params = {
        "DayOffset": 0,
        "GameDate": today,
        "LeagueID": "00"
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            result_sets = data.get('resultSets', [])
            
            # Find GameHeader result set
            for rs in result_sets:
                if rs.get('name') == 'GameHeader':
                    headers = rs.get('headers', [])
                    rows = rs.get('rowSet', [])
                    
                    games = []
                    for row in rows:
                        game_dict = dict(zip(headers, row))
                        games.append({
                            'game_id': game_dict.get('GAME_ID'),
                            'home_team_id': str(game_dict.get('HOME_TEAM_ID')),
                            'away_team_id': str(game_dict.get('VISITOR_TEAM_ID')),
                        })
                    return games
        else:
            print(f"API returned {response.status_code}")
    except Exception as e:
        print(f"Error fetching schedule: {e}")
    
    return []


def get_team_roster(team_id: str) -> List[Dict]:
    """Get roster for a team"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_id, name 
        FROM players 
        WHERE team_id = ?
    """, (team_id,))
    
    players = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return players


def fetch_player_game_log(player_id: str, player_name: str, season: str = CURRENT_SEASON) -> List[Dict]:
    """Fetch last 15 games for a player"""
    url = f"{BASE_URL}/playergamelog"
    params = {
        "PlayerID": player_id,
        "Season": season,
        "SeasonType": "Regular Season",
        "LeagueID": "00"
    }
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            result_sets = data.get('resultSets', [])
            
            if result_sets:
                headers = result_sets[0].get('headers', [])
                rows = result_sets[0].get('rowSet', [])
                
                games = []
                for row in rows[:15]:
                    game_dict = dict(zip(headers, row))
                    games.append({
                        'player_id': player_id,
                        'player_name': player_name,
                        'game_id': game_dict.get('Game_ID', ''),
                        'game_date': game_dict.get('GAME_DATE', ''),
                        'opponent': game_dict.get('MATCHUP', '').split(' ')[-1] if game_dict.get('MATCHUP') else '',
                        'home_away': 'home' if 'vs.' in game_dict.get('MATCHUP', '') else 'away',
                        'pts': game_dict.get('PTS', 0),
                        'reb': game_dict.get('REB', 0),
                        'ast': game_dict.get('AST', 0),
                        'stl': game_dict.get('STL', 0),
                        'blk': game_dict.get('BLK', 0),
                        'tov': game_dict.get('TOV', 0),
                        'fgm': game_dict.get('FGM', 0),
                        'fga': game_dict.get('FGA', 0),
                        'fg3m': game_dict.get('FG3M', 0),
                        'fg3a': game_dict.get('FG3A', 0),
                        'ftm': game_dict.get('FTM', 0),
                        'fta': game_dict.get('FTA', 0),
                        'plus_minus': game_dict.get('PLUS_MINUS', 0),
                    })
                return games
        elif response.status_code == 429:
            print(f"  ⚠️ Rate limited, waiting 60s...")
            time.sleep(60)
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    return []


def save_games_to_db(games: List[Dict]):
    """Save games to database"""
    if not games:
        return
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_game_logs (
            player_id TEXT,
            game_id TEXT,
            game_date TEXT,
            opponent TEXT,
            home_away TEXT,
            result TEXT,
            pts REAL,
            reb REAL,
            ast REAL,
            stl REAL,
            blk REAL,
            tov REAL,
            fgm REAL,
            fga REAL,
            fg3m REAL,
            fg3a REAL,
            ftm REAL,
            fta REAL,
            plus_minus REAL,
            sync_timestamp TEXT,
            PRIMARY KEY (player_id, game_id)
        )
    """)
    
    now = datetime.now().isoformat()
    
    for game in games:
        cursor.execute("""
            INSERT OR REPLACE INTO player_game_logs 
            (player_id, game_id, game_date, opponent, home_away, pts, reb, ast, 
             stl, blk, tov, fgm, fga, fg3m, fg3a, ftm, fta, plus_minus, sync_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game['player_id'], game['game_id'], game['game_date'], 
            game['opponent'], game['home_away'],
            game['pts'], game['reb'], game['ast'],
            game['stl'], game['blk'], game['tov'],
            game['fgm'], game['fga'], game['fg3m'], game['fg3a'],
            game['ftm'], game['fta'], game['plus_minus'], now
        ))
    
    conn.commit()
    conn.close()


def main():
    print("=" * 60)
    print("FETCH GAME LOGS FOR TODAY'S PLAYERS")
    print("=" * 60)
    
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n📅 Date: {today}")
    
    # Get players who already have data
    players_with_logs = get_players_with_logs()
    print(f"✅ Players already have logs: {len(players_with_logs)}")
    
    # Get today's games
    print("\n🏀 Fetching today's schedule...")
    games = get_todays_games()
    
    if not games:
        print("⚠️ No games found for today (or API unavailable)")
        print("\nFalling back to all active players without logs...")
        
        # Fallback: get all players without logs
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT player_id, name FROM players WHERE team_id IS NOT NULL")
        all_players = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        missing_players = [p for p in all_players if str(p['player_id']) not in players_with_logs]
        print(f"🔍 Players missing logs: {len(missing_players)}")
        
        # Limit to first 20 for quick test
        missing_players = missing_players[:20]
        print(f"   (Limiting to first 20 for quick test)")
    else:
        print(f"   Found {len(games)} games today")
        
        # Get all team IDs
        team_ids = set()
        for game in games:
            team_ids.add(game['home_team_id'])
            team_ids.add(game['away_team_id'])
        
        # Get rosters for all teams playing today
        missing_players = []
        for team_id in team_ids:
            roster = get_team_roster(team_id)
            for player in roster:
                if str(player['player_id']) not in players_with_logs:
                    missing_players.append(player)
        
        print(f"🔍 Players in today's games missing logs: {len(missing_players)}")
    
    if not missing_players:
        print("\n✅ All players already have game logs!")
        return
    
    print("\n" + "-" * 60)
    print("Starting fetch...")
    print("-" * 60)
    
    success_count = 0
    for i, player in enumerate(missing_players):
        player_id = str(player['player_id'])
        player_name = player['name']
        
        print(f"\n[{i+1}/{len(missing_players)}] {player_name} ({player_id})")
        
        # Wait to avoid rate limiting
        time.sleep(random.uniform(1.5, 2.5))
        
        games = fetch_player_game_log(player_id, player_name)
        
        if games:
            save_games_to_db(games)
            print(f"  ✅ Saved {len(games)} games")
            success_count += 1
        else:
            print(f"  ⚠️ No games found")
    
    print("\n" + "=" * 60)
    print(f"COMPLETE: {success_count}/{len(missing_players)} players updated")
    print("=" * 60)


if __name__ == "__main__":
    main()
