"""
FETCH MATCHUP HISTORY: Last 2 Games vs Opponent
===============================================
Fetches each player's last 2 games against the opponent team
directly from NBA API for targeted matchup intelligence.
"""

import requests
import sqlite3
import time
from pathlib import Path
from datetime import datetime

# Configuration
HOME_TEAM = "CLE"
AWAY_TEAM = "LAL"

# Team IDs
TEAM_IDS = {
    'ATL': 1610612737, 'BOS': 1610612738, 'BKN': 1610612751, 'CHA': 1610612766,
    'CHI': 1610612741, 'CLE': 1610612739, 'DAL': 1610612742, 'DEN': 1610612743,
    'DET': 1610612765, 'GSW': 1610612744, 'HOU': 1610612745, 'IND': 1610612754,
    'LAC': 1610612746, 'LAL': 1610612747, 'MEM': 1610612763, 'MIA': 1610612748,
    'MIL': 1610612749, 'MIN': 1610612750, 'NOP': 1610612740, 'NYK': 1610612752,
    'OKC': 1610612760, 'ORL': 1610612753, 'PHI': 1610612755, 'PHX': 1610612756,
    'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'TOR': 1610612761,
    'UTA': 1610612762, 'WAS': 1610612764,
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
}

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

def get_players_for_team(team):
    """Get top players for a team from our database"""
    cursor.execute("""
        SELECT pra.player_id, pra.player_name, pb.position, pra.avg_points
        FROM player_rolling_averages pra
        JOIN player_bio pb ON pra.player_id = pb.player_id
        WHERE pb.team = ?
        ORDER BY pra.avg_points DESC
        LIMIT 8
    """, (team,))
    return [dict(row) for row in cursor.fetchall()]

def fetch_player_games_vs_opponent(player_id, opponent_id, last_n=2):
    """Fetch player's game logs vs a specific opponent from NBA API"""
    url = "https://stats.nba.com/stats/playergamelogs"
    
    params = {
        'DateFrom': '',
        'DateTo': '',
        'GameSegment': '',
        'LastNGames': '0',
        'LeagueID': '00',
        'Location': '',
        'MeasureType': 'Base',
        'Month': '0',
        'OppTeamID': opponent_id,  # Filter by opponent
        'Outcome': '',
        'PORound': '0',
        'PaceAdjust': 'N',
        'PerMode': 'Totals',
        'Period': '0',
        'PlayerID': player_id,
        'PlusMinus': 'N',
        'Rank': 'N',
        'Season': '2024-25',
        'SeasonSegment': '',
        'SeasonType': 'Regular Season',
        'ShotClockRange': '',
        'VsConference': '',
        'VsDivision': '',
    }
    
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            result_sets = data.get('resultSets', [])
            if result_sets:
                headers = result_sets[0].get('headers', [])
                rows = result_sets[0].get('rowSet', [])
                
                games = []
                for row in rows[:last_n]:
                    game = dict(zip(headers, row))
                    games.append({
                        'date': game.get('GAME_DATE', 'Unknown'),
                        'matchup': game.get('MATCHUP', ''),
                        'pts': game.get('PTS', 0),
                        'reb': game.get('REB', 0),
                        'ast': game.get('AST', 0),
                        'fg_pct': game.get('FG_PCT', 0) * 100 if game.get('FG_PCT') else 0,
                        'min': game.get('MIN', 0),
                        'plus_minus': game.get('PLUS_MINUS', 0),
                        'wl': game.get('WL', ''),
                    })
                return games
    except Exception as e:
        print(f"      ⚠️  API Error: {e}")
    
    return []

