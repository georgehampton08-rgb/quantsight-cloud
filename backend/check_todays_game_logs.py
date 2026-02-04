"""
Game Log Checker & Fetcher for Today's Games
=============================================
1. Gets today's schedule
2. Gets all players from teams playing today
3. Checks if each player has game logs
4. Fetches missing game logs from NBA API
"""
import sqlite3
import requests
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_URL = "http://localhost:5000"
DB_PATH = Path(__file__).parent / "data" / "nba_data.db"

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def get_todays_schedule():
    """Get today's games from API"""
    print("\n1. FETCHING TODAY'S SCHEDULE")
    print("-" * 50)
    
    try:
        r = requests.get(f"{BASE_URL}/schedule", timeout=30)
        if r.status_code == 200:
            games = r.json()
            print(f"   Found {len(games)} games scheduled")
            return games
        else:
            print(f"   Error: {r.status_code}")
            return []
    except Exception as e:
        print(f"   Error: {e}")
        return []

def get_team_players(team_id: str) -> list:
    """Get all players for a team"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # NBA team ID mapping
    nba_team_map = {
        'ATL': '1610612737', 'BOS': '1610612738', 'BKN': '1610612751', 'CHA': '1610612766',
        'CHI': '1610612741', 'CLE': '1610612739', 'DAL': '1610612742', 'DEN': '1610612743',
        'DET': '1610612765', 'GSW': '1610612744', 'HOU': '1610612745', 'IND': '1610612754',
        'LAC': '1610612746', 'LAL': '1610612747', 'MEM': '1610612763', 'MIA': '1610612748',
        'MIL': '1610612749', 'MIN': '1610612750', 'NOP': '1610612740', 'NYK': '1610612752',
        'OKC': '1610612760', 'ORL': '1610612753', 'PHI': '1610612755', 'PHX': '1610612756',
        'POR': '1610612757', 'SAC': '1610612758', 'SAS': '1610612759', 'TOR': '1610612761',
        'UTA': '1610612762', 'WAS': '1610612764'
    }
    
    # Convert abbreviation to ID if needed
    target_ids = [team_id]
    if team_id in nba_team_map:
        target_ids.append(nba_team_map[team_id])
    for abbr, tid in nba_team_map.items():
        if tid == team_id:
            target_ids.append(abbr)
            break
    
    placeholders = ','.join(['?'] * len(target_ids))
    cursor.execute(f"""
        SELECT player_id, name, team_id 
        FROM players 
        WHERE team_id IN ({placeholders})
    """, tuple(target_ids))
    
    players = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return players

def check_player_game_logs(player_id: str) -> dict:
    """Check if player has game logs in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check player_rolling_averages
    cursor.execute("""
        SELECT player_id, avg_points, avg_rebounds, avg_assists, games_count
        FROM player_rolling_averages
        WHERE player_id = ?
    """, (str(player_id),))
    
    rolling = cursor.fetchone()
    
    # Check game_logs table
    cursor.execute("""
        SELECT COUNT(*) as count, MAX(game_date) as last_game
        FROM game_logs
        WHERE player_id = ?
    """, (str(player_id),))
    
    logs = cursor.fetchone()
    
    conn.close()
    
    return {
        "player_id": player_id,
        "has_rolling_avg": rolling is not None,
        "avg_points": rolling["avg_points"] if rolling else 0,
        "game_log_count": logs["count"] if logs else 0,
        "last_game": logs["last_game"] if logs else None
    }

