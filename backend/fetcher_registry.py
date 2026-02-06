"""
NBA Data Fetcher Registry & Smart Scheduler v2
Optimized schedules to minimize API usage while keeping data fresh.

SCHEDULE PHILOSOPHY:
- Scoreboard: Only during game hours (3pm-1am ET), every 30 min
- Standings/Leaders: Once daily after games complete (~2am)
- Player stats: Once daily 
- Game logs: Once daily overnight (slow but comprehensive)

FEATURES:
- Staleness detection (data age warnings)
- Force refresh capability
- Game-day aware scheduling
- API usage tracking
"""

import subprocess
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

# ============================================================================
# OPTIMIZED FETCHER REGISTRY
# ============================================================================

FETCHER_REGISTRY = {
    # REAL-TIME: Only during games (3pm-1am ET)
    "scoreboard": {
        "script": "fetch_quick_batch.py",
        "description": "Today's scoreboard only (live scores)",
        "schedule": "game_hours_only",  # 3pm-1am, every 30 min
        "api_calls": 1,
        "staleness_threshold_minutes": 60,  # Warn if >1 hour old during games
        "priority": 1,
        "tables_updated": ["todays_games"],
        "run_on_startup": True,
    },
    
    # DAILY: Run once after games complete (~2am or on first startup)
    "standings": {
        "script": "fetch_quick_batch.py",  # Uses specific method
        "description": "Team standings with records",
        "schedule": "twice_daily",  # 2am after games + 10am for morning freshness
        "api_calls": 1,
        "staleness_threshold_minutes": 720,  # 12 hours - catch if missed
        "priority": 2,
        "tables_updated": ["team_standings"],
        "run_on_startup": True,
    },
    
    "league_leaders": {
        "script": "fetch_quick_batch.py",
        "description": "Top 10 in each stat category",
        "schedule": "daily_2am",
        "api_calls": 7,  # One per category
        "staleness_threshold_minutes": 1440,
        "priority": 3,
        "tables_updated": ["league_leaders"],
        "run_on_startup": True,
    },
    
    "team_defense": {
        "script": "fetch_team_defense.py",
        "description": "Team defensive ratings + matchup history",
        "schedule": "daily_2am",
        "api_calls": 2,
        "staleness_threshold_minutes": 1440,
        "priority": 4,
        "tables_updated": ["team_defense", "player_vs_team"],
        "run_on_startup": True,
    },
    
    "advanced_stats": {
        "script": "fetch_advanced_stats.py",
        "description": "TS%, usage, PIE for all players (batch)",
        "schedule": "daily_3am",
        "api_calls": 2,
        "staleness_threshold_minutes": 1440,
        "priority": 5,
        "tables_updated": ["player_stats", "player_advanced_stats"],
        "run_on_startup": False,  # Takes ~1 min, don't block startup
    },
    
    # GAME DAY ONLY: Only when there are games involving these players
    "todays_players": {
        "script": "fetch_todays_games.py",
        "description": "Game logs for players in today's games",
        "schedule": "game_day_morning",  # 10am on game days
        "api_calls": "~350",
        "staleness_threshold_minutes": 720,  # 12 hours
        "priority": 6,
        "tables_updated": ["player_game_logs", "player_bio", "player_rolling_averages"],
        "run_on_startup": False,
    },
    
    # OVERNIGHT ONLY: Full league refresh
    "all_game_logs": {
        "script": "fetch_gamelogs_smart.py",
        "description": "All 569 players (comprehensive)",
        "schedule": "weekly_sunday_3am",  # Weekly is enough
        "api_calls": "~1100",
        "staleness_threshold_minutes": 10080,  # 7 days
        "priority": 7,
        "tables_updated": ["player_game_logs", "player_bio"],
        "run_on_startup": False,
    },
}

# API USAGE SUMMARY:
# - Daily: ~15 API calls (standings + leaders + defense + advanced)
# - Game days: +350 calls (today's players)
# - Weekly: +1100 calls (full refresh)
# - Total weekly estimate: ~500 calls (vs unlimited if running constantly)


