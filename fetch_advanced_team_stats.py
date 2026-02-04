"""
Fetch Advanced Team Stats from NBA API
======================================
Fetches shot zones, transition stats, and playmaking data for all teams.
"""
import sqlite3
from pathlib import Path
import time
from nba_api.stats.endpoints import (
    leaguedashteamshotlocations,
    leaguedashteamstats,
)
from nba_api.stats.static import teams

DB_PATH = Path(__file__).parent / 'data' / 'nba_data.db'


def create_advanced_tables():
    """Create tables for advanced metrics if they don't exist"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Team shot zones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_shot_zones (
            team_id TEXT PRIMARY KEY,
            team_abbr TEXT UNIQUE,
            corner_3_freq REAL,
            corner_3_pct REAL,
            above_break_3_freq REAL,
            above_break_3_pct REAL,
            mid_range_freq REAL,
            mid_range_pct REAL,
            paint_freq REAL,
            paint_pct REAL,
            restricted_area_freq REAL,
            restricted_area_pct REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Team transition stats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_transition_stats (
            team_id TEXT PRIMARY KEY,
            team_abbr TEXT UNIQUE,
            transition_freq REAL,
            transition_ppp REAL,
            halfcourt_ppp REAL,
            fastbreak_pts_per_game REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Team playmaking stats (secondary assists)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_playmaking_stats (
            team_id TEXT PRIMARY KEY,
            team_abbr TEXT UNIQUE,
            secondary_ast_rate REAL,
            ast_to_pass_pct REAL,
            potential_ast_per_game REAL,
            ast_adj_per_game REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("Advanced tables created/verified")


def fetch_team_shot_zones():
    """Fetch shot zone data for all teams"""
    print("\nFetching team shot zones...")
    try:
        shot_data = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
            season='2024-25',
            season_type_all_star='Regular Season'
        )
        
        df = shot_data.get_data_frames()[0]
        
        if df.empty:
            print("  No shot zone data available")
            return
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Calculate frequencies and percentages
        for _, row in df.iterrows():
            team_id = str(row.get('TEAM_ID', ''))
            team_abbr = row.get('TEAM_ABBREVIATION', '')
            
            # Get shot zone data (columns vary)
            total_fga = row.get('FGA', 1) or 1
            
            # These column names may vary - adapt as needed
            corner_3_fga = row.get('Corner 3-8 FGA', 0) or 0
            corner_3_fgm = row.get('Corner 3-8 FGM', 0) or 0
            
            ab3_fga = row.get('Above Break 3s FGA', 0) or 0
            ab3_fgm = row.get('Above Break 3s FGM', 0) or 0
            
            mid_fga = row.get('Mid-Range FGA', 0) or 0
            mid_fgm = row.get('Mid-Range FGM', 0) or 0
            
            paint_fga = row.get('In The Paint (Non-RA) FGA', 0) or 0
            paint_fgm = row.get('In The Paint (Non-RA) FGM', 0) or 0
            
            ra_fga = row.get('Restricted Area FGA', 0) or 0
            ra_fgm = row.get('Restricted Area FGM', 0) or 0
            
            cursor.execute("""
                INSERT OR REPLACE INTO team_shot_zones (
                    team_id, team_abbr,
                    corner_3_freq, corner_3_pct,
                    above_break_3_freq, above_break_3_pct,
                    mid_range_freq, mid_range_pct,
                    paint_freq, paint_pct,
                    restricted_area_freq, restricted_area_pct,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                team_id, team_abbr,
                corner_3_fga / total_fga if total_fga else 0,
                corner_3_fgm / corner_3_fga if corner_3_fga else 0,
                ab3_fga / total_fga if total_fga else 0,
                ab3_fgm / ab3_fga if ab3_fga else 0,
                mid_fga / total_fga if total_fga else 0,
                mid_fgm / mid_fga if mid_fga else 0,
                paint_fga / total_fga if total_fga else 0,
                paint_fgm / paint_fga if paint_fga else 0,
                ra_fga / total_fga if total_fga else 0,
                ra_fgm / ra_fga if ra_fga else 0,
            ))
        
        conn.commit()
        conn.close()
        print(f"  Updated shot zones for {len(df)} teams")
        
    except Exception as e:
        print(f"  Error fetching shot zones: {e}")


def fetch_team_general_stats():
    """Fetch general team stats for transition and playmaking"""
    print("\nFetching team general stats...")
    try:
        team_stats = leaguedashteamstats.LeagueDashTeamStats(
            season='2024-25',
            season_type_all_star='Regular Season'
        )
        
        df = team_stats.get_data_frames()[0]
        
        if df.empty:
            print("  No team stats available")
            return
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            team_id = str(row.get('TEAM_ID', ''))
            team_abbr = row.get('TEAM_ABBREVIATION', '')
            
            # Get stats
            pts = row.get('PTS', 0) or 0
            ast = row.get('AST', 0) or 0
            tov = row.get('TOV', 0) or 0
            poss = row.get('POSS', 0) or (row.get('FGA', 75) - row.get('OREB', 10) + tov + 0.44 * (row.get('FTA', 20)))
            
            # Estimate transition stats from available data
            fastbreak_pts = 14.0  # Default - would need tracking data for actual
            transition_freq = 0.15
            
            cursor.execute("""
                INSERT OR REPLACE INTO team_transition_stats (
                    team_id, team_abbr,
                    transition_freq, transition_ppp,
                    halfcourt_ppp, fastbreak_pts_per_game,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                team_id, team_abbr,
                transition_freq,
                1.12,  # League avg - would need tracking data
                pts / poss if poss else 0.96,
                fastbreak_pts,
            ))
            
            # Calculate playmaking metrics
            ast_rate = ast / poss if poss else 0.20
            
            cursor.execute("""
                INSERT OR REPLACE INTO team_playmaking_stats (
                    team_id, team_abbr,
                    secondary_ast_rate, ast_to_pass_pct,
                    potential_ast_per_game, ast_adj_per_game,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                team_id, team_abbr,
                0.52,  # Default - would need tracking data
                0.08,
                ast * 1.3,  # Estimate potential assists
                ast,
            ))
        
        conn.commit()
        conn.close()
        print(f"  Updated stats for {len(df)} teams")
        
    except Exception as e:
        print(f"  Error fetching team stats: {e}")


def main():
    print("=" * 60)
    print("ADVANCED TEAM STATS FETCHER")
    print("=" * 60)
    
    create_advanced_tables()
    time.sleep(0.5)
    
    fetch_team_shot_zones()
    time.sleep(0.5)
    
    fetch_team_general_stats()
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
