"""
NBA Complete Data Fetcher - All Active Players
Uses stats.nba.com with VERY conservative rate limiting to avoid blocks
Saves progress to CSV continuously, resumes if interrupted
"""

import requests
import time
import random
import csv
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sys
sys.path.insert(0, str(Path(__file__).parent))
from core.config import CURRENT_SEASON

class NBACompleteFetcher:
    """Fetches all active NBA players with extremely conservative rate limiting"""
    
    BASE_URL = "https://stats.nba.com/stats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }
    
    # All 30 NBA Teams
    TEAMS = {
        1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
        1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
        1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
        1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
        1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
        1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
        1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
        1610612762: "UTA", 1610612764: "WAS"
    }
    
    def __init__(self, db_path: str, data_dir: str):
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        
        # VERY conservative rate limiting: 10-15 seconds between requests
        self.min_delay = 10.0
        self.max_delay = 15.0
        self.last_request_time = 0
        
        # Progress tracking
        self.progress_file = self.data_dir / "fetch_progress.json"
        self.csv_file = self.data_dir / "nba_all_players_2024_25.csv"
        self.completed_players = set()
        self.all_players = []
        self.errors = []
        
        self._load_progress()
    
    def _load_progress(self):
        """Load progress from previous run"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.completed_players = set(data.get('completed', []))
                    print(f"📂 Resuming: {len(self.completed_players)} players already fetched")
            except:
                pass
    
    def _save_progress(self):
        """Save progress for resume capability"""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'completed': list(self.completed_players),
                'last_update': datetime.now().isoformat(),
                'total_errors': len(self.errors)
            }, f, indent=2)
    
    def wait_with_jitter(self):
        """Wait with random jitter to appear more human-like"""
        base_wait = random.uniform(self.min_delay, self.max_delay)
        # Add occasional longer pauses
        if random.random() < 0.1:  # 10% chance of extra long pause
            base_wait += random.uniform(5, 15)
            print(f"    💤 Taking a longer break ({base_wait:.1f}s)...")
        else:
            print(f"    ⏳ Waiting {base_wait:.1f}s...")
        
        time.sleep(base_wait)
        self.last_request_time = time.time()
    
    def get_all_players(self) -> List[Dict]:
        """Fetch list of all current season players"""
        print(f"\n📋 Fetching player list for {CURRENT_SEASON} season...")
        
        url = f"{self.BASE_URL}/commonallplayers"
        params = {
            'LeagueID': '00',
            'Season': CURRENT_SEASON,
            'IsOnlyCurrentSeason': '1'
        }
        
        try:
            self.wait_with_jitter()
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            players = []
            for row in rows:
                player = dict(zip(headers, row))
                # Only active players with a team
                if player.get('ROSTERSTATUS') == 1:
                    team_id = player.get('TEAM_ID')
                    players.append({
                        'player_id': str(player.get('PERSON_ID', '')),
                        'name': player.get('DISPLAY_FIRST_LAST', ''),
                        'team_id': team_id,
                        'team': self.TEAMS.get(team_id, 'UNK'),
                    })
            
            print(f"   ✅ Found {len(players)} active players")
            return players
        except Exception as e:
            print(f"   ❌ Error fetching player list: {e}")
            self.errors.append(f"Player list: {e}")
            return []
    
    def get_player_stats(self, player_id: str, player_name: str) -> Optional[Dict]:
        """Fetch stats for a single player"""
        url = f"{self.BASE_URL}/playercareerstats"
        params = {
            'PlayerID': player_id,
            'PerMode': 'PerGame'
        }
        
        try:
            self.wait_with_jitter()
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
            
            # Find 2024-25 season
            for row in rows:
                stats = dict(zip(headers, row))
                if stats.get('SEASON_ID') == CURRENT_SEASON:
                    return {
                        'games': stats.get('GP', 0),
                        'points_avg': round(float(stats.get('PTS', 0) or 0), 1),
                        'rebounds_avg': round(float(stats.get('REB', 0) or 0), 1),
                        'assists_avg': round(float(stats.get('AST', 0) or 0), 1),
                        'steals_avg': round(float(stats.get('STL', 0) or 0), 1),
                        'blocks_avg': round(float(stats.get('BLK', 0) or 0), 1),
                        'fg_pct': round(float(stats.get('FG_PCT', 0) or 0), 3),
                        'fg3_pct': round(float(stats.get('FG3_PCT', 0) or 0), 3),
                        'ft_pct': round(float(stats.get('FT_PCT', 0) or 0), 3),
                        'minutes': round(float(stats.get('MIN', 0) or 0), 1),
                    }
            
            return None
        except requests.exceptions.Timeout:
            print(f"   ⏰ Timeout - will retry later")
            self.errors.append(f"{player_name}: Timeout")
            return None
        except Exception as e:
            self.errors.append(f"{player_name}: {e}")
            return None
    
    def append_to_csv(self, player: Dict, stats: Dict):
        """Append a single player's data to CSV"""
        file_exists = self.csv_file.exists()
        
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            fieldnames = [
                'player_id', 'name', 'team', 'games', 'points_avg', 'rebounds_avg',
                'assists_avg', 'steals_avg', 'blocks_avg', 'fg_pct', 'fg3_pct',
                'ft_pct', 'minutes', 'updated_at'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            row = {
                'player_id': player['player_id'],
                'name': player['name'],
                'team': player['team'],
                **stats,
                'updated_at': datetime.now().isoformat()
            }
            writer.writerow(row)
    
    def update_database(self, player: Dict, stats: Dict):
        """Update database with player stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update players table
        cursor.execute("""
            INSERT OR REPLACE INTO players 
            (player_id, name, team_id, status)
            VALUES (?, ?, ?, 'active')
        """, (
            player['player_id'],
            player['name'],
            player['team']
        ))
        
        # Update stats table
        cursor.execute("""
            INSERT OR REPLACE INTO player_stats 
            (player_id, season, games, points_avg, rebounds_avg, assists_avg, 
             fg_pct, three_p_pct, ft_pct)
            VALUES (?, CURRENT_SEASON, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player['player_id'],
            stats['games'],
            stats['points_avg'],
            stats['rebounds_avg'],
            stats['assists_avg'],
            stats['fg_pct'],
            stats['fg3_pct'],
            stats['ft_pct']
        ))
        
        conn.commit()
        conn.close()
    
    def fetch_all(self):
        """Main entry point: fetch all players with stats"""
        print("\n" + "="*70)
        print("🏀 NBA COMPLETE DATA FETCHER")
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️  Rate limit: {self.min_delay}-{self.max_delay}s between requests")
        print("="*70)
        
        # Get all players
        players = self.get_all_players()
        if not players:
            print("❌ Failed to get player list. Exiting.")
            return
        
        # Filter out already completed
        remaining = [p for p in players if p['player_id'] not in self.completed_players]
        print(f"\n📊 {len(remaining)} players remaining to fetch")
        
        if len(remaining) == 0:
            print("✅ All players already fetched!")
            return
        
        # Estimate time
        avg_wait = (self.min_delay + self.max_delay) / 2
        estimated_minutes = (len(remaining) * avg_wait) / 60
        print(f"⏰ Estimated time: ~{estimated_minutes:.0f} minutes")
        print("\n" + "-"*70)
        
        # Fetch each player
        success_count = 0
        for i, player in enumerate(remaining):
            player_id = player['player_id']
            player_name = player['name']
            
            print(f"[{i+1}/{len(remaining)}] {player_name} ({player['team']})...", end=" ")
            
            stats = self.get_player_stats(player_id, player_name)
            
            if stats and stats['games'] > 0:
                print(f"✅ {stats['points_avg']} PPG, {stats['rebounds_avg']} RPG, {stats['assists_avg']} APG")
                self.append_to_csv(player, stats)
                self.update_database(player, stats)
                success_count += 1
            elif stats:
                print("⚠️ No games played yet")
            else:
                print(f"❌ No {CURRENT_SEASON} data")
            
            # Mark as completed
            self.completed_players.add(player_id)
            
            # Save progress every 10 players
            if (i + 1) % 10 == 0:
                self._save_progress()
                print(f"    💾 Progress saved ({len(self.completed_players)} total)")
        
        # Final save
        self._save_progress()
        
        # Summary
        print("\n" + "="*70)
        print("📊 SUMMARY")
        print(f"   Total players processed: {len(remaining)}")
        print(f"   Successfully fetched: {success_count}")
        print(f"   Errors: {len(self.errors)}")
        print(f"   CSV file: {self.csv_file}")
        print(f"   Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    data_dir = script_dir / 'data' / 'fetched'
    
    print(f"📁 Database: {db_path}")
    print(f"📁 Output dir: {data_dir}")
    
    fetcher = NBACompleteFetcher(str(db_path), str(data_dir))
    fetcher.fetch_all()
    
    print("\n✅ Complete!")
