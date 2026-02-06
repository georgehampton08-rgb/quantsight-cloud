"""
Test simulations for today's NBA games.
- Fetches today's schedule
- Gets players for each team
- Checks for injuries
- Runs simulations with play type data
- Uses smart rate limiting
"""
import time
import random
import requests
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core.config import CURRENT_SEASON

BASE_URL = "http://localhost:5000"
DB_PATH = Path(__file__).parent / "data" / "nba_data.db"

# Rate limiting settings
MIN_DELAY = 0.5  # Min delay between API calls
MAX_DELAY = 1.5  # Max delay between API calls
BATCH_SIZE = 5   # Process in batches
BATCH_DELAY = 3  # Delay between batches


class RateLimiter:
    """Smart rate limiter with exponential backoff"""
    
    def __init__(self):
        self.consecutive_errors = 0
        self.last_call = 0
        
    def wait(self):
        """Wait before next call"""
        now = time.time()
        elapsed = now - self.last_call
        
        # Base delay
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        
        # Exponential backoff on errors
        if self.consecutive_errors > 0:
            delay *= (2 ** self.consecutive_errors)
            delay = min(delay, 30)  # Cap at 30 seconds
        
        if elapsed < delay:
            time.sleep(delay - elapsed)
        
        self.last_call = time.time()
    
    def success(self):
        self.consecutive_errors = 0
    
    def error(self):
        self.consecutive_errors += 1


def get_todays_schedule() -> List[Dict]:
    """Get today's games directly from NBA API (like fetch_todays_players_logs.py)"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # NBA API Settings (must match working script)
    NBA_API_URL = "https://stats.nba.com/stats/scoreboardv2"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "Accept-Language": "en-US,en;q=0.9"
    }
    params = {
        "DayOffset": 0,
        "GameDate": today,
        "LeagueID": "00"
    }
    
    try:
        response = requests.get(NBA_API_URL, headers=HEADERS, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            result_sets = data.get('resultSets', [])
            
            # Find GameHeader result set
            for rs in result_sets:
                if rs.get('name') == 'GameHeader':
                    headers_list = rs.get('headers', [])
                    rows = rs.get('rowSet', [])
                    
                    games = []
                    for row in rows:
                        game_dict = dict(zip(headers_list, row))
                        games.append({
                            'game_id': game_dict.get('GAME_ID'),
                            'home_team_id': str(game_dict.get('HOME_TEAM_ID')),
                            'away_team_id': str(game_dict.get('VISITOR_TEAM_ID')),
                            'home_team': game_dict.get('HOME_TEAM_ABBREVIATION', 'HOME'),
                            'away_team': game_dict.get('VISITOR_TEAM_ABBREVIATION', 'AWAY'),
                            'game_time': game_dict.get('GAME_STATUS_TEXT', 'TBD')
                        })
                    return games
        else:
            print(f"⚠️ NBA API returned {response.status_code}")
    except Exception as e:
        print(f"⚠️ Error fetching schedule from NBA API: {e}")
    return []


def get_injuries() -> Dict[str, Dict]:
    """Get current injuries indexed by player name"""
    try:
        res = requests.get(f"{BASE_URL}/injuries/current", timeout=10)
        if res.ok:
            data = res.json()
            injuries = {}
            for inj in data.get("injuries", []):
                injuries[inj["player_name"].lower()] = inj
            return injuries
    except Exception as e:
        print(f"⚠️ Error fetching injuries: {e}")
    return {}


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


def get_team_roster(team_id: str) -> List[Dict]:
    """Get team roster (handles both numeric IDs and abbreviations)"""
    # Convert numeric ID to abbreviation if needed
    team_abbr = TEAM_ID_MAP.get(team_id, team_id)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_id, name, position
        FROM players
        WHERE team_id = ?
    """, (team_abbr,))
    
    players = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return players


def get_play_types(player_id: str, rate_limiter: RateLimiter) -> Optional[Dict]:
    """Fetch play type data for a player"""
    rate_limiter.wait()
    
    try:
        res = requests.get(f"{BASE_URL}/players/{player_id}/play-types", timeout=10)
        if res.ok:
            rate_limiter.success()
            return res.json()
    except:
        rate_limiter.error()
    
    return None


def run_simulation(player_id: str, opponent_id: str, rate_limiter: RateLimiter) -> Optional[Dict]:
    """Run Aegis simulation for a player"""
    rate_limiter.wait()
    
    try:
        res = requests.get(
            f"{BASE_URL}/aegis/simulate/{player_id}",
            params={"opponent_id": opponent_id},
            timeout=30
        )
        if res.ok:
            rate_limiter.success()
            return res.json()
    except Exception as e:
        print(f"    ⚠️ Simulation error: {e}")
        rate_limiter.error()
    
    return None


