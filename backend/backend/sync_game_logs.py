"""
Robust Game Log Collector - All Active Players
===============================================
Syncs ALL active players from today's games with proper delays and error handling.
"""
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "nba_data.db"

# Conservative delays to avoid rate limiting
ROSTER_DELAY = 2.0    # seconds between roster fetches
PLAYER_DELAY = 2.5    # seconds between player log fetches
BATCH_REST = 10       # seconds rest after every 10 players
ERROR_COOLDOWN = 15   # seconds to wait after an error


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def setup_tables():
    """Create tables if they don't exist (preserves existing data)"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            game_id TEXT,
            game_date TEXT,
            matchup TEXT,
            wl TEXT,
            min REAL,
            pts INTEGER,
            reb INTEGER,
            ast INTEGER,
            stl INTEGER,
            blk INTEGER,
            tov INTEGER,
            fg_pct REAL,
            fg3_pct REAL,
            ft_pct REAL,
            UNIQUE(player_id, game_id)
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS player_rolling_averages (
            player_id TEXT PRIMARY KEY,
            player_name TEXT,
            avg_points REAL,
            avg_rebounds REAL,
            avg_assists REAL,
            games_count INTEGER,
            updated_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def get_synced_player_ids():
    """Get list of player IDs that already have data"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT player_id FROM game_logs")
    ids = set(row["player_id"] for row in c.fetchall())
    conn.close()
    return ids


def get_todays_teams():
    """Get teams playing today from backend"""
    import requests
    
    try:
        r = requests.get("http://localhost:5000/schedule", timeout=30)
        data = r.json()
        games = data.get("games", [])
        
        teams = []
        for g in games:
            if g.get("home") and g["home"] not in teams:
                teams.append(g["home"])
            if g.get("away") and g["away"] not in teams:
                teams.append(g["away"])
        
        return teams, len(games)
    except Exception as e:
        print(f"    Error: {e}")
        return [], 0


def get_active_roster(team_abbr):
    """Get active roster from NBA API with delay"""
    from nba_api.stats.endpoints import commonteamroster
    from nba_api.stats.static import teams
    
    team_list = teams.get_teams()
    team = next((t for t in team_list if t['abbreviation'] == team_abbr), None)
    if not team:
        return []
    
    try:
        time.sleep(ROSTER_DELAY)
        roster = commonteamroster.CommonTeamRoster(team_id=team['id'], season='2024-25', timeout=60)
        df = roster.get_data_frames()[0]
        return [{"id": str(row['PLAYER_ID']), "name": row['PLAYER']} for _, row in df.iterrows()]
    except Exception as e:
        print(f"      [!] Failed {team_abbr}: {str(e)[:30]}")
        return []


