"""
Test simulation for ONE real game today.
Uses working NBA API logic from fetch_todays_players_logs.py.
"""
import requests
import sqlite3
from datetime import datetime
from pathlib import Path

# === CONFIG ===
BASE_URL = "http://localhost:5000"
DB_PATH = Path(__file__).parent / "data" / "nba_data.db"

# NBA Team ID to Abbreviation mapping
TEAM_ID_MAP = {
    "1610612737": "ATL", "1610612738": "BOS", "1610612751": "BKN", "1610612766": "CHA",
    "1610612741": "CHI", "1610612739": "CLE", "1610612742": "DAL", "1610612743": "DEN",
    "1610612765": "DET", "1610612744": "GSW", "1610612745": "HOU", "1610612754": "IND",
    "1610612746": "LAC", "1610612747": "LAL", "1610612763": "MEM", "1610612748": "MIA",
    "1610612749": "MIL", "1610612750": "MIN", "1610612740": "NOP", "1610612752": "NYK",
    "1610612760": "OKC", "1610612753": "ORL", "1610612755": "PHI", "1610612756": "PHX",
    "1610612757": "POR", "1610612758": "SAC", "1610612759": "SAS", "1610612761": "TOR",
    "1610612762": "UTA", "1610612764": "WAS"
}

def get_todays_games():
    """Get today's games directly from NBA API (working logic)"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    NBA_API_URL = "https://stats.nba.com/stats/scoreboardv2"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "Accept-Language": "en-US,en;q=0.9"
    }
    params = {"DayOffset": 0, "GameDate": today, "LeagueID": "00"}
    
    try:
        response = requests.get(NBA_API_URL, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            for rs in data.get('resultSets', []):
                if rs.get('name') == 'GameHeader':
                    headers = rs.get('headers', [])
                    rows = rs.get('rowSet', [])
                    games = []
                    for row in rows:
                        g = dict(zip(headers, row))
                        games.append({
                            'game_id': g.get('GAME_ID'),
                            'home_team_id': str(g.get('HOME_TEAM_ID')),
                            'away_team_id': str(g.get('VISITOR_TEAM_ID')),
                            'status': g.get('GAME_STATUS_TEXT', 'TBD')
                        })
                    return games
    except Exception as e:
        print(f"Error fetching schedule: {e}")
    return []


def get_team_roster(team_id):
    """Get roster using team abbreviation"""
    team_abbr = TEAM_ID_MAP.get(team_id, team_id)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_id, name, position
        FROM players WHERE team_id = ?
        ORDER BY name LIMIT 8
    """, (team_abbr,))
    
    players = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return players


def run_simulation(player_id, opponent_id):
    """Run simulation for a player"""
    try:
        url = f"{BASE_URL}/aegis/simulate/{player_id}?opponent_id={opponent_id}"
        res = requests.get(url, timeout=30)
        if res.ok:
            return res.json()
    except Exception as e:
        print(f"  Error: {e}")
    return None


def main():
    print("=" * 60)
    print("REAL GAME SIMULATION TEST")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Get today's games
    games = get_todays_games()
    if not games:
        print("\nNo games found today!")
        return
    
    print(f"\nFound {len(games)} games today")
    
    # Pick FIRST game only
    game = games[0]
    home_id = game['home_team_id']
    away_id = game['away_team_id']
    home_abbr = TEAM_ID_MAP.get(home_id, home_id)
    away_abbr = TEAM_ID_MAP.get(away_id, away_id)
    
    print(f"\n>>> Testing: {away_abbr} @ {home_abbr}")
    print(f"    Status: {game['status']}")
    print("-" * 60)
    
    # Get rosters
    home_roster = get_team_roster(home_id)
    away_roster = get_team_roster(away_id)
    
    print(f"\n{home_abbr} Roster: {len(home_roster)} players loaded")
    print(f"{away_abbr} Roster: {len(away_roster)} players loaded")
    
    # Run simulations for top 3 players from each team
    print("\n=== SIMULATIONS ===\n")
    
    all_results = []
    
    for i, player in enumerate(home_roster[:3]):
        print(f"[{i+1}] {player['name']} ({home_abbr}) vs {away_abbr}")
        result = run_simulation(player['player_id'], away_id)
        if result:
            proj = result.get('projections', {})
            ev = proj.get('expected_value', {})
            pts = ev.get('points', 0)
            reb = ev.get('rebounds', 0)
            ast = ev.get('assists', 0)
            print(f"    PTS: {pts}, REB: {reb}, AST: {ast}")
            all_results.append({'name': player['name'], 'pts': pts, 'reb': reb, 'ast': ast})
        else:
            print(f"    (No data)")
    
    for i, player in enumerate(away_roster[:3]):
        print(f"[{i+4}] {player['name']} ({away_abbr}) vs {home_abbr}")
        result = run_simulation(player['player_id'], home_id)
        if result:
            proj = result.get('projections', {})
            ev = proj.get('expected_value', {})
            pts = ev.get('points', 0)
            reb = ev.get('rebounds', 0)
            ast = ev.get('assists', 0)
            print(f"    PTS: {pts}, REB: {reb}, AST: {ast}")
            all_results.append({'name': player['name'], 'pts': pts, 'reb': reb, 'ast': ast})
        else:
            print(f"    (No data)")
    
    print("\n" + "=" * 60)
    print(f"TEST COMPLETE: {len(all_results)} players simulated")
    print("=" * 60)


if __name__ == "__main__":
    main()
