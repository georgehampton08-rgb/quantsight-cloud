"""
Crucible Builder v1.0
=====================
Builds player projection inputs for the Crucible Engine by:
1. Loading player stats from nba_complete_2024_25.csv
2. Loading game logs from database (last 15 games)
3. Computing rolling averages, variance, and archetype
4. Outputting Crucible-ready JSON for simulation

Run this after fetch_game_logs.py completes.
"""

import os
import sys
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import csv

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent / 'backend'))


@dataclass
class CruciblePlayer:
    """Player data formatted for Crucible Engine input"""
    player_id: str
    name: str
    team: str
    position: str
    archetype: str
    
    # Usage & efficiency
    usage: float
    fg2_pct: float
    fg3_pct: float
    ft_pct: float
    
    # Rolling averages (from last 15 games)
    pts_avg: float
    reb_avg: float
    ast_avg: float
    pts_variance: float
    
    # Advanced metrics
    ts_pct: float
    off_rating: float
    def_rating: float
    net_rating: float
    
    # Availability
    games_played: int
    availability_pct: float


def classify_archetype(row: Dict) -> str:
    """
    Classify player into archetype based on stats.
    
    Archetypes:
    - Scorer: High usage, high points
    - Playmaker: High assists, high assist%
    - Rim Protector: High blocks, high rebounds
    - Three-and-D: High 3PT%, low usage
    - Slasher: High 2PT%, moderate usage
    - Balanced: Default
    """
    usage = float(row.get('usage', 0.15))
    pts = float(row.get('points', 0) or row.get('points_avg', 0))
    ast = float(row.get('assists', 0) or row.get('assists_avg', 0))
    reb = float(row.get('rebounds', 0) or row.get('rebounds_avg', 0))
    fg3_pct = float(row.get('fg3_pct', 0))
    fg2_pct = float(row.get('fg_pct', 0.45))  # Approximate 2PT%
    blocks = float(row.get('blocks', 0))
    ast_pct = float(row.get('ast_pct', 0.1))
    
    # Scorer: High usage + high points
    if usage >= 0.25 and pts >= 20:
        return "Scorer"
    
    # Playmaker: High assists
    if ast >= 6 or ast_pct >= 0.25:
        return "Playmaker"
    
    # Rim Protector: High rebounds + blocks
    if reb >= 8 or blocks >= 1.2:
        return "Rim Protector"
    
    # Three-and-D: Good 3PT shooter with low usage
    if fg3_pct >= 0.36 and usage < 0.18:
        return "Three-and-D"
    
    # Slasher: High 2PT%
    if fg2_pct >= 0.52 and usage >= 0.16:
        return "Slasher"
    
    return "Balanced"


def load_player_stats(csv_path: str) -> Dict[str, Dict]:
    """Load player stats from CSV"""
    players = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                player_id = row.get('player_id', '')
                if player_id:
                    players[player_id] = row
        logger.info(f"📊 Loaded {len(players)} players from CSV")
    except Exception as e:
        logger.error(f"Failed to load CSV: {e}")
    return players


