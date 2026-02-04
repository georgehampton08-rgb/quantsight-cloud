"""
CONFLUENCE PROJECTION ENGINE: Multi-Factor Analysis
=====================================================
Combines ALL data sources for comprehensive player projections:
1. Season Baseline (current averages)
2. Head-to-Head History (vs opponent performance)
3. Recent Form (last 5 games trend - hot/cold)
4. Team Defense (opponent defensive metrics)
5. Pace Impact (game tempo adjustment)
6. Usage Context (minutes and role)
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import json

# Configuration
HOME_TEAM = "CLE"
AWAY_TEAM = "LAL"
LEAGUE_AVG_PACE = 99.5
LEAGUE_AVG_PPG = 115.0

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("\n" + "="*80)
print(f"🔮 CONFLUENCE PROJECTION ENGINE: {AWAY_TEAM} @ {HOME_TEAM}")
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

def get_team_defense(team):
    """Get team defensive profile"""
    cursor.execute("""
        SELECT def_rating, opp_pts, pace, opp_fg_pct FROM team_defense WHERE team_abbr = ?
    """, (team,))
    row = cursor.fetchone()
    if row:
        return {
            'def_rating': row['def_rating'] or 110,
            'opp_pts': row['opp_pts'] or 115,
            'pace': row['pace'] or 99.5,
            'opp_fg_pct': row['opp_fg_pct'] or 0.46,
        }
    return {'def_rating': 110, 'opp_pts': 115, 'pace': 99.5, 'opp_fg_pct': 0.46}

def get_players_for_team(team):
    """Get players with stats"""
    cursor.execute("""
        SELECT pra.player_id, pra.player_name, pb.position, 
               pra.avg_points, pra.avg_rebounds, pra.avg_assists,
               pra.trend, pra.hot_streak, pra.cold_streak
        FROM player_rolling_averages pra
        JOIN player_bio pb ON pra.player_id = pb.player_id
        WHERE pb.team = ?
        ORDER BY pra.avg_points DESC
        LIMIT 8
    """, (team,))
    return [dict(row) for row in cursor.fetchall()]

def get_head_to_head(player_id, opponent):
    """Get player's history vs opponent"""
    cursor.execute("""
        SELECT avg_pts, games FROM player_vs_team 
        WHERE player_id = ? AND opponent = ?
    """, (str(player_id), opponent))
    row = cursor.fetchone()
    if row:
        return {'avg_pts': row['avg_pts'], 'games': row['games']}
    return None

def get_recent_games(player_id, n=5):
    """Get player's recent games for form analysis"""
    cursor.execute("""
        SELECT points, game_date FROM player_game_logs
        WHERE player_id = ?
        ORDER BY game_date DESC
        LIMIT ?
    """, (str(player_id), n))
    return [dict(row) for row in cursor.fetchall()]

def calculate_form_score(player_id, season_avg):
    """Calculate recent form score (-1 cold to +1 hot)"""
    games = get_recent_games(player_id, 5)
    if not games or season_avg == 0:
        return 0, "Neutral"
    
    recent_avg = sum(g['points'] for g in games) / len(games)
    delta_pct = (recent_avg - season_avg) / season_avg
    
    if delta_pct > 0.15:
        return 0.15, "🔥 HOT"
    elif delta_pct > 0.05:
        return 0.08, "📈 Warm"
    elif delta_pct < -0.15:
        return -0.15, "❄️ COLD"
    elif delta_pct < -0.05:
        return -0.08, "📉 Cool"
    else:
        return 0, "➖ Neutral"

def calculate_defense_impact(opponent_defense, position):
    """Calculate defensive impact based on opponent defense"""
    opp_pts = opponent_defense['opp_pts']
    diff_from_avg = opp_pts - LEAGUE_AVG_PPG
    
    # Position-based scaling
    pos_scale = {
        'PG': 0.9, 'G': 0.92, 'SG': 0.95,
        'SF': 1.0, 'F': 1.0,
        'PF': 1.05, 'C': 1.1, 'C-F': 1.08, 'F-C': 1.05
    }
    scale = pos_scale.get(position, 1.0)
    
    # Calculate adjustment (-3 to +3 points typically)
    adjustment = diff_from_avg * scale * 0.08
    
    label = "Elite D" if opp_pts < 108 else "Good D" if opp_pts < 112 else "Average D" if opp_pts < 116 else "Weak D"
    
    return round(adjustment, 1), label

def calculate_pace_multiplier(team1_defense, team2_defense):
    """Calculate pace impact on scoring"""
    pace1 = team1_defense['pace']
    pace2 = team2_defense['pace']
    avg_pace = (pace1 + pace2) / 2
    
    # How much faster/slower than league average
    pace_diff = (avg_pace - LEAGUE_AVG_PACE) / LEAGUE_AVG_PACE
    multiplier = 1 + pace_diff
    
    label = "Fast" if avg_pace > 102 else "Slow" if avg_pace < 97 else "Average"
    
    return round(multiplier, 3), label, round(avg_pace, 1)

