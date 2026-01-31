"""
NBA Data Fetcher v2 - Uses BALLDONTLIE API for reliable, free NBA stats
Saves to CSV for backup and normalizes for SQL import
"""

import requests
import time
import random
import csv
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json

# BALLDONTLIE API - Free, no registration required for basic access
BALLDONTLIE_URL = "https://api.balldontlie.io/v1"

class NBADataFetcherV2:
    """Fetches current NBA stats with CSV backup and proper rate limiting"""
    
    def __init__(self, db_path: str, data_dir: str):
        self.db_path = db_path
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
            'Accept': 'application/json',
        })
        
        # Rate limiting: 10 requests/min to be safe
        self.request_count = 0
        self.last_request_time = 0
        self.min_delay = 6.0  # 6 seconds between requests (10/min)
        
        # Stats
        self.stats_fetched = 0
        self.errors = []
        self.all_players = []
        
    def rate_limit(self):
        """Enforce rate limiting with human-like variation"""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_delay:
            wait_time = self.min_delay - time_since_last + random.uniform(0.5, 2.0)
            print(f"    ⏳ Rate limit: waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
        self.last_request_time = time.time()
        self.request_count += 1
        
    def get_all_teams(self) -> List[Dict]:
        """Fetch all NBA teams"""
        print("📋 Fetching all NBA teams...")
        self.rate_limit()
        
        try:
            response = self.session.get(f"{BALLDONTLIE_URL}/teams", timeout=30)
            response.raise_for_status()
            data = response.json()
            
            teams = data.get('data', [])
            nba_teams = [t for t in teams if t.get('conference') in ['East', 'West']]
            print(f"   ✅ Found {len(nba_teams)} NBA teams")
            return nba_teams
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.errors.append(f"Teams: {e}")
            return []
    
    def get_players_page(self, page: int = 0, per_page: int = 100) -> tuple:
        """Fetch one page of players"""
        self.rate_limit()
        
        try:
            params = {
                'page': page,
                'per_page': per_page,
            }
            response = self.session.get(f"{BALLDONTLIE_URL}/players", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            players = data.get('data', [])
            meta = data.get('meta', {})
            return players, meta
        except Exception as e:
            print(f"   ❌ Error fetching page {page}: {e}")
            self.errors.append(f"Players page {page}: {e}")
            return [], {}
    
    def get_all_active_players(self) -> List[Dict]:
        """Fetch all active NBA players with pagination"""
        print("\n📋 Fetching all active players...")
        all_players = []
        page = 0
        
        while True:
            print(f"   Page {page}...", end=" ", flush=True)
            players, meta = self.get_players_page(page)
            
            if not players:
                break
                
            # Filter for active players (have a team) 
            active = [p for p in players if p.get('team') and p['team'].get('id')]
            all_players.extend(active)
            print(f"✅ {len(active)} active players")
            
            # Check for more pages
            next_page = meta.get('next_page')
            if not next_page:
                break
            page = next_page
            
            # Save progress periodically
            if len(all_players) % 300 == 0:
                self.save_progress(all_players)
        
        print(f"   📊 Total active players: {len(all_players)}")
        return all_players
    
    def get_player_season_averages(self, player_id: int, season: int = 2024) -> Optional[Dict]:
        """Fetch season averages for a player"""
        self.rate_limit()
        
        try:
            params = {
                'season': season,
                'player_ids[]': player_id
            }
            response = self.session.get(
                f"{BALLDONTLIE_URL}/season_averages",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            averages = data.get('data', [])
            if averages:
                return averages[0]
            return None
        except Exception as e:
            self.errors.append(f"Stats for {player_id}: {e}")
            return None
    
    def save_progress(self, players: List[Dict]):
        """Save current progress to CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = self.data_dir / f"nba_players_progress_{timestamp}.csv"
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if players:
                fieldnames = list(players[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for p in players:
                    # Flatten nested team dict
                    row = p.copy()
                    if 'team' in row and isinstance(row['team'], dict):
                        row['team_id'] = row['team'].get('id', '')
                        row['team_abbr'] = row['team'].get('abbreviation', '')
                        row['team_name'] = row['team'].get('full_name', '')
                        del row['team']
                    writer.writerow(row)
        
        print(f"   💾 Progress saved to {csv_path.name}")
    
    def save_to_csv(self, players: List[Dict]) -> str:
        """Save all players with stats to final CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = self.data_dir / f"nba_active_players_{timestamp}.csv"
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'player_id', 'first_name', 'last_name', 'position', 'height', 'weight',
                'team_id', 'team_abbr', 'team_name', 'team_city',
                'games_played', 'minutes_avg', 'points_avg', 'rebounds_avg', 'assists_avg',
                'steals_avg', 'blocks_avg', 'turnovers_avg', 
                'fg_pct', 'fg3_pct', 'ft_pct',
                'updated_at'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for p in players:
                stats = p.get('stats', {}) or {}
                team = p.get('team', {}) or {}
                row = {
                    'player_id': p.get('id', ''),
                    'first_name': p.get('first_name', ''),
                    'last_name': p.get('last_name', ''),
                    'position': p.get('position', ''),
                    'height': p.get('height', ''),
                    'weight': p.get('weight', ''),
                    'team_id': team.get('id', ''),
                    'team_abbr': team.get('abbreviation', ''),
                    'team_name': team.get('full_name', ''),
                    'team_city': team.get('city', ''),
                    'games_played': stats.get('games_played', 0),
                    'minutes_avg': stats.get('min', 0),
                    'points_avg': stats.get('pts', 0),
                    'rebounds_avg': stats.get('reb', 0),
                    'assists_avg': stats.get('ast', 0),
                    'steals_avg': stats.get('stl', 0),
                    'blocks_avg': stats.get('blk', 0),
                    'turnovers_avg': stats.get('turnover', 0),
                    'fg_pct': stats.get('fg_pct', 0),
                    'fg3_pct': stats.get('fg3_pct', 0),
                    'ft_pct': stats.get('ft_pct', 0),
                    'updated_at': datetime.now().isoformat()
                }
                writer.writerow(row)
        
        print(f"\n💾 Saved {len(players)} players to {csv_path}")
        return str(csv_path)
    
    def update_database(self, players: List[Dict]) -> int:
        """Update SQLite database with normalized data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updated = 0
        for p in players:
            stats = p.get('stats', {}) or {}
            team = p.get('team', {}) or {}
            
            if not stats.get('games_played'):
                continue  # Skip players without stats
            
            # Update players table
            cursor.execute("""
                INSERT OR REPLACE INTO players 
                (player_id, name, team_id, position, height, weight, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
            """, (
                str(p.get('id')),
                f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                team.get('abbreviation', ''),
                p.get('position', ''),
                p.get('height', ''),
                p.get('weight', ''),
            ))
            
            # Update player_stats table
            cursor.execute("""
                INSERT OR REPLACE INTO player_stats 
                (player_id, season, games, points_avg, rebounds_avg, assists_avg, 
                 fg_pct, three_p_pct, ft_pct, updated_at)
                VALUES (?, '2024-25', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(p.get('id')),
                stats.get('games_played', 0),
                stats.get('pts', 0),
                stats.get('reb', 0),
                stats.get('ast', 0),
                stats.get('fg_pct', 0),
                stats.get('fg3_pct', 0),
                stats.get('ft_pct', 0),
                datetime.now().isoformat()
            ))
            updated += 1
        
        conn.commit()
        conn.close()
        print(f"   ✅ Updated {updated} player records in database")
        return updated
    
    def fetch_all(self, fetch_stats: bool = True):
        """Main entry: fetch all teams, players, and optionally stats"""
        print("\n" + "="*60)
        print("🏀 NBA Data Fetcher v2 - BALLDONTLIE API")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Step 1: Get all active players
        players = self.get_all_active_players()
        
        if not players:
            print("❌ No players fetched. Exiting.")
            return
        
        # Step 2: Fetch stats for each player (optional)
        if fetch_stats:
            print(f"\n📊 Fetching season averages for {len(players)} players...")
            print("   (This will take time due to rate limiting)")
            
            for i, player in enumerate(players):
                player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
                print(f"   [{i+1}/{len(players)}] {player_name}...", end=" ", flush=True)
                
                stats = self.get_player_season_averages(player['id'], 2024)
                if stats:
                    player['stats'] = stats
                    print(f"✅ {stats.get('pts', 0):.1f} PPG")
                else:
                    print("⚠️ No stats")
                
                # Save progress every 50 players
                if (i + 1) % 50 == 0:
                    self.save_progress(players[:i+1])
        
        # Step 3: Save to CSV
        csv_path = self.save_to_csv(players)
        
        # Step 4: Update database
        print("\n📥 Updating database...")
        self.update_database(players)
        
        # Summary
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print(f"   Players processed: {len(players)}")
        print(f"   With stats: {len([p for p in players if p.get('stats')])}")
        print(f"   Errors: {len(self.errors)}")
        print(f"   CSV saved: {csv_path}")
        print("="*60)
        
        return players


if __name__ == '__main__':
    import os
    
    # Paths
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    data_dir = script_dir / 'data' / 'fetched'
    
    print(f"📁 Database: {db_path}")
    print(f"📁 Data dir: {data_dir}")
    
    fetcher = NBADataFetcherV2(str(db_path), str(data_dir))
    
    # Fetch all - set fetch_stats=False for quick player list only
    fetcher.fetch_all(fetch_stats=True)
    
    print("\n✅ Complete!")