def load_game_logs(db_path: str) -> Dict[str, List[Dict]]:
    """Load game logs from SQLite database"""
    game_logs = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='game_logs'
        """)
        if not cursor.fetchone():
            logger.warning("⚠️  game_logs table not found")
            return game_logs
        
        cursor.execute("""
            SELECT * FROM game_logs 
            ORDER BY player_id, game_date DESC
        """)
        
        for row in cursor.fetchall():
            player_id = row['player_id']
            if player_id not in game_logs:
                game_logs[player_id] = []
            
            game_logs[player_id].append({
                'game_date': row['game_date'],
                'opponent': row['opponent'],
                'points': row['points'],
                'rebounds': row['rebounds'],
                'assists': row['assists'],
                'minutes': row['minutes'],
                'fg_pct': row.get('fg_pct', 0),
                'fg3_pct': row.get('fg3_pct', 0),
            })
        
        conn.close()
        logger.info(f"🎮 Loaded game logs for {len(game_logs)} players")
    except Exception as e:
        logger.warning(f"Failed to load game logs: {e}")
    return game_logs


def compute_variance(games: List[Dict], stat: str) -> float:
    """Compute variance for a stat from game logs"""
    if not games:
        return 0.0
    
    values = [float(g.get(stat, 0) or 0) for g in games]
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance


def build_crucible_player(
    player_id: str,
    stats: Dict,
    games: List[Dict] = None
) -> CruciblePlayer:
    """Build a CruciblePlayer from stats and game logs"""
    
    # Parse stats
    name = stats.get('name', 'Unknown')
    team = stats.get('team', 'XXX')
    position = stats.get('position', 'G')
    
    # Get averages from season stats or game logs
    pts_avg = float(stats.get('points', 0) or stats.get('points_avg', 0))
    reb_avg = float(stats.get('rebounds', 0) or stats.get('rebounds_avg', 0))
    ast_avg = float(stats.get('assists', 0) or stats.get('assists_avg', 0))
    
    # If we have game logs, use rolling averages
    pts_variance = 0.0
    if games and len(games) >= 5:
        pts_avg = sum(float(g.get('points', 0) or 0) for g in games[:15]) / min(len(games), 15)
        reb_avg = sum(float(g.get('rebounds', 0) or 0) for g in games[:15]) / min(len(games), 15)
        ast_avg = sum(float(g.get('assists', 0) or 0) for g in games[:15]) / min(len(games), 15)
        pts_variance = compute_variance(games[:15], 'points')
    
    # Shooting percentages
    fg_pct = float(stats.get('fg_pct', 0.45))
    fg3_pct = float(stats.get('fg3_pct', 0.33))
    ft_pct = float(stats.get('ft_pct', 0.75))
    
    # Estimate 2PT% from overall FG%
    # Rough approximation: 2PT% ≈ FG% + 0.05 (since 3PT% is usually lower)
    fg2_pct = min(fg_pct + 0.05, 0.70)
    
    # Usage and advanced metrics
    usage = float(stats.get('usage', 0.15))
    ts_pct = float(stats.get('ts_pct', 0.55))
    off_rating = float(stats.get('off_rating', 110))
    def_rating = float(stats.get('def_rating', 110))
    net_rating = float(stats.get('net_rating', 0))
    
    # Games and availability
    games_played = int(stats.get('games', 0))
    availability_pct = float(stats.get('availability_pct', 50)) / 100
    
    # Classify archetype
    archetype = classify_archetype(stats)
    
    return CruciblePlayer(
        player_id=player_id,
        name=name,
        team=team,
        position=position,
        archetype=archetype,
        usage=usage,
        fg2_pct=fg2_pct,
        fg3_pct=fg3_pct,
        ft_pct=ft_pct,
        pts_avg=pts_avg,
        reb_avg=reb_avg,
        ast_avg=ast_avg,
        pts_variance=pts_variance,
        ts_pct=ts_pct,
        off_rating=off_rating,
        def_rating=def_rating,
        net_rating=net_rating,
        games_played=games_played,
        availability_pct=availability_pct
    )


def build_team_roster(
    team_abbr: str,
    players: Dict[str, Dict],
    game_logs: Dict[str, List[Dict]]
) -> List[Dict]:
    """Build a team roster for Crucible simulation"""
    
    team_players = [
        (pid, stats) for pid, stats in players.items()
        if stats.get('team', '') == team_abbr
    ]
    
    # Sort by usage (highest first, these are starters)
    team_players.sort(
        key=lambda x: float(x[1].get('usage', 0) or 0),
        reverse=True
    )
    
    roster = []
    for player_id, stats in team_players[:10]:  # Top 10 by usage
        games = game_logs.get(player_id, [])
        crucible_player = build_crucible_player(player_id, stats, games)
        roster.append(asdict(crucible_player))
    
    return roster


def build_all_rosters(
    players: Dict[str, Dict],
    game_logs: Dict[str, List[Dict]]
) -> Dict[str, List[Dict]]:
    """Build rosters for all teams"""
    
    teams = set(p.get('team', '') for p in players.values() if p.get('team'))
    
    rosters = {}
    for team in sorted(teams):
        if len(team) == 3:  # Valid team abbreviation
            roster = build_team_roster(team, players, game_logs)
            if roster:
                rosters[team] = roster
                logger.info(f"  {team}: {len(roster)} players")
    
    return rosters


def main():
    """Build Crucible player data"""
    logger.info("=" * 60)
    logger.info(" 🔥 CRUCIBLE BUILDER v1.0")
    logger.info("=" * 60)
    
    # Paths - scripts directory is under quantsight_dashboard_v1
    # CSV is in backend/data/fetched
    backend_dir = script_dir.parent / 'backend'
    data_dir = backend_dir / 'data'
    fetched_dir = data_dir / 'fetched'
    csv_path = fetched_dir / 'nba_complete_2024_25.csv'
    db_path = data_dir / 'nba_data.db'
    output_path = data_dir / 'crucible_rosters.json'

    
    # Check paths
    if not csv_path.exists():
        logger.error(f"❌ CSV not found: {csv_path}")
        return
    
    # Load data
    players = load_player_stats(str(csv_path))
    game_logs = load_game_logs(str(db_path))
    
    if not players:
        logger.error("❌ No players loaded")
        return
    
    # Build rosters
    logger.info("\n🏀 Building team rosters...")
    rosters = build_all_rosters(players, game_logs)
    
    # Save output
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'total_players': len(players),
        'players_with_game_logs': len(game_logs),
        'teams': rosters
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"\n✅ Saved to {output_path}")
    logger.info(f"   Teams: {len(rosters)}")
    logger.info(f"   Players with game logs: {len(game_logs)}")
    
    # Show sample
    logger.info("\n📊 Sample roster (LAL):")
    if 'LAL' in rosters:
        for p in rosters['LAL'][:5]:
            logger.info(f"   {p['name']:20} {p['archetype']:15} {p['pts_avg']:.1f} pts")


if __name__ == '__main__':
    main()
