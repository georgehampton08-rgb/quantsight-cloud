"""
HISTORICAL MATCHUP ANALYSIS: Last Games vs Opponent
===================================================
Shows the last 2 games each player played against their opponent
to provide concrete recent history for matchup intelligence.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Configuration
HOME_TEAM = "CLE"
AWAY_TEAM = "LAL"

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\n" + "="*70)
print(f"🏀 HISTORICAL MATCHUP ANALYSIS: {AWAY_TEAM} @ {HOME_TEAM}")
print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*70)

def get_team_defense_profile(team):
    """Get team defensive stats"""
    cursor.execute("""
        SELECT def_rating, opp_pts, pace FROM team_defense WHERE team_abbr = ?
    """, (team,))
    row = cursor.fetchone()
    if row:
        return {
            'def_rating': row['def_rating'],
            'opp_pts': row['opp_pts'],
            'pace': row['pace']
        }
    return None

def get_players_for_team(team):
    """Get top players for a team"""
    cursor.execute("""
        SELECT pra.player_id, pra.player_name, pb.position, pra.avg_points
        FROM player_rolling_averages pra
        JOIN player_bio pb ON pra.player_id = pb.player_id
        WHERE pb.team = ?
        ORDER BY pra.avg_points DESC
        LIMIT 8
    """, (team,))
    return [dict(row) for row in cursor.fetchall()]

def get_last_n_games_vs_opponent(player_id, opponent, n=2):
    """Get the last N games this player played vs the opponent"""
    cursor.execute("""
        SELECT game_date, points, rebounds, assists, fg_pct, minutes
        FROM player_game_logs
        WHERE player_id = ? AND opponent = ?
        ORDER BY game_date DESC
        LIMIT ?
    """, (str(player_id), opponent, n))
    return [dict(row) for row in cursor.fetchall()]

def get_player_season_avg(player_id):
    """Get player's season averages"""
    cursor.execute("""
        SELECT avg_points, avg_rebounds, avg_assists
        FROM player_rolling_averages
        WHERE player_id = ?
    """, (str(player_id),))
    row = cursor.fetchone()
    return dict(row) if row else None

def calculate_grade(avg_vs_opp, season_avg):
    """Calculate matchup grade based on historical performance"""
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

# Get team defense profiles
print("\n📊 TEAM DEFENSIVE PROFILES")
print("-"*70)

for team in [HOME_TEAM, AWAY_TEAM]:
    defense = get_team_defense_profile(team)
    if defense:
        print(f"   {team}: DEF_RATING {defense['def_rating']:.1f} | OPP_PTS {defense['opp_pts']:.1f} | PACE {defense['pace']:.1f}")
    else:
        print(f"   {team}: No defensive data")

# Analyze each team
for team, opponent in [(AWAY_TEAM, HOME_TEAM), (HOME_TEAM, AWAY_TEAM)]:
    print(f"\n{'='*70}")
    print(f"🏀 {team} PLAYERS vs {opponent}")
    print("="*70)
    
    players = get_players_for_team(team)
    
    if not players:
        print(f"   No players found for {team}")
        continue
    
    for player in players:
        pid = player['player_id']
        name = player['player_name']
        pos = player.get('position', 'N/A')
        season_ppg = player.get('avg_points', 0)
        
        # Get last 2 games vs opponent
        history = get_last_n_games_vs_opponent(pid, opponent, 2)
        
        # Calculate grade
        if history:
            avg_vs_opp = sum(g['points'] for g in history) / len(history)
            grade, status = calculate_grade(avg_vs_opp, season_ppg)
            games_count = len(history)
        else:
            avg_vs_opp = None
            grade, status = "?", "No History"
            games_count = 0
        
        print(f"\n   📍 {name} ({pos}) - Season: {season_ppg:.1f} PPG")
        print(f"      Grade: {grade} ({status})")
        
        if history:
            print(f"      Last {games_count} game(s) vs {opponent}:")
            for g in history:
                date = g['game_date']
                pts = g['points']
                reb = g['rebounds']
                ast = g['assists']
                fg = g['fg_pct'] * 100 if g['fg_pct'] else 0
                mins = g['minutes']
                
                # Delta from season average
                delta = pts - season_ppg
                delta_str = f"{delta:+.1f}" if season_ppg > 0 else "N/A"
                
                print(f"         {date}: {pts} PTS ({delta_str}) | {reb} REB | {ast} AST | {fg:.0f}% FG | {mins:.0f} MIN")
            
            # Summary vs this opponent
            avg_pts = sum(g['points'] for g in history) / len(history)
            delta_pct = ((avg_pts - season_ppg) / season_ppg * 100) if season_ppg > 0 else 0
            print(f"      ➡️  AVG vs {opponent}: {avg_pts:.1f} PPG ({delta_pct:+.1f}% vs season)")
        else:
            print(f"      ⚠️  No game history vs {opponent} in database")
            print(f"      ➡️  Using season average: {season_ppg:.1f} PPG")

# Summary
print(f"\n{'='*70}")
print("📋 MATCHUP SUMMARY")
print("="*70)

all_matchups = []
for team, opponent in [(AWAY_TEAM, HOME_TEAM), (HOME_TEAM, AWAY_TEAM)]:
    players = get_players_for_team(team)
    for player in players:
        pid = player['player_id']
        history = get_last_n_games_vs_opponent(pid, opponent, 2)
        season_ppg = player.get('avg_points', 0)
        
        if history:
            avg_vs = sum(g['points'] for g in history) / len(history)
            delta = avg_vs - season_ppg
            grade, status = calculate_grade(avg_vs, season_ppg)
            all_matchups.append({
                'name': player['player_name'],
                'team': team,
                'vs': opponent,
                'season_ppg': season_ppg,
                'avg_vs': avg_vs,
                'delta': delta,
                'games': len(history),
                'grade': grade,
                'status': status
            })

if all_matchups:
    # Sort by advantage
    all_matchups.sort(key=lambda x: x['delta'], reverse=True)
    
    print("\n   🔥 BEST HISTORICAL MATCHUPS (overperform vs opponent):")
    for m in all_matchups[:3]:
        print(f"      {m['name']} ({m['team']}): {m['season_ppg']:.1f} → {m['avg_vs']:.1f} PPG ({m['delta']:+.1f}) [{m['grade']}] [{m['games']}g vs {m['vs']}]")
    
    print("\n   ❄️ WORST HISTORICAL MATCHUPS (underperform vs opponent):")
    for m in all_matchups[-3:]:
        print(f"      {m['name']} ({m['team']}): {m['season_ppg']:.1f} → {m['avg_vs']:.1f} PPG ({m['delta']:+.1f}) [{m['grade']}] [{m['games']}g vs {m['vs']}]")
else:
    print("\n   ⚠️  No historical matchup data found for these teams")
    print("   The 15-game fetch may not include LAL vs CLE games yet")

conn.close()
print("\n" + "="*70)
print("✅ Analysis complete!")
