"""
Incremental Game Log Fetcher
=============================
Only fetches game logs for players who DON'T already have data.
Preserves existing data and fills gaps.
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

# NBA API Settings
BASE_URL = "https://stats.nba.com/stats"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept-Language": "en-US,en;q=0.9"
}


def get_players_with_logs(db_path: str) -> Set[str]:
    """Get set of player IDs that already have game logs"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    players = set()
    
    # Old game_logs table was merged into player_game_logs
    # Only check player_game_logs now
    
    # Check player_game_logs table
    try:
        cursor.execute("SELECT DISTINCT player_id FROM player_game_logs")
        for row in cursor.fetchall():
            players.add(str(row[0]))
    except:
        pass
    
    conn.close()
    return players


def get_all_active_players(db_path: str) -> List[Dict]:
    """Get all active players from database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_id, name 
        FROM players 
        WHERE team_id IS NOT NULL
        ORDER BY name
    """)
    
    players = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return players


def fetch_player_game_log(player_id: str, player_name: str, season: str = CURRENT_SEASON) -> List[Dict]:
    """Fetch last 15 games for a player from NBA API"""
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
                for row in rows[:15]:  # Last 15 games
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
                        'min': game_dict.get('MIN', 0),
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
            print(f"  ⚠️  Rate limited, waiting 60s...")
            time.sleep(60)
            return []
        else:
            print(f"  ⚠️  API returned {response.status_code}")
            return []
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []
    
    return []


def save_games_to_db(db_path: str, games: List[Dict]):
    """Save games to database"""
    if not games:
        return
    
    conn = sqlite3.connect(db_path)
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


def fetch_missing_players(max_players: int = None):
    """Fetch game logs for players who don't have them yet"""
    db_path = Path(__file__).parent / 'data' / 'nba_data.db'
    
    print("=" * 60)
    print("INCREMENTAL GAME LOG FETCHER")
    print("=" * 60)
    
    # Get players who already have data
    players_with_logs = get_players_with_logs(str(db_path))
    print(f"\n✅ Players already have logs: {len(players_with_logs)}")
    
    # Get all active players
    all_players = get_all_active_players(str(db_path))
    print(f"📊 Total active players: {len(all_players)}")
    
    # Find missing players
    missing_players = [p for p in all_players if str(p['player_id']) not in players_with_logs]
    print(f"🔍 Players missing logs: {len(missing_players)}")
    
    if not missing_players:
        print("\n✅ All players already have game logs!")
        return
    
    if max_players:
        missing_players = missing_players[:max_players]
        print(f"   (Limiting to first {max_players})")
    
    print("\n" + "-" * 60)
    print("Starting fetch...")
    print("-" * 60)
    
    success_count = 0
    fail_count = 0
    
    for i, player in enumerate(missing_players):
        player_id = str(player['player_id'])
        player_name = player['name']
        
        print(f"\n[{i+1}/{len(missing_players)}] {player_name} ({player_id})")
        
        # Wait to avoid rate limiting
        wait_time = random.uniform(1.5, 3.0)
        time.sleep(wait_time)
        
        games = fetch_player_game_log(player_id, player_name)
        
        if games:
            save_games_to_db(str(db_path), games)
            print(f"  ✅ Saved {len(games)} games")
            success_count += 1
        else:
            print(f"  ⚠️  No games found")
            fail_count += 1
    
    print("\n" + "=" * 60)
    print(f"COMPLETE: {success_count} players updated, {fail_count} failed")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--max', type=int, default=None, help='Max players to fetch')
    args = parser.parse_args()
    
    fetch_missing_players(max_players=args.max)
