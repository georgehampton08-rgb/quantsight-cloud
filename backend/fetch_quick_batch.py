"""
NBA Quick Batch Fetchers - All Single API Calls (Fast!)
These are batch endpoints that return lots of data in ONE call:
- League Leaders (PPG, RPG, APG, etc.)
- Team Standings
- Today's Schedule with scores
- League averages/benchmarks
"""

import requests
import time
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class NBAQuickFetcher:
    """Quick batch fetchers - no per-player loops!"""
    
    BASE_URL = "https://stats.nba.com/stats"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com',
    }
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.timeout = (15, 60)
        self._init_db()
    
    def _init_db(self):
        """Create tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # League leaders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS league_leaders (
                category TEXT,
                rank INTEGER,
                player_id TEXT,
                player_name TEXT,
                team TEXT,
                value REAL,
                updated_at TEXT,
                PRIMARY KEY (category, rank)
            )
        """)
        
        # Team standings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_standings (
                team_id TEXT PRIMARY KEY,
                team TEXT,
                conference TEXT,
                division TEXT,
                wins INTEGER,
                losses INTEGER,
                win_pct REAL,
                conf_rank INTEGER,
                home_record TEXT,
                away_record TEXT,
                last_10 TEXT,
                streak TEXT,
                updated_at TEXT
            )
        """)
        
        # Today's games
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS todays_games (
                game_id TEXT PRIMARY KEY,
                game_date TEXT,
                game_time TEXT,
                home_team TEXT,
                away_team TEXT,
                home_score INTEGER,
                away_score INTEGER,
                status TEXT,
                updated_at TEXT
            )
        """)
        
        # League benchmarks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS league_benchmarks (
                stat TEXT PRIMARY KEY,
                league_avg REAL,
                top_10_avg REAL,
                elite_threshold REAL,
                updated_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def make_request(self, url: str, params: dict) -> Optional[dict]:
        """Make request"""
        try:
            time.sleep(2)  # Small delay between batch calls
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None
    
    def fetch_league_leaders(self):
        """Fetch top players in each category - ONE API CALL"""
        print("\n🏆 Fetching league leaders...")
        
        categories = {
            'PTS': 'Points',
            'REB': 'Rebounds', 
            'AST': 'Assists',
            'STL': 'Steals',
            'BLK': 'Blocks',
            'FG_PCT': 'FG%',
            'FG3_PCT': '3P%',
        }
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        total = 0
        
        for stat, name in categories.items():
            data = self.make_request(f"{self.BASE_URL}/leagueleaders", {
                'LeagueID': '00',
                'PerMode': 'PerGame',
                'Scope': 'S',
                'Season': '2024-25',
                'SeasonType': 'Regular Season',
                'StatCategory': stat,
            })
            
            if not data:
                continue
            
            try:
                headers = data['resultSet']['headers']
                rows = data['resultSet']['rowData'][:10]  # Top 10
            except (KeyError, IndexError) as e:
                continue
            
            for i, row in enumerate(rows):
                player = dict(zip(headers, row))
                cursor.execute("""
                    INSERT OR REPLACE INTO league_leaders
                    (category, rank, player_id, player_name, team, value, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, i + 1,
                    str(player.get('PLAYER_ID', '')),
                    player.get('PLAYER', ''),
                    player.get('TEAM', ''),
                    float(player.get(stat, 0) or 0),
                    datetime.now().isoformat()
                ))
                total += 1
        
        conn.commit()
        conn.close()
        print(f"   ✅ Saved {total} league leader entries")
        return total
    
    def fetch_standings(self):
        """Fetch team standings - ONE API CALL"""
        print("\n📊 Fetching team standings...")
        
        data = self.make_request(f"{self.BASE_URL}/leaguestandingsv3", {
            'LeagueID': '00',
            'Season': '2024-25',
            'SeasonType': 'Regular Season',
        })
        
        if not data:
            return 0
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
        except (KeyError, IndexError) as e:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for row in rows:
            team = dict(zip(headers, row))
            cursor.execute("""
                INSERT OR REPLACE INTO team_standings
                (team_id, team, conference, division, wins, losses, win_pct,
                 conf_rank, home_record, away_record, last_10, streak, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(team.get('TeamID', '')),
                team.get('TeamName', ''),
                team.get('Conference', ''),
                team.get('Division', ''),
                int(team.get('WINS', 0) or 0),
                int(team.get('LOSSES', 0) or 0),
                float(team.get('WinPCT', 0) or 0),
                int(team.get('ConferenceGamesBack', 0) or 0),
                team.get('HOME', ''),
                team.get('ROAD', ''),
                team.get('L10', ''),
                team.get('CurrentStreak', ''),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
        print(f"   ✅ Saved {len(rows)} team standings")
        return len(rows)
    
    def fetch_todays_scoreboard(self):
        """Fetch today's games - ONE API CALL"""
        print("\n🗓️ Fetching today's scoreboard...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        data = self.make_request(f"{self.BASE_URL}/scoreboardv2", {
            'DayOffset': '0',
            'GameDate': today,
            'LeagueID': '00',
        })
        
        if not data:
            return 0
        
        try:
            headers = data['resultSets'][0]['headers']
            rows = data['resultSets'][0]['rowSet']
        except (KeyError, IndexError) as e:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear old games
        cursor.execute("DELETE FROM todays_games")
        
        for row in rows:
            game = dict(zip(headers, row))
            cursor.execute("""
                INSERT OR REPLACE INTO todays_games
                (game_id, game_date, game_time, home_team, away_team,
                 home_score, away_score, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game.get('GAME_ID', ''),
                today,
                game.get('GAME_STATUS_TEXT', ''),
                str(game.get('HOME_TEAM_ID', '')),
                str(game.get('VISITOR_TEAM_ID', '')),
                int(game.get('HOME_TEAM_SCORE', 0) or 0),
                int(game.get('VISITOR_TEAM_SCORE', 0) or 0),
                game.get('GAME_STATUS_TEXT', ''),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
        print(f"   ✅ Saved {len(rows)} games for today")
        return len(rows)
    
    def calculate_league_benchmarks(self):
        """Calculate league averages from player_stats"""
        print("\n📈 Calculating league benchmarks...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get benchmarks from player_stats
        try:
            cursor.execute("""
                SELECT 
                    AVG(points_avg) as avg_pts,
                    AVG(rebounds_avg) as avg_reb,
                    AVG(assists_avg) as avg_ast
                FROM player_stats
                WHERE season = '2024-25' AND points_avg > 0
            """)
            row = cursor.fetchone()
            
            if row:
                benchmarks = [
                    ('PPG', row[0] or 0, 25.0, 20.0),
                    ('RPG', row[1] or 0, 10.0, 8.0),
                    ('APG', row[2] or 0, 8.0, 6.0),
                ]
                
                for stat, avg, top10, elite in benchmarks:
                    cursor.execute("""
                        INSERT OR REPLACE INTO league_benchmarks
                        (stat, league_avg, top_10_avg, elite_threshold, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (stat, round(avg, 1), top10, elite, datetime.now().isoformat()))
                
                print(f"   ✅ Saved benchmarks: Avg PPG={row[0]:.1f}")
        except Exception as e:
            print(f"   ⚠️ Could not calculate: {e}")
        
        conn.commit()
        conn.close()
    
    def fetch_all(self):
        """Run all quick fetchers"""
        print("\n" + "="*60)
        print("⚡ NBA QUICK BATCH FETCHERS")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("   These are FAST single-call endpoints!")
        print("="*60)
        
        self.fetch_league_leaders()
        self.fetch_standings()
        self.fetch_todays_scoreboard()
        self.calculate_league_benchmarks()
        
        print("\n" + "="*60)
        print("✅ QUICK FETCHERS COMPLETE!")
        print("="*60)


if __name__ == '__main__':
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    
    fetcher = NBAQuickFetcher(str(db_path))
    fetcher.fetch_all()
