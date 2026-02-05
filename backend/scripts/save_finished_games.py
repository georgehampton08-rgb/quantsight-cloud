"""
Save Finished Games to Firestore
=================================
Uses the existing /live/games endpoint to find finished games,
then fetches detailed box scores and saves to Firestore.

Run: python -m scripts.save_finished_games [--date YYYY-MM-DD]
"""

import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import firebase_admin
from firebase_admin import credentials, firestore

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Endpoints
LIVE_GAMES_URL = "https://quantsight-cloud-nucvdwqo6q-uc.a.run.app/live/games"
BOXSCORE_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"


def init_firebase():
    """Initialize Firebase if not already done."""
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()


def fetch_live_games() -> List[Dict[str, Any]]:
    """Fetch current games from our Cloud Run endpoint."""
    try:
        response = requests.get(LIVE_GAMES_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('games', [])
    except Exception as e:
        logger.error(f"Failed to fetch live games: {e}")
        return []


def fetch_boxscore(game_id: str) -> Optional[Dict[str, Any]]:
    """Fetch box score for a specific game."""
    try:
        url = BOXSCORE_URL.format(game_id=game_id)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch boxscore for {game_id}: {e}")
        return None


def transform_to_game_log(game_meta: Dict, boxscore_data: Dict) -> Dict[str, Any]:
    """Transform NBA API data to our game log format."""
    game_id = game_meta['game_id']
    
    # Extract game date from game_id (first 8 characters: 0022YYNN -> need to parse differently)
    # Actually, use the metadata we already have
    game_date_str = game_id[:8] if len(game_id) >= 8 else "00000000"
    formatted_date = f"{game_date_str[:4]}-{game_date_str[4:6]}-{game_date_str[6:8]}"
    
    game_log = {
        'game_id': game_id,
        'date': formatted_date,
        'home_team': game_meta.get('home_team'),
        'away_team': game_meta.get('away_team'),
        'home_score': game_meta.get('home_score', 0),
        'away_score': game_meta.get('away_score', 0),
        'final_period': game_meta.get('period', 4),
        'status': 'FINAL',
        'saved_at': datetime.utcnow().isoformat(),
        'teams': {}
    }
    
    # Extract players from boxscore
    game_data = boxscore_data.get('game', {})
    home_team_data = game_data.get('homeTeam', {})
    away_team_data = game_data.get('awayTeam', {})
    
    for team_data, team_code in [(home_team_data, game_log['home_team']),  
                                   (away_team_data, game_log['away_team'])]:
        if team_code not in game_log['teams']:
            game_log['teams'][team_code] = {'players': {}}
        
        players = team_data.get('players', [])
        
        for player in players:
            player_id = str(player.get('personId'))
            stats_data = player.get('statistics', {})
            
            player_stats = {
                'player_id': player_id,
                'name': player.get('name', 'Unknown'),
                'team': team_code,
                'position': player.get('position', ''),
                'starter': player.get('starter') == '1',
                'stats': {
                    'min': stats_data.get('minutes', '0:00'),
                    'pts': stats_data.get('points', 0),
                    'fgm': stats_data.get('fieldGoalsMade', 0),
                    'fga': stats_data.get('fieldGoalsAttempted', 0),
                    'fg_pct': stats_data.get('fieldGoalsPercentage', 0),
                    'fg3m': stats_data.get('threePointersMade', 0),
                    'fg3a': stats_data.get('threePointersAttempted', 0),
                    'fg3_pct': stats_data.get('threePointersPercentage', 0),
                    'ftm': stats_data.get('freeThrowsMade', 0),
                    'fta': stats_data.get('freeThrowsAttempted', 0),
                    'ft_pct': stats_data.get('freeThrowsPercentage', 0),
                    'oreb': stats_data.get('reboundsOffensive', 0),
                    'dreb': stats_data.get('reboundsDefensive', 0),
                    'reb': stats_data.get('reboundsTotal', 0),
                    'ast': stats_data.get('assists', 0),
                    'stl': stats_data.get('steals', 0),
                    'blk': stats_data.get('blocks', 0),
                    'tov': stats_data.get('turnovers', 0),
                    'pf': stats_data.get('foulsPersonal', 0),
                    'plus_minus': stats_data.get('plusMinusPoints', 0)
                }
            }
            
            game_log['teams'][team_code]['players'][player_id] = player_stats
    
    return game_log


def main():
    """Main execution function."""
    logger.info("="*70)
    logger.info("FINISHED GAMES PERSISTENCE SCRIPT")
    logger.info("="*70)
    
    # Initialize Firestore
    logger.info("\n🔧 Initializing Firebase...")
    db = init_firebase()
    logger.info("✅ Firebase ready")
    
    # Fetch games from our endpoint
    logger.info(f"\n📊 Fetching games from /live/games endpoint...")
    games = fetch_live_games()
    
    if not games:
        logger.error("❌ No games found")
        return
    
    # Filter for finished games
    finished_games = [g for g in games if g.get('status') == 'FINAL']
    
    logger.info(f"✅ Found {len(finished_games)} finished games out of {len(games)} total")
    
    if not finished_games:
        logger.info("⚠️  No finished games to persist")
        return
    
    # Process each finished game
    saved_count = 0
    skipped_count = 0
    failed_count = 0
    total_players = 0
    
    for i, game_meta in enumerate(finished_games, 1):
        game_id = game_meta.get('game_id')
        home_team = game_meta.get('home_team', '???')
        away_team = game_meta.get('away_team', '???')
        home_score = game_meta.get('home_score', 0)
        away_score = game_meta.get('away_score', 0)
        
        logger.info(f"\n[{i}/{len(finished_games)}] Processing: {game_id}")
        logger.info(f"   {away_team} {away_score} @ {home_team} {home_score}")
        
        try:
            # Extract date from game_id (rough approximation for Firestore path)
            game_date = game_id[:8] if len(game_id) >= 8 else "00000000"
            formatted_date = f"{game_date[:4]}-{game_date[4:6]}-{game_date[6:8]}"
            
            # Check if already saved
            doc_ref = db.collection('game_logs').document(formatted_date).collection('games').document(game_id)
            existing = doc_ref.get()
            
            if existing.exists:
                logger.info(f"   ⏭️  Already saved, skipping")
                skipped_count += 1
                continue
            
            # Fetch box score
            logger.info(f"   🔍 Fetching box score...")
            boxscore_data = fetch_boxscore(game_id)
            
            if not boxscore_data:
                logger.warning(f"   ⚠️  No box score data available")
                failed_count += 1
                continue
            
            # Transform to game log format
            game_log = transform_to_game_log(game_meta, boxscore_data)
            
            # Count players
            player_count = sum(len(team['players']) for team in game_log['teams'].values())
            logger.info(f"   📋 Found {player_count} players")
            
            # Save to Firestore
            doc_ref.set(game_log)
            
            saved_count += 1
            total_players += player_count
            logger.info(f"   ✅ SAVED")
            
        except Exception as e:
            logger.error(f"   ❌ Failed: {e}", exc_info=True)
            failed_count += 1
            continue
    
    # Final summary
    logger.info("\n" + "="*70)
    logger.info("SUMMARY")
    logger.info("="*70)
    logger.info(f"Total finished games: {len(finished_games)}")
    logger.info(f"✅ Saved:    {saved_count} games ({total_players} players)")
    logger.info(f"⏭️  Skipped:  {skipped_count} games (already saved)")
    logger.info(f"❌ Failed:   {failed_count} games")
    logger.info("="*70)
    
    if saved_count > 0:
        logger.info(f"\n🎉 SUCCESS! Persisted {saved_count} game logs to Firestore")
    elif skipped_count > 0:
        logger.info(f"\n✅ All games already saved")
    else:
        logger.warning(f"\n⚠️  No games were saved")


if __name__ == "__main__":
    main()