def calculate_confluence_projection(player, opponent, opponent_defense, pace_mult):
    """
    The core CONFLUENCE calculation:
    Final = Baseline × (1 + Form) × (1 + H2H Weight) + Defense Adj × Pace
    """
    pid = player['player_id']
    name = player['player_name']
    pos = player.get('position', 'SF')
    baseline = player.get('avg_points', 15) or 15
    
    # 1. Form Analysis (recent games trend)
    form_adj, form_label = calculate_form_score(pid, baseline)
    
    # 2. Head-to-Head History
    h2h = get_head_to_head(pid, opponent)
    if h2h and h2h['games'] >= 2:
        h2h_avg = h2h['avg_pts']
        h2h_delta = h2h_avg - baseline
        # Weight H2H more heavily if more games
        h2h_weight = min(h2h['games'] / 10, 0.4)  # Max 40% weight
        h2h_contribution = h2h_delta * h2h_weight
        h2h_label = f"{h2h_avg:.1f} ({h2h['games']}g)"
    else:
        h2h_contribution = 0
        h2h_label = "No data"
    
    # 3. Defense Impact
    def_adj, def_label = calculate_defense_impact(opponent_defense, pos)
    
    # 4. Form adjustment
    form_pts = baseline * form_adj
    
    # 5. Combine all factors
    # Projection = (Baseline + H2H contribution + Form boost + Defense adjustment) × Pace
    raw_projection = baseline + h2h_contribution + form_pts + def_adj
    final_projection = raw_projection * pace_mult
    
    # Confidence score based on data availability
    confidence = 60  # Base
    if h2h and h2h['games'] >= 2:
        confidence += 20
    if form_label in ['🔥 HOT', '❄️ COLD']:
        confidence += 10
    confidence += 10  # Defense data always available
    
    return {
        'player': name,
        'position': pos,
        'baseline': round(baseline, 1),
        'form_adj': round(form_pts, 1),
        'form_label': form_label,
        'h2h_avg': h2h_label,
        'h2h_contrib': round(h2h_contribution, 1),
        'def_adj': def_adj,
        'def_label': def_label,
        'pace_mult': pace_mult,
        'projected': round(final_projection, 1),
        'delta': round(final_projection - baseline, 1),
        'confidence': confidence
    }

# Get defense profiles
home_defense = get_team_defense(HOME_TEAM)
away_defense = get_team_defense(AWAY_TEAM)

# Calculate pace
pace_mult, pace_label, avg_pace = calculate_pace_multiplier(home_defense, away_defense)

print(f"\n📊 MATCHUP CONTEXT")
print("-"*80)
print(f"   {HOME_TEAM} Defense: {home_defense['opp_pts']:.1f} PPG allowed | DEF RTG: {home_defense['def_rating']:.1f}")
print(f"   {AWAY_TEAM} Defense: {away_defense['opp_pts']:.1f} PPG allowed | DEF RTG: {away_defense['def_rating']:.1f}")
print(f"   Pace: {avg_pace} ({pace_label}) | Multiplier: {pace_mult}")

all_projections = []

for team, opponent, opponent_def in [(AWAY_TEAM, HOME_TEAM, home_defense), (HOME_TEAM, AWAY_TEAM, away_defense)]:
    print(f"\n{'='*80}")
    print(f"🏀 {team} PROJECTIONS vs {opponent}")
    print("="*80)
    print(f"\n   {'Player':<18} {'Pos':<4} {'Base':<6} {'Form':<8} {'H2H':<10} {'Def':<8} {'Proj':<7} {'Δ':<6} {'Conf':<5}")
    print(f"   {'-'*75}")
    
    players = get_players_for_team(team)
    
    for player in players:
        p = calculate_confluence_projection(player, opponent, opponent_def, pace_mult)
        
        print(f"   {p['player']:<18} {p['position']:<4} {p['baseline']:<6.1f} {p['form_label']:<8} {p['h2h_avg']:<10} {p['def_label']:<8} {p['projected']:<7.1f} {p['delta']:+5.1f} {p['confidence']}%")
        
        all_projections.append({
            'team': team,
            'opponent': opponent,
            **p
        })

# Summary
print(f"\n{'='*80}")
print("📋 CONFLUENCE PROJECTION SUMMARY")
print("="*80)

# Sort by delta (advantage)
all_projections.sort(key=lambda x: x['delta'], reverse=True)

print("\n   🔥 BEST CONFLUENCE MATCHUPS (highest projected boost):")
for p in all_projections[:5]:
    print(f"      {p['player']:18} ({p['team']}): {p['baseline']:.1f} → {p['projected']:.1f} ({p['delta']:+.1f}) | {p['form_label']} | {p['h2h_avg']} | {p['confidence']}%")

print("\n   ❄️ WORST CONFLUENCE MATCHUPS (lowest projected):")
for p in all_projections[-5:]:
    print(f"      {p['player']:18} ({p['team']}): {p['baseline']:.1f} → {p['projected']:.1f} ({p['delta']:+.1f}) | {p['form_label']} | {p['h2h_avg']} | {p['confidence']}%")

# High confidence picks
high_conf = [p for p in all_projections if p['confidence'] >= 80]
if high_conf:
    print("\n   ⭐ HIGH CONFIDENCE PROJECTIONS (80%+):")
    for p in sorted(high_conf, key=lambda x: x['projected'], reverse=True)[:5]:
        print(f"      {p['player']:18} ({p['team']}): {p['projected']:.1f} PPG | {p['confidence']}% confidence")

# Save to file
output = {
    'game': f"{AWAY_TEAM} @ {HOME_TEAM}",
    'generated_at': datetime.now().isoformat(),
    'pace': {'value': avg_pace, 'multiplier': pace_mult, 'label': pace_label},
    'home_defense': home_defense,
    'away_defense': away_defense,
    'projections': all_projections
}

output_file = db_path.parent / 'confluence_projections.json'
with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

conn.close()
print(f"\n   📁 Full projections saved to: {output_file}")
print("\n" + "="*80)
print("✅ Confluence Analysis Complete!")
