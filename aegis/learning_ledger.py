"""
Learning Ledger v3.1
====================
Projection history database for ML feedback loop.

Every simulation result (Floor/EV/Ceiling) is saved.
Next-Day Audit compares projections to actuals.
"""

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class LedgerEntry:
    """Single entry in the learning ledger"""
    id: Optional[int]
    player_id: str
    opponent_id: str
    game_date: date
    
    # Projections
    pts_floor: float
    pts_ev: float
    pts_ceiling: float
    
    # Actuals (filled by Next-Day Audit)
    pts_actual: Optional[float] = None
    prediction_error: Optional[float] = None
    within_range: Optional[bool] = None
    
    # Metadata
    model_weights: Optional[Dict[str, float]] = None
    confluence_score: Optional[float] = None
    created_at: Optional[datetime] = None


class LearningLedger:
    """
    Projection history database.
    
    Features:
    - Persist every simulation result
    - Track actuals after games complete
    - Calculate historical accuracy for Confluence Score
    """
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS learning_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id TEXT NOT NULL,
        opponent_id TEXT NOT NULL,
        game_date DATE NOT NULL,
        
        -- Projections
        pts_floor REAL,
        pts_ev REAL,
        pts_ceiling REAL,
        reb_floor REAL,
        reb_ev REAL,
        reb_ceiling REAL,
        ast_floor REAL,
        ast_ev REAL,
        ast_ceiling REAL,
        
        -- Actuals (filled by Next-Day Audit)
        pts_actual REAL,
        reb_actual REAL,
        ast_actual REAL,
        
        -- Accuracy
        prediction_error REAL,
        within_range BOOLEAN,
        
        -- Metadata
        model_weights TEXT,
        confluence_score REAL,
        execution_time_ms REAL,
        
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        
        UNIQUE(player_id, opponent_id, game_date)
    );
    
    CREATE INDEX IF NOT EXISTS idx_ledger_player ON learning_ledger(player_id);
    CREATE INDEX IF NOT EXISTS idx_ledger_date ON learning_ledger(game_date);
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "learning_ledger.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
    
    def record_projection(
        self,
        player_id: str,
        opponent_id: str,
        game_date: date,
        projection: Dict[str, Dict[str, float]],
        confluence_score: float,
        model_weights: Optional[Dict[str, float]] = None,
        execution_time_ms: Optional[float] = None
    ) -> int:
        """
        Record a projection in the ledger.
        
        Args:
            player_id: NBA player ID
            opponent_id: Opponent team ID
            game_date: Date of the game
            projection: {'floor': {...}, 'ev': {...}, 'ceiling': {...}}
            confluence_score: 0-100 confidence score
            
        Returns:
            Row ID of inserted record
        """
        floor = projection.get('floor', {})
        ev = projection.get('ev', {})
        ceiling = projection.get('ceiling', {})
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO learning_ledger (
                    player_id, opponent_id, game_date,
                    pts_floor, pts_ev, pts_ceiling,
                    reb_floor, reb_ev, reb_ceiling,
                    ast_floor, ast_ev, ast_ceiling,
                    model_weights, confluence_score, execution_time_ms,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_id, opponent_id, game_date.isoformat(),
                floor.get('points'), ev.get('points'), ceiling.get('points'),
                floor.get('rebounds'), ev.get('rebounds'), ceiling.get('rebounds'),
                floor.get('assists'), ev.get('assists'), ceiling.get('assists'),
                json.dumps(model_weights) if model_weights else None,
                confluence_score,
                execution_time_ms,
                datetime.now().isoformat()
            ))
            
            logger.info(f"[LEDGER] Recorded projection for {player_id} vs {opponent_id}")
            return cursor.lastrowid
    
    def update_actuals(
        self,
        player_id: str,
        game_date: date,
        actuals: Dict[str, float]
    ) -> bool:
        """
        Update a projection with actual results.
        
        Args:
            player_id: NBA player ID
            game_date: Date of the game
            actuals: {'points': x, 'rebounds': y, 'assists': z}
            
        Returns:
            True if record was updated
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get projection to calculate error
            cursor = conn.execute("""
                SELECT pts_ev, pts_floor, pts_ceiling 
                FROM learning_ledger
                WHERE player_id = ? AND game_date = ?
            """, (player_id, game_date.isoformat()))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            pts_ev, pts_floor, pts_ceiling = row
            pts_actual = actuals.get('points', 0)
            
            # Calculate error and within_range
            prediction_error = abs(pts_ev - pts_actual) if pts_ev else None
            within_range = pts_floor <= pts_actual <= pts_ceiling if all([pts_floor, pts_ceiling]) else None
            
            conn.execute("""
                UPDATE learning_ledger
                SET pts_actual = ?, reb_actual = ?, ast_actual = ?,
                    prediction_error = ?, within_range = ?,
                    updated_at = ?
                WHERE player_id = ? AND game_date = ?
            """, (
                pts_actual,
                actuals.get('rebounds'),
                actuals.get('assists'),
                prediction_error,
                within_range,
                datetime.now().isoformat(),
                player_id,
                game_date.isoformat()
            ))
            
            logger.info(f"[LEDGER] Updated actuals for {player_id} on {game_date}")
            return True
    
    def get_player_history(
        self,
        player_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """Get player's projection history for accuracy calculation"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM learning_ledger
                WHERE player_id = ? AND pts_actual IS NOT NULL
                ORDER BY game_date DESC
                LIMIT ?
            """, (player_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_historical_accuracy(self, player_id: str, limit: int = 20) -> float:
        """
        Calculate % of projections within Floor-Ceiling range.
        Used for the Historical Accuracy component of Confluence Score.
        """
        history = self.get_player_history(player_id, limit)
        
        if not history:
            return 0.5  # Default 50% for new players
        
        hits = sum(1 for h in history if h.get('within_range'))
        return hits / len(history)
    
    def get_projections_for_date(self, game_date: date) -> List[Dict]:
        """Get all projections for a specific date (for Next-Day Audit)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM learning_ledger
                WHERE game_date = ?
            """, (game_date.isoformat(),))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_accuracy_stats(self, days: int = 30) -> Dict:
        """Get aggregate accuracy stats for recent projections"""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN within_range = 1 THEN 1 ELSE 0 END) as hits,
                    AVG(prediction_error) as avg_error,
                    AVG(confluence_score) as avg_confidence
                FROM learning_ledger
                WHERE game_date >= ? AND pts_actual IS NOT NULL
            """, (cutoff,))
            
            row = cursor.fetchone()
            
            if not row or row[0] == 0:
                return {'total': 0, 'accuracy': 0, 'avg_error': 0}
            
            return {
                'total': row[0],
                'hits': row[1] or 0,
                'accuracy': (row[1] or 0) / row[0],
                'avg_error': row[2] or 0,
                'avg_confidence': row[3] or 0
            }
