"""
Model Auto-Tuner
================
Compares Crucible projections to actual box scores.
Triggers hyperparameter re-calibration if MAE > 3.5.

Schedule: Daily at 4:00 AM
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ProjectionAudit:
    """Single projection vs actual comparison"""
    player_id: str
    player_name: str
    stat: str
    projected: float
    actual: float
    error: float
    game_date: str


@dataclass 
class DriftReport:
    """Daily drift analysis report"""
    audit_date: str
    total_projections: int
    mae_points: float
    mae_rebounds: float
    mae_assists: float
    overall_mae: float
    needs_recalibration: bool
    worst_misses: List[ProjectionAudit]


class ModelAutoTuner:
    """
    Compares yesterday's Crucible projections to actual box scores.
    Triggers re-calibration if drift exceeds threshold.
    """
    
    MAE_THRESHOLD = 3.5  # Trigger recalibration if MAE > 3.5
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'nba_data.db'
        self.db_path = str(db_path)
        self._ensure_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_tables(self):
        """Create audit tables"""
        conn = self._get_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                player_name TEXT,
                game_date TEXT,
                opponent TEXT,
                proj_points REAL,
                proj_rebounds REAL,
                proj_assists REAL,
                proj_threes REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drift_reports (
                audit_date TEXT PRIMARY KEY,
                total_projections INTEGER,
                mae_points REAL,
                mae_rebounds REAL,
                mae_assists REAL,
                overall_mae REAL,
                needs_recalibration INTEGER,
                worst_misses TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hyperparameters (
                param_name TEXT PRIMARY KEY,
                param_value REAL,
                last_tuned TEXT,
                tune_count INTEGER DEFAULT 0
            )
        """)
        
        conn.commit()
        conn.close()
    
    def log_projection(
        self,
        player_id: str,
        player_name: str,
        game_date: str,
        opponent: str,
        proj_points: float,
        proj_rebounds: float,
        proj_assists: float,
        proj_threes: float = 0
    ):
        """Log a projection for later audit"""
        conn = self._get_connection()
        
        conn.execute("""
            INSERT INTO projection_log
            (player_id, player_name, game_date, opponent,
             proj_points, proj_rebounds, proj_assists, proj_threes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(player_id), player_name, game_date, opponent,
            proj_points, proj_rebounds, proj_assists, proj_threes
        ))
        
        conn.commit()
        conn.close()
    
    def get_actual_stats(self, player_id: str, game_date: str) -> Optional[Dict]:
        """Get actual stats from game logs"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT pts, reb, ast, fg3m
            FROM game_logs
            WHERE player_id = ? AND game_date = ?
        """, (str(player_id), game_date))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'points': row['pts'] or 0,
                'rebounds': row['reb'] or 0,
                'assists': row['ast'] or 0,
                'threes': row['fg3m'] or 0,
            }
        return None
    
    def run_daily_audit(self, audit_date: Optional[str] = None) -> DriftReport:
        """
        Run the daily audit comparing yesterday's projections to actuals.
        Called at 4:00 AM daily.
        """
        if audit_date is None:
            yesterday = datetime.now() - timedelta(days=1)
            audit_date = yesterday.strftime('%Y-%m-%d')
        
        logger.info(f"Running daily audit for {audit_date}")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all projections for that date
        cursor.execute("""
            SELECT player_id, player_name, opponent,
                   proj_points, proj_rebounds, proj_assists, proj_threes
            FROM projection_log
            WHERE game_date = ?
        """, (audit_date,))
        
        projections = cursor.fetchall()
        conn.close()
        
        audits = []
        points_errors = []
        reb_errors = []
        ast_errors = []
        
        for proj in projections:
            actual = self.get_actual_stats(proj['player_id'], audit_date)
            
            if actual:
                # Points
                pts_error = abs(proj['proj_points'] - actual['points'])
                points_errors.append(pts_error)
                audits.append(ProjectionAudit(
                    player_id=proj['player_id'],
                    player_name=proj['player_name'],
                    stat='points',
                    projected=proj['proj_points'],
                    actual=actual['points'],
                    error=pts_error,
                    game_date=audit_date,
                ))
                
                # Rebounds
                reb_error = abs(proj['proj_rebounds'] - actual['rebounds'])
                reb_errors.append(reb_error)
                audits.append(ProjectionAudit(
                    player_id=proj['player_id'],
                    player_name=proj['player_name'],
                    stat='rebounds',
                    projected=proj['proj_rebounds'],
                    actual=actual['rebounds'],
                    error=reb_error,
                    game_date=audit_date,
                ))
                
                # Assists
                ast_error = abs(proj['proj_assists'] - actual['assists'])
                ast_errors.append(ast_error)
                audits.append(ProjectionAudit(
                    player_id=proj['player_id'],
                    player_name=proj['player_name'],
                    stat='assists',
                    projected=proj['proj_assists'],
                    actual=actual['assists'],
                    error=ast_error,
                    game_date=audit_date,
                ))
        
        # Calculate MAE
        mae_points = statistics.mean(points_errors) if points_errors else 0
        mae_rebounds = statistics.mean(reb_errors) if reb_errors else 0
        mae_assists = statistics.mean(ast_errors) if ast_errors else 0
        
        overall_mae = statistics.mean(points_errors + reb_errors + ast_errors) if audits else 0
        
        # Get worst misses
        audits.sort(key=lambda x: x.error, reverse=True)
        worst_misses = audits[:10]
        
        # Create report
        report = DriftReport(
            audit_date=audit_date,
            total_projections=len(projections),
            mae_points=round(mae_points, 2),
            mae_rebounds=round(mae_rebounds, 2),
            mae_assists=round(mae_assists, 2),
            overall_mae=round(overall_mae, 2),
            needs_recalibration=overall_mae > self.MAE_THRESHOLD,
            worst_misses=worst_misses,
        )
        
        # Save report
        self._save_drift_report(report)
        
        # Trigger recalibration if needed
        if report.needs_recalibration:
            logger.warning(f"⚠️ MAE {overall_mae:.2f} exceeds threshold {self.MAE_THRESHOLD}")
            self._trigger_recalibration(report)
        else:
            logger.info(f"✅ MAE {overall_mae:.2f} within threshold")
        
        return report
    
    def _save_drift_report(self, report: DriftReport):
        """Save drift report to database"""
        conn = self._get_connection()
        
        worst_misses_json = json.dumps([
            {'player': m.player_name, 'stat': m.stat, 
             'projected': m.projected, 'actual': m.actual, 'error': m.error}
            for m in report.worst_misses
        ])
        
        conn.execute("""
            INSERT OR REPLACE INTO drift_reports
            (audit_date, total_projections, mae_points, mae_rebounds,
             mae_assists, overall_mae, needs_recalibration, worst_misses)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.audit_date, report.total_projections,
            report.mae_points, report.mae_rebounds, report.mae_assists,
            report.overall_mae, 1 if report.needs_recalibration else 0,
            worst_misses_json
        ))
        
        conn.commit()
        conn.close()
    
    def _trigger_recalibration(self, report: DriftReport):
        """
        Trigger hyperparameter recalibration.
        
        Adjusts:
        - Fatigue penalty rate
        - Clutch time usage boost
        - Cold streak pass probability
        """
        logger.info("🔧 Triggering hyperparameter recalibration...")
        
        conn = self._get_connection()
        now = datetime.now().isoformat()
        
        # Example: If points MAE high, reduce fatigue penalty
        if report.mae_points > 4.0:
            # Reduce fatigue penalty (players scoring less than expected)
            conn.execute("""
                INSERT OR REPLACE INTO hyperparameters
                (param_name, param_value, last_tuned, tune_count)
                VALUES ('fatigue_penalty_rate', 0.008, ?, 
                        COALESCE((SELECT tune_count FROM hyperparameters 
                                  WHERE param_name = 'fatigue_penalty_rate'), 0) + 1)
            """, (now,))
            logger.info("  Reduced fatigue_penalty_rate to 0.008")
        
        # If assists MAE high, adjust pass probability
        if report.mae_assists > 2.5:
            conn.execute("""
                INSERT OR REPLACE INTO hyperparameters
                (param_name, param_value, last_tuned, tune_count)
                VALUES ('cold_streak_pass_boost', 0.12, ?,
                        COALESCE((SELECT tune_count FROM hyperparameters 
                                  WHERE param_name = 'cold_streak_pass_boost'), 0) + 1)
            """, (now,))
            logger.info("  Adjusted cold_streak_pass_boost to 0.12")
        
        conn.commit()
        conn.close()
    
    def get_hyperparameter(self, param_name: str, default: float = None) -> float:
        """Get a tuned hyperparameter value"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT param_value FROM hyperparameters WHERE param_name = ?
        """, (param_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return float(row['param_value'])
        return default
    
    def get_recent_reports(self, days: int = 7) -> List[Dict]:
        """Get recent drift reports"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM drift_reports
            ORDER BY audit_date DESC
            LIMIT ?
        """, (days,))
        
        reports = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return reports


# Singleton
_tuner = None

def get_auto_tuner() -> ModelAutoTuner:
    global _tuner
    if _tuner is None:
        _tuner = ModelAutoTuner()
    return _tuner


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    tuner = get_auto_tuner()
    
    print("="*60)
    print("MODEL AUTO-TUNER TEST")
    print("="*60)
    
    # Log some test projections
    print("\n1. Logging test projections...")
    tuner.log_projection(
        "2544", "LeBron James", "2025-01-27", "GSW",
        proj_points=25.5, proj_rebounds=8.0, proj_assists=7.5
    )
    print("   Logged LeBron projection for 2025-01-27")
    
    # Run audit (will be empty without actual data)  
    print("\n2. Running daily audit...")
    report = tuner.run_daily_audit("2025-01-27")
    print(f"   Total projections: {report.total_projections}")
    print(f"   Overall MAE: {report.overall_mae}")
    print(f"   Needs recalibration: {report.needs_recalibration}")