def fetch_player_game_logs(player_id: str, player_name: str):
    """Fetch game logs from NBA API for a player"""
    from nba_api.stats.endpoints import playergamelog
    from nba_api.stats.static import players
    
    print(f"      Fetching game logs for {player_name} ({player_id})...")
    
    try:
        # Add delay to avoid rate limiting
        time.sleep(0.75)
        
        log = playergamelog.PlayerGameLog(
            player_id=player_id,
            season='2024-25',
            season_type_all_star='Regular Season'
        )
        
        df = log.get_data_frames()[0]
        
        if df.empty:
            print(f"         No games found")
            return 0
        
        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        inserted = 0
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO game_logs 
                    (player_id, game_id, game_date, matchup, wl, min, pts, reb, ast, stl, blk, tov, fg_pct, fg3_pct, ft_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(player_id),
                    row.get('Game_ID', ''),
                    row.get('GAME_DATE', ''),
                    row.get('MATCHUP', ''),
                    row.get('WL', ''),
                    row.get('MIN', 0),
                    row.get('PTS', 0),
                    row.get('REB', 0),
                    row.get('AST', 0),
                    row.get('STL', 0),
                    row.get('BLK', 0),
                    row.get('TOV', 0),
                    row.get('FG_PCT', 0),
                    row.get('FG3_PCT', 0),
                    row.get('FT_PCT', 0)
                ))
                inserted += 1
            except Exception as e:
                pass
        
        conn.commit()
        
        # Update rolling averages
        if inserted > 0:
            avg_pts = df['PTS'].mean()
            avg_reb = df['REB'].mean()
            avg_ast = df['AST'].mean()
            
            cursor.execute("""
                INSERT OR REPLACE INTO player_rolling_averages 
                (player_id, avg_points, avg_rebounds, avg_assists, games_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(player_id),
                round(avg_pts, 1),
                round(avg_reb, 1),
                round(avg_ast, 1),
                len(df),
                datetime.now().isoformat()
            ))
            conn.commit()
        
        conn.close()
        print(f"         Inserted {inserted} games (avg: {df['PTS'].mean():.1f} pts)")
        return inserted
        
    except Exception as e:
        print(f"         Error: {e}")
        return 0

def main():
    print("\n" + "="*60)
    print("  GAME LOG CHECKER FOR TODAY'S GAMES")
    print("="*60)
    
    # 1. Get today's games
    games = get_todays_schedule()
    
    if not games:
        print("No games found for today")
        return
    
    # 2. Collect all teams playing
    print("\n2. TEAMS PLAYING TODAY")
    print("-" * 50)
    
    teams = set()
    for game in games:
        home = game.get("home_team_id") or game.get("home_tricode")
        away = game.get("away_team_id") or game.get("away_tricode")
        if home:
            teams.add(home)
        if away:
            teams.add(away)
    
    print(f"   {len(teams)} teams: {', '.join(str(t) for t in list(teams)[:10])}")
    
    # 3. Get all players from these teams
    print("\n3. CHECKING PLAYER GAME LOGS")
    print("-" * 50)
    
    all_players = []
    for team_id in teams:
        players = get_team_players(str(team_id))
        print(f"   {team_id}: {len(players)} players")
        all_players.extend(players)
    
    print(f"\n   Total players to check: {len(all_players)}")
    
    # 4. Check each player for game logs
    print("\n4. GAME LOG STATUS")
    print("-" * 50)
    
    missing = []
    has_data = []
    
    for player in all_players:
        status = check_player_game_logs(player["player_id"])
        
        if status["game_log_count"] == 0 and not status["has_rolling_avg"]:
            missing.append({**player, **status})
        else:
            has_data.append({**player, **status})
    
    print(f"   Players WITH game logs: {len(has_data)}")
    print(f"   Players MISSING game logs: {len(missing)}")
    
    # 5. Show sample of players with data
    if has_data:
        print("\n   Sample players with data:")
        for p in has_data[:5]:
            print(f"      {p['name']:25s} - {p['game_log_count']} games, avg {p['avg_points']:.1f} pts")
    
    # 6. Fetch missing game logs
    if missing:
        print(f"\n5. FETCHING MISSING GAME LOGS ({len(missing)} players)")
        print("-" * 50)
        
        # Limit to first 20 to avoid rate limiting
        to_fetch = missing[:20]
        print(f"   Fetching first {len(to_fetch)} players (rate limited)...")
        
        fetched = 0
        for player in to_fetch:
            result = fetch_player_game_logs(player["player_id"], player["name"])
            if result > 0:
                fetched += 1
        
        print(f"\n   Successfully fetched data for {fetched}/{len(to_fetch)} players")
        
        if len(missing) > 20:
            print(f"   NOTE: {len(missing) - 20} more players need data - run again to continue")
    else:
        print("\n   All players have game log data!")
    
    print("\n" + "="*60)
    print("  COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
