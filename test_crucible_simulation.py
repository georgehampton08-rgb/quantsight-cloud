"""
Crucible Full Simulation Test
=============================
Tests the complete simulation pipeline with REAL roster data from database.
"""
import sys
sys.path.insert(0, '.')
import sqlite3
from pathlib import Path
from engines.crucible_engine import CrucibleSimulator
from engines.usage_vacuum import get_usage_vacuum
from services.injury_manager import get_injury_manager


def get_real_roster(team_abbr: str) -> list:
    """Get real roster from database with all stats"""
    db = Path(__file__).parent / 'data' / 'nba_data.db'
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            pas.player_id,
            pas.player_name as name,
            pas.usg_pct as usage,
            pas.off_rating,
            pas.def_rating,
            pas.net_rating,
            pa.primary_archetype as archetype
        FROM player_advanced_stats pas
        LEFT JOIN player_archetypes pa ON pas.player_id = pa.player_id
        WHERE pas.team = ?
        ORDER BY pas.usg_pct DESC
        LIMIT 8
    """, (team_abbr.upper(),))
    
    players = []
    for row in cursor.fetchall():
        players.append({
            'player_id': str(row['player_id']),
            'name': row['name'] or 'Unknown',
            'archetype': row['archetype'] or 'Balanced',
            'usage': float(row['usage'] or 0.15),
            'fg2_pct': 0.50,  # Default, could pull from tracking
            'fg3_pct': 0.35,
        })
    
    conn.close()
    return players


def check_injuries(team_abbr: str, players: list) -> tuple:
    """Check injury report and filter roster"""
    manager = get_injury_manager()
    available, out = manager.filter_available_players(players)
    return available, out


def run_simulation():
    print("="*60)
    print("CRUCIBLE v4.0 - FULL SIMULATION TEST")
    print("="*60)
    
    # Get real rosters
    print("\n📋 Loading real rosters from database...")
    lakers = get_real_roster("LAL")
    warriors = get_real_roster("GSW")
    
    print(f"   LAL: {len(lakers)} players")
    for p in lakers[:5]:
        print(f"      {p['name']}: {p['usage']*100:.1f}% usage ({p['archetype']})")
    
    print(f"\n   GSW: {len(warriors)} players")
    for p in warriors[:5]:
        print(f"      {p['name']}: {p['usage']*100:.1f}% usage ({p['archetype']})")
    
    # Check injuries
    print("\n🏥 Checking injury report...")
    lal_available, lal_out = check_injuries("LAL", lakers)
    gsw_available, gsw_out = check_injuries("GSW", warriors)
    
    if lal_out:
        print(f"   LAL OUT: {[p['name'] for p in lal_out]}")
    else:
        print("   LAL: All players available")
    
    if gsw_out:
        print(f"   GSW OUT: {[p['name'] for p in gsw_out]}")
    else:
        print("   GSW: All players available")
    
    # Run simulation
    print("\n🎮 Running Crucible simulation...")
    sim = CrucibleSimulator(
        usage_vacuum=get_usage_vacuum(),
        verbose=True
    )
    
    result = sim.simulate_game(lal_available, gsw_available)
    
    # Results
    print(f"\n🏀 FINAL SCORE: LAL {result.final_score[0]} - GSW {result.final_score[1]}")
    print(f"⏱️ Execution: {result.execution_time_ms:.0f}ms")
    print(f"⚡ Friction events: {len(sim.friction_log)} DFG% adjustments")
    print(f"🔥 Was Clutch: {result.was_clutch}")
    print(f"💨 Was Blowout: {result.was_blowout}")
    
    # Top performers
    print("\n📊 TOP PERFORMERS:")
    all_stats = [
        (pid, stats, 'LAL') for pid, stats in result.home_team_stats.items()
    ] + [
        (pid, stats, 'GSW') for pid, stats in result.away_team_stats.items()
    ]
    
    for pid, stats, team in sorted(all_stats, key=lambda x: x[1]['points'], reverse=True)[:5]:
        print(f"   [{team}] {stats['name']}: {stats['points']}pts {stats['rebounds']}reb {stats['assists']}ast")
    
    # Friction samples
    if sim.friction_log:
        print("\n⚡ FRICTION SAMPLES (DFG% impact):")
        for f in sim.friction_log[:3]:
            print(f"   {f['shooter']} vs {f['defender']}: {f['original_fg']*100:.0f}% → {f['adjusted_fg']*100:.0f}%")


if __name__ == "__main__":
    run_simulation()
