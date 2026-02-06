"""
Auto-Tuner v4.0
================
Next-Day Refinement Engine for Crucible Simulation.

Compares predicted game scripts to actual game flow.
Adjusts Team Consistency Factor (TCF) and model weights.

Features:
- Compare blowout predictions to actual results
- Compare clutch game predictions to actual close games
- Adjust archetype probabilities based on accuracy
- Track prediction confidence calibration
"""

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class AuditResult:
    """Result of a single game audit"""
    game_id: str
    game_date: date
    home_team: str
    away_team: str
    
    # Predicted vs Actual
    predicted_home_score: Tuple[float, float, float]  # floor, ev, ceiling
    predicted_away_score: Tuple[float, float, float]
    actual_home_score: int
    actual_away_score: int
    
    # Game script comparison
    predicted_blowout: bool
    actual_blowout: bool
    predicted_clutch: bool
    actual_clutch: bool
    
    # Errors
    home_score_error: float
    away_score_error: float
    script_accuracy: float  # 0-1 how well we predicted game flow


@dataclass
class TuningRecommendation:
    """Recommended weight adjustments"""
    team_id: str
    adjustment_type: str  # 'tcf', 'archetype_weights', 'blowout_threshold'
    current_value: float
    recommended_value: float
    confidence: float
    reason: str


