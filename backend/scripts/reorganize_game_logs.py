"""
Game Log Reorganization Script
Reads existing game_logs from Firestore and organizes them hierarchically:
- Groups players by game_id (same matchup)
- Identifies home vs away teams
- Creates proper matchups/{date}/games/{game_id}/players/{player_id} structure
- Works with already saved data - NO API CALLS
"""
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from firestore_db import get_firestore_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GameLogReorganizer:
    """
    Reorganizes flat game_logs collection into hierarchical matchup structure.
    """
    
    def __init__(self):
        self.db = get_firestore_db()
        logger.info("Firestore connected")
        
        # Stats
        self.games_processed = 0
        self.matchups_created = 0
        self.players_organized = 0
    
    def fetch_all_game_logs(self, limit=None) -> List[Dict]:
        """Fetch all game logs from Firestore"""
        logger.info("Fetching game logs from Firestore...")
        
        collection = self.db.collection('game_logs')
        
        # Don't use orderBy - old data may not have consistent game_date field
        if limit:
            query = collection.limit(limit)
        else:
            query = collection
        
        docs = query.stream()
        
        logs = []
        for doc in docs:
            data = doc.to_dict()
            data['doc_id'] = doc.id
            logs.append(data)
        
        logger.info(f"Fetched {len(logs)} game logs")
        return logs
    
    def group_by_matchup(self, logs: List[Dict]) -> Dict[str, Dict]:
        """
        Group logs by game_id to find players in same matchup.
        Returns: {game_id: {date, matchup, home_team, away_team, players: [...]}}
        """
        logger.info("Grouping logs by matchup...")
        
        matchups = defaultdict(lambda: {
            'game_id': '',
            'date': '',
            'matchup': '',
            'home_team': '',
            'away_team': '',
            'teams': set(),
            'players': {
                'home': [],
                'away': [],
            }
        })
        
        for log in logs:
            game_id = log.get('game_id', '')
            if not game_id:
                continue
            
            matchup_raw = log.get('matchup', '')
            home_away = log.get('home_away', '')
            team = log.get('team', '')
            player_name = log.get('player_name', '')
            player_id = log.get('player_id', '')
            game_date = log.get('game_date', '')
            
            # Initialize matchup info
            if not matchups[game_id]['game_id']:
                matchups[game_id]['game_id'] = game_id
                matchups[game_id]['date'] = game_date
                matchups[game_id]['matchup'] = matchup_raw
            
            # Track teams
            matchups[game_id]['teams'].add(team)
            
            # Determine home/away
            is_home = home_away.lower() == 'home' or 'vs.' in matchup_raw
            
            # Parse home/away teams from matchup
            if 'vs.' in matchup_raw:
                parts = matchup_raw.split(' vs. ')
                if len(parts) == 2:
                    matchups[game_id]['home_team'] = parts[0].strip()
                    matchups[game_id]['away_team'] = parts[1].strip()
            elif '@' in matchup_raw:
                parts = matchup_raw.split(' @ ')
                if len(parts) == 2:
                    matchups[game_id]['away_team'] = parts[0].strip()
                    matchups[game_id]['home_team'] = parts[1].strip()
            
            # Add player to appropriate team
            player_summary = {
                'player_id': player_id,
                'player_name': player_name,
                'team': team,
                'game_date': game_date,
                # Core stats
                'minutes': log.get('minutes', 0),
                'points': log.get('points', 0),
                'rebounds': log.get('rebounds', 0),
                'assists': log.get('assists', 0),
                'steals': log.get('steals', 0),
                'blocks': log.get('blocks', 0),
                'turnovers': log.get('turnovers', 0),
                # Shooting
                'fg_made': log.get('fg_made', 0),
                'fg_attempted': log.get('fg_attempted', 0),
                'fg_pct': log.get('fg_pct', 0),
                'fg3_made': log.get('fg3_made', 0),
                'fg3_attempted': log.get('fg3_attempted', 0),
                'fg3_pct': log.get('fg3_pct', 0),
                'ft_made': log.get('ft_made', 0),
                'ft_attempted': log.get('ft_attempted', 0),
                'ft_pct': log.get('ft_pct', 0),
                # Advanced (if available)
                'plus_minus': log.get('plus_minus', 0),
                'ts_pct': log.get('ts_pct', 0),
                'efg_pct': log.get('efg_pct', 0),
                'result': log.get('result', ''),
                'opponent': log.get('opponent', ''),
                'home_away': home_away,
            }
            
            if is_home:
                matchups[game_id]['players']['home'].append(player_summary)
            else:
                matchups[game_id]['players']['away'].append(player_summary)
        
        # Convert sets to lists for JSON serialization
        for game_id, data in matchups.items():
            data['teams'] = list(data['teams'])
        
        logger.info(f"Found {len(matchups)} unique matchups")
        return dict(matchups)
    
    def save_hierarchical_structure(self, matchups: Dict[str, Dict]):
        """
        Save matchups to hierarchical Firestore structure:
        matchups/{date}/games/{game_id}
        """
        logger.info("Saving to hierarchical structure...")
        
        # Group by date first
        by_date = defaultdict(list)
        for game_id, data in matchups.items():
            date_raw = data.get('date', '')
            if not date_raw:
                continue
            
            # Normalize date format (handle "Nov 12, 2024" -> "2024-11-12")
            date_iso = None
            
            # Try common formats
            for fmt in ['%b %d, %Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                try:
                    parsed = datetime.strptime(date_raw, fmt)
                    date_iso = parsed.strftime('%Y-%m-%d')
                    break
                except:
                    continue
            
            if not date_iso:
                logger.debug(f"Could not parse date '{date_raw}', skipping game {game_id}")
                continue
            
            by_date[date_iso].append(data)
        
        logger.info(f"Found {len(by_date)} unique dates")
        
        for date, games in by_date.items():
            logger.info(f"\n--- Processing {date}: {len(games)} matchups ---")
            
            for game_data in games:
                game_id = game_data['game_id']
                matchup = game_data['matchup']
                home_team = game_data.get('home_team', '')
                away_team = game_data.get('away_team', '')
                
                # Save game document
                game_doc_ref = self.db.collection('matchups').document(date).collection('games').document(game_id)
                
                game_doc = {
                    'game_id': game_id,
                    'date': date,
                    'matchup': matchup,
                    'home_team': home_team,
                    'away_team': away_team,
                    'teams': game_data.get('teams', []),
                    'home_player_count': len(game_data['players']['home']),
                    'away_player_count': len(game_data['players']['away']),
                    'updated_at': datetime.now().isoformat(),
                }
                
                game_doc_ref.set(game_doc, merge=True)
                self.matchups_created += 1
                
                # Save home players
                for player in game_data['players']['home']:
                    player_id = player['player_id']
                    player_doc_ref = game_doc_ref.collection('players').document(player_id)
                    player['is_home'] = True
                    player_doc_ref.set(player, merge=True)
                    self.players_organized += 1
                
                # Save away players
                for player in game_data['players']['away']:
                    player_id = player['player_id']
                    player_doc_ref = game_doc_ref.collection('players').document(player_id)
                    player['is_home'] = False
                    player_doc_ref.set(player, merge=True)
                    self.players_organized += 1
                
                logger.info(f"  {matchup}: {len(game_data['players']['home'])} home, {len(game_data['players']['away'])} away")
                self.games_processed += 1
        
        logger.info(f"\nSaved {self.matchups_created} matchups, {self.players_organized} player records")
    
    def run(self, limit=None):
        """Main execution"""
        logger.info("="*60)
        logger.info("Game Log Reorganization Script")
        logger.info("Organizing existing data into hierarchical structure")
        logger.info("="*60)
        
        start_time = datetime.now()
        
        # Fetch all game logs
        logs = self.fetch_all_game_logs(limit=limit)
        
        if not logs:
            logger.error("No game logs found in Firestore")
            return
        
        # Group by matchup
        matchups = self.group_by_matchup(logs)
        
        # Save hierarchical structure
        self.save_hierarchical_structure(matchups)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("\n" + "="*60)
        logger.info("SUMMARY")
        logger.info(f"Logs processed: {len(logs)}")
        logger.info(f"Matchups created: {self.matchups_created}")
        logger.info(f"Players organized: {self.players_organized}")
        logger.info(f"Time: {elapsed:.1f}s")
        logger.info("="*60)


def main():
    parser = argparse.ArgumentParser(description="Reorganize game logs into hierarchical matchup structure")
    parser.add_argument('--limit', type=int, default=None, help='Limit number of logs to process')
    
    args = parser.parse_args()
    
    reorganizer = GameLogReorganizer()
    reorganizer.run(limit=args.limit)


if __name__ == '__main__':
    main()