def calculate_grade(avg_vs_opp, season_avg):
    """Calculate matchup grade"""
    if not avg_vs_opp or not season_avg or season_avg == 0:
        return "?", "No History"
    
    delta_pct = (avg_vs_opp - season_avg) / season_avg * 100
    
    if delta_pct > 15:
        return "A+", "Nemesis Mode"
    elif delta_pct > 5:
        return "B", "Favorable"
    elif delta_pct > -5:
        return "C", "Neutral"
    elif delta_pct > -15:
        return "D", "Disadvantage"
    else:
        return "F", "Locked Down"

print("\n" + "="*70)
print(f"🔍 LIVE API MATCHUP FETCH: {AWAY_TEAM} @ {HOME_TEAM}")
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*70)
print(f"\nFetching each player's last 2 games vs opponent from NBA API...")

all_matchups = []

for team, opponent in [(AWAY_TEAM, HOME_TEAM), (HOME_TEAM, AWAY_TEAM)]:
    print(f"\n{'='*70}")
    print(f"🏀 {team} PLAYERS vs {opponent}")
    print("="*70)
    
    opponent_id = TEAM_IDS.get(opponent)
    players = get_players_for_team(team)
    
    for player in players:
        pid = player['player_id']
        name = player['player_name']
        pos = player.get('position', 'N/A')
        season_ppg = player.get('avg_points', 0)
        
        print(f"\n   📍 {name} ({pos}) - Season: {season_ppg:.1f} PPG")
        
        # Fetch from API
        print(f"      Fetching vs {opponent}...", end=" ")
        games = fetch_player_games_vs_opponent(pid, opponent_id, 2)
        
        if games:
            print(f"✅ Found {len(games)} game(s)")
            
            for g in games:
                delta = g['pts'] - season_ppg
                print(f"         {g['date']}: {g['pts']} PTS ({delta:+.1f}) | {g['reb']} REB | {g['ast']} AST | {g['fg_pct']:.0f}% | {g['wl']}")
            
            # Calculate average and grade
            avg_pts = sum(g['pts'] for g in games) / len(games)
            grade, status = calculate_grade(avg_pts, season_ppg)
            delta_pct = ((avg_pts - season_ppg) / season_ppg * 100) if season_ppg > 0 else 0
            
            print(f"      ➡️  AVG vs {opponent}: {avg_pts:.1f} PPG ({delta_pct:+.1f}%)")
            print(f"      🎯 Grade: {grade} ({status})")
            
            all_matchups.append({
                'name': name,
                'team': team,
                'vs': opponent,
                'season_ppg': season_ppg,
                'avg_vs': avg_pts,
                'delta': avg_pts - season_ppg,
                'games': len(games),
                'grade': grade,
            })
            
            # Save to database
            cursor.execute("""
                INSERT OR REPLACE INTO player_vs_team 
                (player_id, opponent, games, avg_pts, last_game_date, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (str(pid), opponent, len(games), avg_pts, games[0]['date']))
        else:
            print(f"❌ No games vs {opponent} this season")
        
        time.sleep(0.8)  # Rate limit

conn.commit()

# Summary
print(f"\n{'='*70}")
print("📋 MATCHUP INTELLIGENCE SUMMARY")
print("="*70)

if all_matchups:
    all_matchups.sort(key=lambda x: x['delta'], reverse=True)
    
    print("\n   🔥 BEST HISTORICAL MATCHUPS:")
    for m in all_matchups[:3]:
        print(f"      {m['name']} ({m['team']}): {m['season_ppg']:.1f} → {m['avg_vs']:.1f} PPG ({m['delta']:+.1f}) [{m['grade']}]")
    
    print("\n   ❄️ WORST HISTORICAL MATCHUPS:")
    for m in all_matchups[-3:]:
        print(f"      {m['name']} ({m['team']}): {m['season_ppg']:.1f} → {m['avg_vs']:.1f} PPG ({m['delta']:+.1f}) [{m['grade']}]")
else:
    print("\n   ⚠️  No historical matchup data found - may be first meeting this season")

conn.close()
print(f"\n{'='*70}")
print("✅ Matchup fetch complete! Data saved to database.")