class AutoTuner:
    """
    Next-Day Refinement Engine.
    
    Workflow:
    1. Morning after games: Fetch actual box scores
    2. Compare to predictions in Learning Ledger
    3. Identify systematic errors
    4. Adjust Team Consistency Factor and model weights
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS game_scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT NOT NULL UNIQUE,
        game_date DATE NOT NULL,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        
        -- Predicted values
        predicted_home_score_floor REAL,
        predicted_home_score_ev REAL,
        predicted_home_score_ceiling REAL,
        predicted_away_score_floor REAL,
        predicted_away_score_ev REAL,
        predicted_away_score_ceiling REAL,
        predicted_blowout_pct REAL,
        predicted_clutch_pct REAL,
        
        -- Game script narrative
        predicted_key_events TEXT,
        
        -- Actuals (filled after game)
        actual_home_score INTEGER,
        actual_away_score INTEGER,
        actual_was_blowout BOOLEAN,
        actual_was_clutch BOOLEAN,
        
        -- Audit results
        home_score_error REAL,
        away_score_error REAL,
        script_accuracy REAL,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        audited_at TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS tuning_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id TEXT NOT NULL,
        adjustment_type TEXT NOT NULL,
        old_value REAL,
        new_value REAL,
        reason TEXT,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS team_consistency_factors (
        team_id TEXT PRIMARY KEY,
        tcf REAL DEFAULT 1.0,
        blowout_propensity REAL DEFAULT 0.0,
        clutch_factor REAL DEFAULT 0.0,
        last_updated TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_scripts_date ON game_scripts(game_date);
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "auto_tuner.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
    
    def log_game_script(
        self,
        game_id: str,
        game_date: date,
        home_team: str,
        away_team: str,
        home_score_pred: Tuple[float, float, float],
        away_score_pred: Tuple[float, float, float],
        blowout_pct: float,
        clutch_pct: float,
        key_events: List[str]
    ):
        """
        Log a game prediction for next-day audit.
        
        Args:
            game_id: Unique game identifier
            game_date: Date of game
            home_team: Home team ID
            away_team: Away team ID
            home_score_pred: (floor, ev, ceiling)
            away_score_pred: (floor, ev, ceiling)
            blowout_pct: Probability of blowout
            clutch_pct: Probability of clutch game
            key_events: Predicted key events
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO game_scripts (
                    game_id, game_date, home_team, away_team,
                    predicted_home_score_floor, predicted_home_score_ev, predicted_home_score_ceiling,
                    predicted_away_score_floor, predicted_away_score_ev, predicted_away_score_ceiling,
                    predicted_blowout_pct, predicted_clutch_pct,
                    predicted_key_events
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id, game_date.isoformat(), home_team, away_team,
                home_score_pred[0], home_score_pred[1], home_score_pred[2],
                away_score_pred[0], away_score_pred[1], away_score_pred[2],
                blowout_pct, clutch_pct,
                json.dumps(key_events)
            ))
        
        logger.info(f"[AUTO-TUNER] Logged game script for {home_team} vs {away_team}")
    
    def update_actuals(
        self,
        game_id: str,
        home_score: int,
        away_score: int,
        was_blowout: bool,
        was_clutch: bool
    ) -> Optional[AuditResult]:
        """
        Update a game prediction with actual results.
        
        Returns:
            AuditResult with comparison data
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get prediction
            cursor = conn.execute("""
                SELECT * FROM game_scripts WHERE game_id = ?
            """, (game_id,))
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"[AUTO-TUNER] No prediction found for game {game_id}")
                return None
            
            # Calculate errors
            home_error = abs(row['predicted_home_score_ev'] - home_score)
            away_error = abs(row['predicted_away_score_ev'] - away_score)
            
            # Script accuracy: did we predict game flow correctly?
            blowout_correct = (row['predicted_blowout_pct'] > 0.5) == was_blowout
            clutch_correct = (row['predicted_clutch_pct'] > 0.2) == was_clutch
            script_accuracy = (1.0 if blowout_correct else 0.0) * 0.5 + (1.0 if clutch_correct else 0.0) * 0.5
            
            # Update database
            conn.execute("""
                UPDATE game_scripts
                SET actual_home_score = ?, actual_away_score = ?,
                    actual_was_blowout = ?, actual_was_clutch = ?,
                    home_score_error = ?, away_score_error = ?,
                    script_accuracy = ?, audited_at = ?
                WHERE game_id = ?
            """, (
                home_score, away_score,
                was_blowout, was_clutch,
                home_error, away_error,
                script_accuracy,
                datetime.now().isoformat(),
                game_id
            ))
            
            return AuditResult(
                game_id=game_id,
                game_date=date.fromisoformat(row['game_date']),
                home_team=row['home_team'],
                away_team=row['away_team'],
                predicted_home_score=(
                    row['predicted_home_score_floor'],
                    row['predicted_home_score_ev'],
                    row['predicted_home_score_ceiling']
                ),
                predicted_away_score=(
                    row['predicted_away_score_floor'],
                    row['predicted_away_score_ev'],
                    row['predicted_away_score_ceiling']
                ),
                actual_home_score=home_score,
                actual_away_score=away_score,
                predicted_blowout=row['predicted_blowout_pct'] > 0.5,
                actual_blowout=was_blowout,
                predicted_clutch=row['predicted_clutch_pct'] > 0.2,
                actual_clutch=was_clutch,
                home_score_error=home_error,
                away_score_error=away_error,
                script_accuracy=script_accuracy
            )
    
    def run_next_day_audit(self, target_date: Optional[date] = None) -> List[TuningRecommendation]:
        """
        Run next-day audit for all games on a date.
        
        Returns:
            List of tuning recommendations
        """
        target = target_date or (date.today() - timedelta(days=1))
        recommendations = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Get all audited games for the date
            cursor = conn.execute("""
                SELECT * FROM game_scripts
                WHERE game_date = ? AND audited_at IS NOT NULL
            """, (target.isoformat(),))
            
            games = cursor.fetchall()
            
            if not games:
                logger.info(f"[AUTO-TUNER] No audited games for {target}")
                return recommendations
            
            # Analyze each team's performance
            team_errors = {}
            for game in games:
                home = game['home_team']
                away = game['away_team']
                
                if home not in team_errors:
                    team_errors[home] = {'score_errors': [], 'blowout_misses': 0, 'games': 0}
                if away not in team_errors:
                    team_errors[away] = {'score_errors': [], 'blowout_misses': 0, 'games': 0}
                
                team_errors[home]['score_errors'].append(game['home_score_error'])
                team_errors[away]['score_errors'].append(game['away_score_error'])
                team_errors[home]['games'] += 1
                team_errors[away]['games'] += 1
                
                # Track blowout prediction accuracy
                if game['predicted_blowout_pct'] > 0.5 and not game['actual_was_blowout']:
                    team_errors[home]['blowout_misses'] += 1
                    team_errors[away]['blowout_misses'] += 1
            
            # Generate recommendations
            for team_id, data in team_errors.items():
                avg_error = sum(data['score_errors']) / len(data['score_errors'])
                
                # If average error > 10 points, adjust TCF
                if avg_error > 10:
                    current_tcf = self._get_team_tcf(team_id)
                    adjustment = 0.95 if avg_error > 15 else 0.98
                    new_tcf = current_tcf * adjustment
                    
                    recommendations.append(TuningRecommendation(
                        team_id=team_id,
                        adjustment_type='tcf',
                        current_value=current_tcf,
                        recommended_value=new_tcf,
                        confidence=0.7,
                        reason=f"High prediction error ({avg_error:.1f} pts avg)"
                    ))
                
                # If consistently missing blowout predictions
                if data['blowout_misses'] >= 2:
                    recommendations.append(TuningRecommendation(
                        team_id=team_id,
                        adjustment_type='blowout_threshold',
                        current_value=18.0,
                        recommended_value=20.0,
                        confidence=0.6,
                        reason=f"Blowout predictions too aggressive ({data['blowout_misses']} misses)"
                    ))
        
        return recommendations
    
    def apply_recommendation(self, recommendation: TuningRecommendation) -> bool:
        """Apply a tuning recommendation"""
        with sqlite3.connect(self.db_path) as conn:
            # Log to history
            conn.execute("""
                INSERT INTO tuning_history (team_id, adjustment_type, old_value, new_value, reason)
                VALUES (?, ?, ?, ?, ?)
            """, (
                recommendation.team_id,
                recommendation.adjustment_type,
                recommendation.current_value,
                recommendation.recommended_value,
                recommendation.reason
            ))
            
            # Update TCF if applicable
            if recommendation.adjustment_type == 'tcf':
                conn.execute("""
                    INSERT OR REPLACE INTO team_consistency_factors (team_id, tcf, last_updated)
                    VALUES (?, ?, ?)
                """, (
                    recommendation.team_id,
                    recommendation.recommended_value,
                    datetime.now().isoformat()
                ))
            
            logger.info(
                f"[AUTO-TUNER] Applied {recommendation.adjustment_type} adjustment for {recommendation.team_id}: "
                f"{recommendation.current_value:.3f} → {recommendation.recommended_value:.3f}"
            )
            return True
    
    def _get_team_tcf(self, team_id: str) -> float:
        """Get current Team Consistency Factor for a team"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT tcf FROM team_consistency_factors WHERE team_id = ?
            """, (team_id,))
            
            row = cursor.fetchone()
            return row[0] if row else 1.0
    
    def get_team_adjustments(self, team_id: str) -> Dict:
        """Get all current adjustments for a team"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute("""
                SELECT * FROM team_consistency_factors WHERE team_id = ?
            """, (team_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            return {
                'team_id': team_id,
                'tcf': 1.0,
                'blowout_propensity': 0.0,
                'clutch_factor': 0.0
            }
    
    def get_audit_summary(self, days: int = 7) -> Dict:
        """Get summary of recent audit performance"""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_games,
                    AVG(home_score_error) as avg_home_error,
                    AVG(away_score_error) as avg_away_error,
                    AVG(script_accuracy) as avg_script_accuracy,
                    SUM(CASE WHEN actual_was_blowout = predicted_blowout_pct > 0.5 THEN 1 ELSE 0 END) as blowout_correct,
                    SUM(CASE WHEN actual_was_clutch = predicted_clutch_pct > 0.2 THEN 1 ELSE 0 END) as clutch_correct
                FROM game_scripts
                WHERE game_date >= ? AND audited_at IS NOT NULL
            """, (cutoff,))
            
            row = cursor.fetchone()
            
            if not row or row[0] == 0:
                return {'total_games': 0}
            
            return {
                'total_games': row[0],
                'avg_home_error': row[1] or 0,
                'avg_away_error': row[2] or 0,
                'avg_script_accuracy': row[3] or 0,
                'blowout_accuracy': (row[4] or 0) / row[0],
                'clutch_accuracy': (row[5] or 0) / row[0]
            }


