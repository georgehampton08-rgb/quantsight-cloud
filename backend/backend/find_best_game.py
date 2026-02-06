import sqlite3
import requests
from datetime import datetime

conn = sqlite3.connect('data/nba_data.db')
cur = conn.cursor()

# Get teams with game log coverage
cur.execute("""
    SELECT p.team_id, COUNT(DISTINCT pgl.player_id) as players_with_logs
    FROM players p
    LEFT JOIN player_game_logs pgl ON CAST(p.player_id AS TEXT) = CAST(pgl.player_id AS TEXT)
    WHERE p.team_id IS NOT NULL
    GROUP BY p.team_id
    HAVING players_with_logs > 0
    ORDER BY players_with_logs DESC
""")
teams_with_data = {row[0]: row[1] for row in cur.fetchall()}
print("Teams with game log data:")
for team, count in teams_with_data.items():
    print(f"  {team}: {count} players")

# Get today's games
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

today = datetime.now().strftime('%Y-%m-%d')
NBA_API_URL = "https://stats.nba.com/stats/scoreboardv2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com"
}
params = {"DayOffset": 0, "GameDate": today, "LeagueID": "00"}
response = requests.get(NBA_API_URL, headers=HEADERS, params=params, timeout=30)
data = response.json()

print("\n\nToday's games with data coverage:")
for rs in data.get('resultSets', []):
    if rs.get('name') == 'GameHeader':
        headers = rs.get('headers', [])
        for row in rs.get('rowSet', []):
            g = dict(zip(headers, row))
            home_id = str(g.get('HOME_TEAM_ID'))
            away_id = str(g.get('VISITOR_TEAM_ID'))
            home_abbr = TEAM_ID_MAP.get(home_id, home_id)
            away_abbr = TEAM_ID_MAP.get(away_id, away_id)
            
            home_coverage = teams_with_data.get(home_abbr, 0)
            away_coverage = teams_with_data.get(away_abbr, 0)
            total = home_coverage + away_coverage
            
            marker = "<<< BEST" if total > 0 else ""
            print(f"  {away_abbr} @ {home_abbr}: {away_coverage}+{home_coverage}={total} players with logs {marker}")

conn.close()