def main():
    print("=" * 70)
    print("📊 TODAY'S GAMES SIMULATION TEST")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Season: {CURRENT_SEASON}")
    print()
    
    rate_limiter = RateLimiter()
    
    # Get schedule
    print("🏀 Fetching today's schedule...")
    games = get_todays_schedule()
    
    if not games:
        print("   No games scheduled today")
        return
    
    print(f"   Found {len(games)} games")
    
    # Get injuries
    print("\n🚑 Fetching injury report...")
    injuries = get_injuries()
    print(f"   {len(injuries)} players on injury report")
    
    # Process each game
    results = []
    
    for i, game in enumerate(games):
        print(f"\n{'='*70}")
        print(f"GAME {i+1}: {game.get('away_team', 'AWAY')} @ {game.get('home_team', 'HOME')}")
        print(f"Time: {game.get('game_time', 'TBD')}")
        print("=" * 70)
        
        home_id = game.get("home_team_id", "")
        away_id = game.get("away_team_id", "")
        
        for team_id, opp_id, team_type in [(home_id, away_id, "HOME"), (away_id, home_id, "AWAY")]:
            print(f"\n--- {team_type} TEAM ---")
            
            roster = get_team_roster(team_id)
            print(f"Roster: {len(roster)} players")
            
            # Check for injured players
            active_players = []
            injured_players = []
            
            for player in roster:
                name_lower = player["name"].lower()
                if name_lower in injuries:
                    inj = injuries[name_lower]
                    injured_players.append(f"{player['name']} ({inj['status']})")
                else:
                    active_players.append(player)
            
            if injured_players:
                print(f"🚨 Injured: {', '.join(injured_players[:5])}")
                if len(injured_players) > 5:
                    print(f"   ...and {len(injured_players) - 5} more")
            
            # Simulate top players (limit to 5 per team for speed)
            print(f"\n🎯 Running simulations for top {min(5, len(active_players))} players...")
            
            for j, player in enumerate(active_players[:5]):
                player_id = str(player["player_id"])
                player_name = player["name"]
                
                print(f"\n  [{j+1}] {player_name}")
                
                # Get play types
                play_data = get_play_types(player_id, rate_limiter)
                if play_data and play_data.get("play_types"):
                    top_plays = play_data["play_types"][:3]
                    play_summary = ", ".join([
                        f"{p['play_type']}({p['ppp']:.2f})" 
                        for p in top_plays
                    ])
                    print(f"      📊 Play Types: {play_summary}")
                
                # Run simulation
                sim = run_simulation(player_id, opp_id, rate_limiter)
                
                if sim and sim.get("projections"):
                    proj = sim["projections"]
                    pts = proj.get("pts", {})
                    reb = proj.get("reb", {})
                    ast = proj.get("ast", {})
                    
                    print(f"      ✅ PTS: {pts.get('floor', 0):.1f}-{pts.get('ev', 0):.1f}-{pts.get('ceiling', 0):.1f}")
                    print(f"         REB: {reb.get('floor', 0):.1f}-{reb.get('ev', 0):.1f}-{reb.get('ceiling', 0):.1f}")
                    print(f"         AST: {ast.get('floor', 0):.1f}-{ast.get('ev', 0):.1f}-{ast.get('ceiling', 0):.1f}")
                    print(f"         Confidence: {sim.get('confidence', {}).get('grade', 'N/A')}")
                    
                    results.append({
                        "player": player_name,
                        "game": f"{game.get('away_team')} @ {game.get('home_team')}",
                        "pts_ev": pts.get("ev", 0),
                        "reb_ev": reb.get("ev", 0),
                        "ast_ev": ast.get("ev", 0),
                        "confidence": sim.get("confidence", {}).get("grade", "N/A")
                    })
                else:
                    print(f"      ⚠️ No simulation data")
                
                # Batch delay
                if (j + 1) % BATCH_SIZE == 0 and j < len(active_players) - 1:
                    print(f"      ⏳ Batch pause ({BATCH_DELAY}s)...")
                    time.sleep(BATCH_DELAY)
    
    # Summary
    print("\n" + "=" * 70)
    print("📈 SUMMARY")
    print("=" * 70)
    print(f"Total games: {len(games)}")
    print(f"Total simulations: {len(results)}")
    
    if results:
        # Top scoring projections
        top_scorers = sorted(results, key=lambda x: x["pts_ev"], reverse=True)[:5]
        print("\n🔥 Top Projected Scorers:")
        for r in top_scorers:
            print(f"   {r['player']:25} {r['pts_ev']:5.1f} pts  ({r['game']})")
        
        # Top assists
        top_assists = sorted(results, key=lambda x: x["ast_ev"], reverse=True)[:5]
        print("\n🎯 Top Projected Assists:")
        for r in top_assists:
            print(f"   {r['player']:25} {r['ast_ev']:5.1f} ast  ({r['game']})")
    
    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
