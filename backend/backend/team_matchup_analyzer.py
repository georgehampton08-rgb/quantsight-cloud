"""
Team Matchup Best Picks Analyzer
================================
Analyzes a full team matchup and finds the best player picks for:
- Points (PTS)
- Rebounds (REB) 
- Assists (AST)
- Three-Pointers (3PM)
"""
import requests
import json
from typing import Dict, List

BASE_URL = "http://localhost:5000"

# Today's games - we'll use one as example
SAMPLE_MATCHUPS = [
    ("1610612747", "1610612764", "LAL @ WAS"),  # Lakers at Wizards
    ("1610612738", "1610612748", "BOS @ MIA"),  # Celtics at Heat
    ("1610612744", "1610612756", "GSW @ PHX"),  # Warriors at Suns
]


def get_matchup_data(home_id: str, away_id: str) -> Dict:
    """Fetch matchup analysis from API"""
    url = f"{BASE_URL}/aegis/matchup?home_team_id={home_id}&away_team_id={away_id}"
    print(f"Fetching matchup data...")
    
    try:
        r = requests.get(url, timeout=120)
        if r.status_code != 200:
            print(f"Error: {r.status_code} - {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return None


def analyze_best_picks(data: Dict, matchup_name: str):
    """Analyze matchup data and find best picks"""
    
    print("\n" + "="*70)
    print(f"  MATCHUP ANALYSIS: {matchup_name}")
    print("="*70)
    
    if not data:
        print("No data available")
        return
    
    # Combine all players from both teams
    home_team = data.get("home_team", {})
    away_team = data.get("away_team", {})
    
    home_name = home_team.get("team_name", "Home")
    away_name = away_team.get("team_name", "Away")
    
    home_players = home_team.get("players", [])
    away_players = away_team.get("players", [])
    
    print(f"\n  {home_name}: {len(home_players)} players")
    print(f"  {away_name}: {len(away_players)} players")
    
    # Add team identifier
    for p in home_players:
        p["team"] = home_name[:3] if len(home_name) >= 3 else home_name
    for p in away_players:
        p["team"] = away_name[:3] if len(away_name) >= 3 else away_name
    
    all_players = home_players + away_players
    
    if not all_players:
        print("No player data")
        return
    
    # Filter to active players only
    active = [p for p in all_players if p.get("is_active", True)]
    print(f"  Active players analyzed: {len(active)}")
    
    print("\n" + "-"*70)
    print("  TOP PICKS BY CATEGORY")
    print("-"*70)
    
    # Best for POINTS
    print("\n  POINTS (EV Points)")
    by_pts = sorted(active, key=lambda x: x.get("ev_points", 0), reverse=True)[:5]
    for i, p in enumerate(by_pts, 1):
        grade = p.get("efficiency_grade", "?")
        matchup = p.get("matchup_advantage", "neutral")
        print(f"    {i}. {p.get('player_name', 'Unknown'):22s} ({p.get('team', '?'):3s}) - "
              f"EV: {p.get('ev_points', 0):5.1f} pts | Grade: {grade:2s} | Matchup: {matchup}")
    
    # Best for REBOUNDS
    print("\n  REBOUNDS (EV Rebounds)")
    by_reb = sorted(active, key=lambda x: x.get("ev_rebounds", 0), reverse=True)[:5]
    for i, p in enumerate(by_reb, 1):
        grade = p.get("efficiency_grade", "?")
        matchup = p.get("matchup_advantage", "neutral")
        print(f"    {i}. {p.get('player_name', 'Unknown'):22s} ({p.get('team', '?'):3s}) - "
              f"EV: {p.get('ev_rebounds', 0):5.1f} reb | Grade: {grade:2s} | Matchup: {matchup}")
    
    # Best for ASSISTS
    print("\n  ASSISTS (EV Assists)")
    by_ast = sorted(active, key=lambda x: x.get("ev_assists", 0), reverse=True)[:5]
    for i, p in enumerate(by_ast, 1):
        grade = p.get("efficiency_grade", "?")
        matchup = p.get("matchup_advantage", "neutral")
        print(f"    {i}. {p.get('player_name', 'Unknown'):22s} ({p.get('team', '?'):3s}) - "
              f"EV: {p.get('ev_assists', 0):5.1f} ast | Grade: {grade:2s} | Matchup: {matchup}")
    
    # Best ARCHETYPE for scoring
    print("\n  BEST ARCHETYPES (High Scorers)")
    scorers = [p for p in active if p.get("archetype") in ["elite_scorer", "sniper", "slasher"]]
    for i, p in enumerate(sorted(scorers, key=lambda x: x.get("ev_points", 0), reverse=True)[:5], 1):
        print(f"    {i}. {p.get('player_name', 'Unknown'):22s} ({p.get('team', '?'):3s}) - "
              f"{p.get('archetype', 'unknown'):15s} | EV: {p.get('ev_points', 0):5.1f} pts")
    
    # Grade Distribution
    print("\n  GRADE DISTRIBUTION")
    grades = {}
    for p in active:
        g = p.get("efficiency_grade", "?")
        grades[g] = grades.get(g, 0) + 1
    for g in ["A", "B+", "B", "C+", "C", "D", "F"]:
        if g in grades:
            print(f"    {g:3s}: {grades[g]} players")
    
    # Matchup Edge
    print(f"\n  MATCHUP EDGE: {data.get('matchup_edge', 'N/A')}")
    print(f"  REASON: {data.get('edge_reason', 'N/A')}")
    
    # Vacuum applied
    vacuum = data.get("usage_vacuum_applied", [])
    if vacuum:
        print(f"  USAGE VACUUM APPLIED TO: {', '.join(vacuum)}")
    
    print("\n" + "="*70)


def main():
    print("\n" + "="*70)
    print("  QUANTSIGHT TEAM MATCHUP ANALYZER")
    print("  Finding best picks for PTS, REB, AST, 3PM")
    print("="*70)
    
    # Test with first matchup
    home_id, away_id, name = SAMPLE_MATCHUPS[0]
    
    data = get_matchup_data(home_id, away_id)
    
    if data:
        analyze_best_picks(data, name)
        
        # Quick summary
        print("\n  QUICK PICK SUMMARY")
        print("-"*70)
        
        home_players = data.get("home_team", {}).get("players", [])
        away_players = data.get("away_team", {}).get("players", [])
        all_p = home_players + away_players
        
        if all_p:
            # Top overall
            top = max(all_p, key=lambda x: x.get("ev_points", 0))
            print(f"  Best PTS pick: {top.get('player_name')} - {top.get('ev_points', 0):.1f} points (Grade: {top.get('efficiency_grade', '?')})")
            
            top_reb = max(all_p, key=lambda x: x.get("ev_rebounds", 0))
            print(f"  Best REB pick: {top_reb.get('player_name')} - {top_reb.get('ev_rebounds', 0):.1f} rebounds")
            
            top_ast = max(all_p, key=lambda x: x.get("ev_assists", 0))
            print(f"  Best AST pick: {top_ast.get('player_name')} - {top_ast.get('ev_assists', 0):.1f} assists")
            
            # A-grade players only
            a_grades = [p for p in all_p if p.get("efficiency_grade") == "A"]
            print(f"\n  A-GRADE players in this matchup: {len(a_grades)}")
            for p in a_grades[:5]:
                print(f"    - {p.get('player_name')} ({p.get('ev_points', 0):.1f} pts)")
    else:
        print("Failed to get matchup data")


if __name__ == "__main__":
    main()
