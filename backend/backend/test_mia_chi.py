"""
Test simulation for MIA @ CHI - game with 36 players having real game logs.
"""
import requests
import sqlite3
from pathlib import Path

BASE_URL = "http://localhost:5000"
DB_PATH = Path(__file__).parent / "data" / "nba_data.db"

def get_roster(team_abbr):
    """Get players with game logs for a team"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get players who have game logs
    cur.execute("""
        SELECT DISTINCT p.player_id, p.name, p.position
        FROM players p
        INNER JOIN player_game_logs pgl ON CAST(p.player_id AS TEXT) = CAST(pgl.player_id AS TEXT)
        WHERE p.team_id = ?
        ORDER BY p.name
        LIMIT 5
    """, (team_abbr,))
    
    players = [dict(row) for row in cur.fetchall()]
    conn.close()
    return players


def run_sim(player_id, opponent_id):
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
    print("REAL GAME TEST: MIA @ CHI")
    print("=" * 60)
    
    # Team IDs
    MIA_ID = "1610612748"
    CHI_ID = "1610612741"
    
    mia_roster = get_roster("MIA")
    chi_roster = get_roster("CHI")
    
    print(f"\nMIA: {len(mia_roster)} players with game logs")
    print(f"CHI: {len(chi_roster)} players with game logs")
    
    print("\n" + "-" * 60)
    print("MIAMI HEAT PROJECTIONS vs CHI:")
    print("-" * 60)
    
    for player in mia_roster:
        result = run_sim(player['player_id'], CHI_ID)
        if result:
            proj = result.get('projections', {})
            ev = proj.get('expected_value', {})
            floor = proj.get('floor', {})
            ceiling = proj.get('ceiling', {})
            
            print(f"\n{player['name']} ({player['position']})")
            print(f"  PTS: {floor.get('points', 0):.1f} / {ev.get('points', 0):.1f} / {ceiling.get('points', 0):.1f}")
            print(f"  REB: {floor.get('rebounds', 0):.1f} / {ev.get('rebounds', 0):.1f} / {ceiling.get('rebounds', 0):.1f}")
            print(f"  AST: {floor.get('assists', 0):.1f} / {ev.get('assists', 0):.1f} / {ceiling.get('assists', 0):.1f}")
    
    print("\n" + "-" * 60)
    print("CHICAGO BULLS PROJECTIONS vs MIA:")
    print("-" * 60)
    
    for player in chi_roster:
        result = run_sim(player['player_id'], MIA_ID)
        if result:
            proj = result.get('projections', {})
            ev = proj.get('expected_value', {})
            floor = proj.get('floor', {})
            ceiling = proj.get('ceiling', {})
            
            print(f"\n{player['name']} ({player['position']})")
            print(f"  PTS: {floor.get('points', 0):.1f} / {ev.get('points', 0):.1f} / {ceiling.get('points', 0):.1f}")
            print(f"  REB: {floor.get('rebounds', 0):.1f} / {ev.get('rebounds', 0):.1f} / {ceiling.get('rebounds', 0):.1f}")
            print(f"  AST: {floor.get('assists', 0):.1f} / {ev.get('assists', 0):.1f} / {ceiling.get('assists', 0):.1f}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