# =============================================================================
# DEMO
# =============================================================================

def run_demo():
    """Demo the Auto-Tuner"""
    print("=" * 70)
    print(" ⚙️  AUTO-TUNER DEMO")
    print("=" * 70)
    
    tuner = AutoTuner()
    
    # Log a sample game script
    today = date.today()
    tuner.log_game_script(
        game_id="LAL_GSW_20260128",
        game_date=today,
        home_team="LAL",
        away_team="GSW",
        home_score_pred=(89, 98, 108),
        away_score_pred=(90, 99, 108),
        blowout_pct=0.25,
        clutch_pct=0.15,
        key_events=[
            "Stephen Curry benched (foul trouble)",
            "🚨 BLOWOUT predicted at 18+ point differential"
        ]
    )
    print("\n✅ Logged game script for LAL vs GSW")
    
    # Simulate updating with actuals
    result = tuner.update_actuals(
        game_id="LAL_GSW_20260128",
        home_score=102,
        away_score=98,
        was_blowout=False,
        was_clutch=True
    )
    
    if result:
        print(f"\n📊 Audit Result:")
        print(f"   Predicted: {result.predicted_home_score[1]:.0f} - {result.predicted_away_score[1]:.0f}")
        print(f"   Actual: {result.actual_home_score} - {result.actual_away_score}")
        print(f"   Home Error: {result.home_score_error:.1f} pts")
        print(f"   Away Error: {result.away_score_error:.1f} pts")
        print(f"   Script Accuracy: {result.script_accuracy:.1%}")
        print(f"   Blowout: Predicted={result.predicted_blowout}, Actual={result.actual_blowout}")
        print(f"   Clutch: Predicted={result.predicted_clutch}, Actual={result.actual_clutch}")
    
    # Get summary
    summary = tuner.get_audit_summary(days=7)
    print(f"\n📈 7-Day Audit Summary:")
    print(f"   Total Games: {summary.get('total_games', 0)}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_demo()