class SmartScheduler:
    """Intelligent scheduler with staleness detection"""
    
    def __init__(self, db_path: str, scripts_dir: str):
        self.db_path = db_path
        self.scripts_dir = Path(scripts_dir)
        self._init_db()
    
    def _init_db(self):
        """Create tracking tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_freshness (
                table_name TEXT PRIMARY KEY,
                last_updated TEXT,
                record_count INTEGER,
                source_fetcher TEXT,
                is_stale INTEGER DEFAULT 0,
                staleness_minutes INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetcher_runs (
                fetcher_id TEXT PRIMARY KEY,
                last_run TEXT,
                last_status TEXT,
                records_updated INTEGER,
                run_time_seconds REAL,
                next_scheduled TEXT,
                error_message TEXT,
                api_calls_used INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetcher_registry (
                fetcher_id TEXT PRIMARY KEY,
                script TEXT,
                description TEXT,
                schedule TEXT,
                priority INTEGER,
                tables_json TEXT,
                staleness_threshold INTEGER,
                is_enabled INTEGER DEFAULT 1
            )
        """)
        
        # Populate registry
        for fid, info in FETCHER_REGISTRY.items():
            cursor.execute("""
                INSERT OR REPLACE INTO fetcher_registry
                (fetcher_id, script, description, schedule, priority, 
                 tables_json, staleness_threshold, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                fid, info['script'], info['description'],
                info['schedule'], info['priority'],
                json.dumps(info['tables_updated']),
                info['staleness_threshold_minutes']
            ))
        
        conn.commit()
        conn.close()
        print(f"📋 Registered {len(FETCHER_REGISTRY)} fetchers (optimized)")
    
    def is_game_hours(self) -> bool:
        """Check if currently during NBA game hours (3pm-1am ET)"""
        now = datetime.now()
        hour = now.hour
        # Games typically 7pm-11pm, but account for West Coast (late)
        return 15 <= hour or hour < 1
    
    def is_game_day(self) -> bool:
        """Check if there are games today"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM todays_games WHERE game_date = ?
        """, (today,))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def get_data_freshness(self) -> List[Dict]:
        """Get freshness status of all data tables"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check each table's last update
        tables_to_check = [
            ('player_bio', 'updated_at'),
            ('player_game_logs', 'fetched_at'),
            ('player_rolling_averages', 'updated_at'),
            ('team_defense', 'updated_at'),
            ('team_standings', 'updated_at'),
            ('league_leaders', 'updated_at'),
            ('todays_games', 'updated_at'),
        ]
        
        freshness = []
        now = datetime.now()
        
        for table, date_col in tables_to_check:
            try:
                cursor.execute(f"""
                    SELECT MAX({date_col}) as last_update, COUNT(*) as count
                    FROM {table}
                """)
                row = cursor.fetchone()
                
                if row and row['last_update']:
                    last_update = datetime.fromisoformat(row['last_update'])
                    age_minutes = (now - last_update).total_seconds() / 60
                    
                    # Find staleness threshold for this table
                    threshold = 1440  # Default 24 hours
                    for fid, info in FETCHER_REGISTRY.items():
                        if table in info['tables_updated']:
                            threshold = info['staleness_threshold_minutes']
                            break
                    
                    freshness.append({
                        'table': table,
                        'last_update': row['last_update'],
                        'age_minutes': round(age_minutes),
                        'record_count': row['count'],
                        'is_stale': age_minutes > threshold,
                        'threshold_minutes': threshold,
                    })
                else:
                    freshness.append({
                        'table': table,
                        'last_update': None,
                        'age_minutes': None,
                        'record_count': 0,
                        'is_stale': True,
                        'threshold_minutes': 1440,
                    })
            except Exception as e:
                freshness.append({
                    'table': table,
                    'error': str(e),
                    'is_stale': True,
                })
        
        conn.close()
        return freshness
    
    def get_stale_fetchers(self) -> List[str]:
        """Get fetchers whose data is stale"""
        freshness = self.get_data_freshness()
        stale_tables = {f['table'] for f in freshness if f.get('is_stale')}
        
        stale_fetchers = []
        for fid, info in FETCHER_REGISTRY.items():
            tables = set(info['tables_updated'])
            if tables & stale_tables:
                stale_fetchers.append(fid)
        
        return stale_fetchers
    
    def force_refresh(self, fetcher_id: str) -> Dict:
        """Force refresh a specific fetcher (bypass schedule)"""
        if fetcher_id not in FETCHER_REGISTRY:
            return {"error": f"Unknown fetcher: {fetcher_id}"}
        
        info = FETCHER_REGISTRY[fetcher_id]
        script_path = self.scripts_dir / info['script']
        
        print(f"\n� FORCE REFRESH: {fetcher_id}")
        
        start = datetime.now()
        try:
            result = subprocess.run(
                ['python', str(script_path)],
                capture_output=True,
                text=True,
                timeout=7200,
                cwd=str(self.scripts_dir)
            )
            
            duration = (datetime.now() - start).total_seconds()
            status = "success" if result.returncode == 0 else "failed"
            
            # Update run history
            self._update_run(fetcher_id, status, duration)
            
            return {
                "fetcher": fetcher_id,
                "status": status,
                "duration_seconds": round(duration, 1),
                "forced": True,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _update_run(self, fetcher_id: str, status: str, duration: float):
        """Update run history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now()
        
        cursor.execute("""
            INSERT OR REPLACE INTO fetcher_runs
            (fetcher_id, last_run, last_status, run_time_seconds, next_scheduled)
            VALUES (?, ?, ?, ?, ?)
        """, (
            fetcher_id, now.isoformat(), status, duration,
            self._calculate_next_run(fetcher_id, now).isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def _calculate_next_run(self, fetcher_id: str, from_time: datetime) -> datetime:
        """Calculate next scheduled run based on smart rules"""
        schedule = FETCHER_REGISTRY[fetcher_id]['schedule']
        
        if schedule == 'game_hours_only':
            # Next 30 min mark during game hours
            return from_time + timedelta(minutes=30)
        
        elif schedule == 'daily_2am':
            # Tomorrow at 2am
            next_run = from_time.replace(hour=2, minute=0, second=0)
            if from_time.hour >= 2:
                next_run += timedelta(days=1)
            return next_run
        
        elif schedule == 'twice_daily':
            # 2am and 10am - pick whichever is next
            now_hour = from_time.hour
            if now_hour < 2:
                return from_time.replace(hour=2, minute=0, second=0)
            elif now_hour < 10:
                return from_time.replace(hour=10, minute=0, second=0)
            else:
                # After 10am, next is 2am tomorrow
                return from_time.replace(hour=2, minute=0, second=0) + timedelta(days=1)
        
        elif schedule == 'daily_3am':
            next_run = from_time.replace(hour=3, minute=0, second=0)
            if from_time.hour >= 3:
                next_run += timedelta(days=1)
            return next_run
        
        elif schedule == 'game_day_morning':
            # 10am tomorrow
            return from_time.replace(hour=10, minute=0) + timedelta(days=1)
        
        elif schedule == 'weekly_sunday_3am':
            # Next Sunday at 3am
            days_until_sunday = (6 - from_time.weekday()) % 7
            if days_until_sunday == 0 and from_time.hour >= 3:
                days_until_sunday = 7
            return from_time.replace(hour=3, minute=0) + timedelta(days=days_until_sunday)
        
        else:
            return from_time + timedelta(hours=24)
    
    def get_status(self) -> Dict:
        """Get comprehensive status"""
        return {
            'freshness': self.get_data_freshness(),
            'is_game_hours': self.is_game_hours(),
            'is_game_day': self.is_game_day(),
            'stale_fetchers': self.get_stale_fetchers(),
            'checked_at': datetime.now().isoformat(),
        }
    
    def print_status(self):
        """Print human-readable status"""
        print("\n" + "="*60)
        print("� DATA FRESHNESS STATUS")
        print("="*60)
        
        freshness = self.get_data_freshness()
        
        for f in freshness:
            if f.get('error'):
                icon = "❓"
                age = "Error"
            elif f.get('is_stale'):
                icon = "🔴"
                age = f"{f['age_minutes']} min (STALE)"
            elif f.get('age_minutes', 0) > 60:
                icon = "🟡"
                age = f"{f['age_minutes']} min"
            else:
                icon = "🟢"
                age = f"{f['age_minutes']} min"
            
            count = f.get('record_count', '?')
            print(f"{icon} {f['table']}: {age} ({count} records)")
        
        print("\n" + "-"*60)
        stale = self.get_stale_fetchers()
        if stale:
            print(f"⚠️  Stale fetchers: {', '.join(stale)}")
            print("   Run: scheduler.force_refresh('fetcher_id')")
        else:
            print("✅ All data is fresh!")
        print("="*60)


def main():
    """Initialize and show status"""
    script_dir = Path(__file__).parent
    db_path = script_dir / 'data' / 'nba_data.db'
    
    scheduler = SmartScheduler(str(db_path), str(script_dir))
    scheduler.print_status()


if __name__ == '__main__':
    main()