def fetch_player_logs(player_id, player_name):
    """Fetch and save game logs for one player"""
    from nba_api.stats.endpoints import playergamelog
    
    try:
        time.sleep(PLAYER_DELAY)
        
        log = playergamelog.PlayerGameLog(
            player_id=player_id,
            season='2024-25',
            season_type_all_star='Regular Season',
            timeout=60
        )
        
        df = log.get_data_frames()[0]
        
        if df.empty:
            return 0, 0
        
        conn = get_db()
        c = conn.cursor()
        
        for _, row in df.iterrows():
            c.execute("""
                INSERT OR REPLACE INTO game_logs 
                (player_id, game_id, game_date, matchup, wl, min, pts, reb, ast, stl, blk, tov, fg_pct, fg3_pct, ft_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(player_id), row['Game_ID'], row['GAME_DATE'], row['MATCHUP'], row['WL'],
                row['MIN'], row['PTS'], row['REB'], row['AST'], row['STL'],
                row['BLK'], row['TOV'], row['FG_PCT'], row['FG3_PCT'], row['FT_PCT']
            ))
        
        avg_pts = round(df['PTS'].mean(), 1)
        avg_reb = round(df['REB'].mean(), 1)
        avg_ast = round(df['AST'].mean(), 1)
        
        c.execute("""
            INSERT OR REPLACE INTO player_rolling_averages 
            (player_id, player_name, avg_points, avg_rebounds, avg_assists, games_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(player_id), player_name, avg_pts, avg_reb, avg_ast, len(df), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return len(df), avg_pts
        
    except Exception as e:
        return -1, str(e)[:30]


def main():
    print("\n" + "="*70)
    print("  ROBUST GAME LOG SYNC - ALL ACTIVE PLAYERS")
    print("="*70)
    print(f"  Delays: Roster={ROSTER_DELAY}s | Player={PLAYER_DELAY}s | Batch Rest={BATCH_REST}s")
    print("="*70)
    
    setup_tables()
    
    # Get already synced players
    synced_ids = get_synced_player_ids()
    print(f"\n[INFO] Already synced: {len(synced_ids)} players")
    
    # Get today's teams
    print("\n[1] Getting today's schedule...")
    teams, game_count = get_todays_teams()
    
    if not teams:
        print("    No games today")
        return
    
    print(f"    {game_count} games, {len(teams)} teams")
    
    # Get all rosters
    print(f"\n[2] Getting active rosters (with {ROSTER_DELAY}s delay)...")
    
    all_players = []
    for team in teams:
        roster = get_active_roster(team)
        # Filter out already synced players
        new_players = [p for p in roster if p["id"] not in synced_ids]
        print(f"    {team}: {len(roster)} total, {len(new_players)} new")
        for p in new_players:
            p["team"] = team
            all_players.append(p)
    
    print(f"\n    Total new players to sync: {len(all_players)}")
    
    if not all_players:
        print("\n[DONE] All players already synced!")
        
        # Show summary
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM player_rolling_averages")
        total = c.fetchone()[0]
        c.execute("SELECT player_name, avg_points FROM player_rolling_averages ORDER BY avg_points DESC LIMIT 5")
        top = c.fetchall()
        conn.close()
        
        print(f"\n    Total players in database: {total}")
        print("    Top scorers:")
        for p in top:
            print(f"      {p['player_name']}: {p['avg_points']} ppg")
        return
    
    # Sync all players
    print(f"\n[3] Syncing game logs (estimated time: ~{len(all_players) * PLAYER_DELAY / 60:.1f} min)...")
    print("-"*70)
    
    success = 0
    errors = 0
    consecutive_errors = 0
    
    for i, p in enumerate(all_players, 1):
        print(f"[{i}/{len(all_players)}] {p['team']:3s} {p['name']:25s}", end=" ", flush=True)
        
        games, result = fetch_player_logs(p["id"], p["name"])
        
        if games > 0:
            print(f"-> {games} games, {result} ppg")
            success += 1
            consecutive_errors = 0
        elif games == 0:
            print("-> no games")
            consecutive_errors = 0
        else:
            print(f"-> FAILED ({result})")
            errors += 1
            consecutive_errors += 1
            
            # If too many errors, take a break
            if consecutive_errors >= 3:
                print(f"\n    [!] Multiple errors, cooling down {ERROR_COOLDOWN}s...")
                time.sleep(ERROR_COOLDOWN)
                consecutive_errors = 0
        
        # Rest after every 10 players
        if i % 10 == 0 and i < len(all_players):
            print(f"\n    [REST] Processed {i} players, resting {BATCH_REST}s...\n")
            time.sleep(BATCH_REST)
    
    # Summary
    print("\n" + "="*70)
    print(f"  SYNC COMPLETE")
    print("="*70)
    print(f"  Success: {success} | Errors: {errors} | Skipped: {len(all_players) - success - errors}")
    
    # Show top scorers
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM player_rolling_averages")
    total = c.fetchone()[0]
    c.execute("SELECT player_name, avg_points, avg_rebounds, avg_assists FROM player_rolling_averages ORDER BY avg_points DESC LIMIT 10")
    top = c.fetchall()
    conn.close()
    
    print(f"\n  Total players in database: {total}")
    print("\n  TOP 10 SCORERS:")
    for i, p in enumerate(top, 1):
        print(f"    {i:2d}. {p['player_name']:25s} {p['avg_points']:5.1f} ppg | {p['avg_rebounds']:4.1f} rpg | {p['avg_assists']:4.1f} apg")
    
    print("="*70)


if __name__ == "__main__":
    main()
