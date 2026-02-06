"""
NBA Data Loader Service
Extracts current season (2024-2025) data from tar.xz archives.
Historical seasons loaded on-demand.
"""

import os
import json
import tarfile
import lzma
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from core.config import CURRENT_SEASON

class NBADataLoader:
    def __init__(self, datasets_dir: str, output_db: str):
        self.datasets_dir = Path(datasets_dir)
        self.output_db = output_db
        self.conn = None
        
    def connect_db(self):
        """Create or connect to SQLite database"""
        self.conn = sqlite3.connect(self.output_db)
        self.create_tables()
        
    def create_tables(self):
        """Create database schema"""
        cursor = self.conn.cursor()
        
        # Players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                position TEXT,
                team_id TEXT,
                jersey_number TEXT,
                status TEXT DEFAULT 'active',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                abbreviation TEXT,
                conference TEXT,
                division TEXT
            )
        """)
        
        # Player stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                season TEXT,
                games INTEGER,
                points_avg REAL,
                rebounds_avg REAL,
                assists_avg REAL,
                fg_pct REAL,
                three_p_pct REAL,
                ft_pct REAL,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        """)
        
        # Injuries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS injuries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                player_name TEXT,
                team TEXT,
                status TEXT,
                injury_type TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        """)
        
        # Data freshness tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_freshness (
                entity_type TEXT PRIMARY KEY,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_stats_season ON player_stats(player_id, season)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id)")
        
        self.conn.commit()
        
    def seed_teams(self):
        """Seed all 30 NBA teams with conference/division structure"""
        cursor = self.conn.cursor()
        
        teams = [
            # Eastern Conference - Atlantic
            ('BOS', 'Boston Celtics', 'Eastern', 'Atlantic'),
            ('BKN', 'Brooklyn Nets', 'Eastern', 'Atlantic'),
            ('NYK', 'New York Knicks', 'Eastern', 'Atlantic'),
            ('PHI', 'Philadelphia 76ers', 'Eastern', 'Atlantic'),
            ('TOR', 'Toronto Raptors', 'Eastern', 'Atlantic'),
            
            # Eastern - Central
            ('CHI', 'Chicago Bulls', 'Eastern', 'Central'),
            ('CLE', 'Cleveland Cavaliers', 'Eastern', 'Central'),
            ('DET', 'Detroit Pistons', 'Eastern', 'Central'),
            ('IND', 'Indiana Pacers', 'Eastern', 'Central'),
            ('MIL', 'Milwaukee Bucks', 'Eastern', 'Central'),
            
            # Eastern - Southeast
            ('ATL', 'Atlanta Hawks', 'Eastern', 'Southeast'),
            ('CHA', 'Charlotte Hornets', 'Eastern', 'Southeast'),
            ('MIA', 'Miami Heat', 'Eastern', 'Southeast'),
            ('ORL', 'Orlando Magic', 'Eastern', 'Southeast'),
            ('WAS', 'Washington Wizards', 'Eastern', 'Southeast'),
            
            # Western - Northwest
            ('DEN', 'Denver Nuggets', 'Western', 'Northwest'),
            ('MIN', 'Minnesota Timberwolves', 'Western', 'Northwest'),
            ('OKC', 'Oklahoma City Thunder', 'Western', 'Northwest'),
            ('POR', 'Portland Trail Blazers', 'Western', 'Northwest'),
            ('UTA', 'Utah Jazz', 'Western', 'Northwest'),
            
            # Western - Pacific
            ('GSW', 'Golden State Warriors', 'Western', 'Pacific'),
            ('LAC', 'LA Clippers', 'Western', 'Pacific'),
            ('LAL', 'Los Angeles Lakers', 'Western', 'Pacific'),
            ('PHX', 'Phoenix Suns', 'Western', 'Pacific'),
            ('SAC', 'Sacramento Kings', 'Western', 'Pacific'),
            
            # Western - Southwest
            ('DAL', 'Dallas Mavericks', 'Western', 'Southwest'),
            ('HOU', 'Houston Rockets', 'Western', 'Southwest'),
            ('MEM', 'Memphis Grizzlies', 'Western', 'Southwest'),
            ('NOP', 'New Orleans Pelicans', 'Western', 'Southwest'),
            ('SAS', 'San Antonio Spurs', 'Western', 'Southwest'),
        ]
        
        for abbrev, name, conf, div in teams:
            cursor.execute("""
                INSERT OR REPLACE INTO teams (team_id, name, abbreviation, conference, division)
                VALUES (?, ?, ?, ?, ?)
            """, (abbrev, name, abbrev, conf, div))
        
        self.conn.commit()
        print(f"Seeded {len(teams)} NBA teams")
        
    def extract_current_season(self):
        """Extract 2024-2025 season data"""
        print("Looking for 2024-2025 season data...")
        
        # Priority: nbastatsv3_2025.tar.xz (most comprehensive)
        target_archive = self.datasets_dir / "nbastatsv3_2025.tar.xz"
        
        if not target_archive.exists():
            print(f"Primary archive not found: {target_archive}")
            # Fallback to 2024
            target_archive = self.datasets_dir / "nbastatsv3_2024.tar.xz"
            if not target_archive.exists():
                print(f"Fallback archive not found: {target_archive}")
                return False
        
        print(f"Extracting {target_archive.name}...")
        
        try:
            # Open tar.xz archive
            with tarfile.open(target_archive, 'r:xz') as tar:
                # Extract to temp directory
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    tar.extractall(tmpdir)
                    tmpdir_path = Path(tmpdir)
                    
                    # Find and parse CSVs
                    print("Parsing player data...")
                    self._parse_player_csvs(tmpdir_path)
                    
                    print("Parsing player stats...")
                    self._parse_stats_csvs(tmpdir_path)
                    
            return True
        except Exception as e:
            print(f"Extraction failed: {e}")
            return False
    
    def _parse_player_csvs(self, extract_dir: Path):
        """Parse player roster CSVs"""
        import csv
        
        # Look for common player files
        player_files = list(extract_dir.rglob("*player*.csv")) + list(extract_dir.rglob("*roster*.csv"))
        
        if not player_files:
            print("No player CSV files found")
            return
        
        cursor = self.conn.cursor()
        players_added = 0
        
        for csv_file in player_files[:1]:  # Use first file for now
            print(f"  Reading {csv_file.name}...")
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Try to extract player info (field names vary by dataset)
                        player_id = row.get('PLAYER_ID') or row.get('player_id') or row.get('id')
                        name = row.get('PLAYER_NAME') or row.get('player_name') or row.get('name')
                        team_id = row.get('TEAM_ABBREVIATION') or row.get('TEAM_ID') or row.get('team')
                        position = row.get('POSITION') or row.get('position') or row.get('pos')
                        jersey = row.get('JERSEY_NUMBER') or row.get('jersey') or row.get('num')
                        
                        if player_id and name:
                            cursor.execute("""
                                INSERT OR REPLACE INTO players 
                                (player_id, name, team_id, position, jersey_number, status)
                                VALUES (?, ?, ?, ?, ?, 'active')
                            """, (player_id, name, team_id, position, jersey))
                            players_added += 1
            except Exception as e:
                print(f"  ⚠️  Error parsing {csv_file.name}: {e}")
                continue
        
        self.conn.commit()
        print(f"Added {players_added} players")
    
    def _parse_stats_csvs(self, extract_dir: Path):
        """Parse player stats CSVs"""
        import csv
        
        # Look for stats files
        stats_files = list(extract_dir.rglob("*stats*.csv")) + list(extract_dir.rglob("*traditional*.csv"))
        
        if not stats_files:
            print("No stats CSV files found")
            return
        
        cursor = self.conn.cursor()
        stats_added = 0
        
        for csv_file in stats_files[:1]:  # Use first file
            print(f"  Reading {csv_file.name}...")
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Extract stats (field names vary)
                        player_id = row.get('PLAYER_ID') or row.get('player_id')
                        season = row.get('SEASON') or row.get('season') or CURRENT_SEASON
                        games = row.get('GP') or row.get('games') or row.get('G') or 0
                        ppg = row.get('PTS') or row.get('points') or row.get('PPG') or 0
                        rpg = row.get('REB') or row.get('rebounds') or row.get('RPG') or 0
                        apg = row.get('AST') or row.get('assists') or row.get('APG') or 0
                        fg_pct = row.get('FG_PCT') or row.get('fg_pct') or row.get('FG%') or 0
                        three_pct = row.get('FG3_PCT') or row.get('3P%') or 0
                        ft_pct = row.get('FT_PCT') or row.get('FT%') or 0
                        
                        if player_id:
                            cursor.execute("""
                                INSERT OR REPLACE INTO player_stats
                                (player_id, season, games, points_avg, rebounds_avg, assists_avg,
                                 fg_pct, three_p_pct, ft_pct)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (player_id, season, games, ppg, rpg, apg, fg_pct, three_pct, ft_pct))
                            stats_added += 1
            except Exception as e:
                print(f"  ⚠️  Error parsing {csv_file.name}: {e}")
                continue
        
        self.conn.commit()
        print(f"Added {stats_added} stat records")
        
    def load_data(self):
        """Main data loading pipeline"""
        print("Starting NBA Data Loader...")
        self.connect_db()
        
        # Check if data already loaded
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams")
        team_count = cursor.fetchone()[0]
        
        if team_count == 0:
            print("First run detected - seeding teams...")
            self.seed_teams()
        else:
            print(f"Database already initialized ({team_count} teams found)")
        
        # Check if players already loaded
        cursor.execute("SELECT COUNT(*) FROM players")
        player_count = cursor.fetchone()[0]
        
        if player_count == 0:
            print("Extracting player data from archives...")
            success = self.extract_current_season()
            if success:
                cursor.execute("SELECT COUNT(*) FROM players")
                player_count = cursor.fetchone()[0]
                print(f"Database now contains {player_count} players")
        else:
            print(f"Players already loaded ({player_count} found)")
        
        # Update freshness timestamp
        cursor.execute("""
            INSERT OR REPLACE INTO data_freshness (entity_type, last_updated)
            VALUES ('initial_load', ?)
        """, (datetime.now(),))
        self.conn.commit()
        
        print("Data loading complete!")
        print(f"Summary: {team_count} teams, {player_count} players")
        self.conn.close()

if __name__ == '__main__':
    # Run from backend directory
    current_dir = Path(__file__).parent.parent
    datasets_dir = current_dir.parent.parent / "nba_data" / "datasets"
    output_db = current_dir / "data" / "nba_data.db"
    
    # Ensure output directory exists
    output_db.parent.mkdir(parents=True, exist_ok=True)
    
    loader = NBADataLoader(
        datasets_dir=str(datasets_dir),
        output_db=str(output_db)
    )
    loader.load_data()
