"""
Advanced NBA Analytics Engine
Calculates advanced metrics from play-type data
"""

import sqlite3
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List
from core.config import CURRENT_SEASON

class NBAAnalyticsEngine:
    """Advanced analytics calculations for NBA players"""
    
    def __init__(self, db_path: str = "quantsight_dashboard_v1/backend/data/nba_data.db"):
        self.db_path = db_path
    
    def calculate_advanced_stats(self, csv_file: str = "NBA_Play_Types_12_25.csv") -> Dict:
        """Calculate advanced analytics from play-type data"""
        
        print("="*70)
        print("ADVANCED ANALYTICS ENGINE")
        print("="*70)
        print()
        print("Analyzing play-type data...")
        
        csv_path = Path(csv_file)
        if not csv_path.exists():
            print(f"CSV file not found: {csv_file}")
            return {}
        
        # Player analytics storage
        player_analytics = defaultdict(lambda: {
            'name': None,
            'team': None,
            'total_poss': 0,
            'total_points': 0,
            'total_fga': 0,
            'total_fgm': 0,
            'play_type_efficiency': {},
            'usage_rate': 0.0,
            'true_shooting': 0.0,
            'effective_fg': 0.0
        })
        
        # Read CSV and aggregate
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                player_id = row.get('PLAYER_ID')
                if not player_id:
                    continue
                
                player_name = row.get('PLAYER_NAME')
                team = row.get('TEAM_ABB')
                play_type = row.get('PLAY_TYPE')
                
                try:
                    poss = int(row.get('POSS', 0) or 0)
                    pts = int(row.get('PTS', 0) or 0)
                    fga = int(row.get('FGA', 0) or 0)
                    fgm = int(row.get('FGM', 0) or 0)
                    freq = float(row.get('FREQ', 0) or 0)
                    
                    analytics = player_analytics[player_id]
                    analytics['name'] = player_name
                    analytics['team'] = team
                    analytics['total_poss'] += poss
                    analytics['total_points'] += pts
                    analytics['total_fga'] += fga
                    analytics['total_fgm'] += fgm
                    
                    # Track efficiency per play type
                    if play_type and poss > 0:
                        ppp = pts / poss  # Points per possession
                        analytics['play_type_efficiency'][play_type] = {
                            'ppp': round(ppp, 3),
                            'frequency': freq,
                            'possessions': poss
                        }
                    
                except (ValueError, TypeError, ZeroDivisionError):
                    continue
        
        print(f"Analyzed {len(player_analytics)} players")
        print()
        print("Calculating advanced metrics...")
        
        # Calculate advanced metrics
        for player_id, analytics in player_analytics.items():
            if analytics['total_poss'] > 0:
                # True Shooting %: PTS / (2 * (FGA + 0.44 * FTA))
                # For now, using simplified version without FTA
                fga = analytics['total_fga']
                if fga > 0:
                    analytics['true_shooting'] = round(
                        analytics['total_points'] / (2 * fga), 3
                    )
                
                # Effective FG%: (FGM + 0.5 * 3PM) / FGA
                # Simplified without 3PT data
                if analytics['total_fga'] > 0:
                    analytics['effective_fg'] = round(
                        analytics['total_fgm'] / analytics['total_fga'], 3
                    )
                
                # Usage Rate estimation from possessions
                analytics['usage_rate'] = round(
                    analytics['total_poss'] / 100.0, 2
                )
        
        return player_analytics
    
    def save_analytics_to_db(self, analytics: Dict) -> int:
        """Save advanced analytics to database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create analytics table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_analytics (
                player_id TEXT,
                season TEXT,
                true_shooting REAL,
                effective_fg REAL,
                usage_rate REAL,
                total_possessions INTEGER,
                best_play_type TEXT,
                best_play_type_ppp REAL,
                PRIMARY KEY (player_id, season)
            )
        """)
        
        saved = 0
        saved = 0
        season = CURRENT_SEASON
        
        for player_id, data in analytics.items():
            # Find best play type
            best_play = None
            best_ppp = 0
            
            for play_type, stats in data['play_type_efficiency'].items():
                if stats['possessions'] >= 10 and stats['ppp'] > best_ppp:
                    best_ppp = stats['ppp']
                    best_play = play_type
            
            cursor.execute("""
                INSERT OR REPLACE INTO player_analytics
                (player_id, season, true_shooting, effective_fg, usage_rate,
                 total_possessions, best_play_type, best_play_type_ppp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_id, season,
                data['true_shooting'],
                data['effective_fg'],
                data['usage_rate'],
                data['total_poss'],
                best_play,
                best_ppp
            ))
            saved += 1
        
        conn.commit()
        
        # Show top analytics
        cursor.execute("""
            SELECT p.name, pa.true_shooting, pa.effective_fg, pa.best_play_type, pa.best_play_type_ppp
            FROM player_analytics pa
            JOIN players p ON pa.player_id = p.player_id
            WHERE pa.season = ?
            ORDER BY pa.true_shooting DESC
            LIMIT 10
        """, (season,))
        
        top_players = cursor.fetchall()
        
        conn.close()
        
        print()
        print("="*70)
        print("ANALYTICS COMPLETE")
        print("="*70)
        print(f"Saved analytics for {saved} players")
        print()
        
        if top_players:
            print("Top 10 Most Efficient Players (True Shooting %):")
            print("-" * 70)
            for name, ts, efg, play_type, ppp in top_players:
                ts_pct = ts * 100
                efg_pct = efg * 100
                print(f"  {name:30} TS: {ts_pct:5.1f}%  eFG: {efg_pct:5.1f}%  Best: {play_type or 'N/A'}")
        
        print()
        print("="*70)
        
        return saved

def main():
    """Run advanced analytics calculation"""
    engine = NBAAnalyticsEngine()
    analytics = engine.calculate_advanced_stats()
    
    if analytics:
        engine.save_analytics_to_db(analytics)

if __name__ == '__main__':
    main()
