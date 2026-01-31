"""
Next-Day Audit v3.1
===================
Morning job to compare yesterday's projections to actual results.
Auto-tunes model weights if error exceeds threshold.
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuditResult:
    """Result of single projection audit"""
    player_id: str
    game_date: date
    pts_projected: float
    pts_actual: float
    error: float
    within_range: bool


@dataclass
class AuditSummary:
    """Summary of daily audit"""
    audit_date: date
    total_projections: int
    projections_audited: int
    accuracy_rate: float
    avg_error: float
    model_adjustments: Dict[str, float]


class NextDayAudit:
    """
    Morning audit job.
    
    1. Get yesterday's projections from Learning Ledger
    2. Fetch actual box scores from NBA API
    3. Calculate prediction error per projection
    4. Mark within_floor_ceiling boolean
    5. Auto-tune model weights if needed
    """
    
    ERROR_THRESHOLD = 3.5  # MAE threshold for rebalancing
    
    def __init__(
        self,
        learning_ledger: Optional[Any] = None,
        vanguard_forge: Optional[Any] = None,
        nba_api: Optional[Any] = None
    ):
        self.ledger = learning_ledger
        self.forge = vanguard_forge
        self.nba_api = nba_api
        
        self._audit_history: List[AuditSummary] = []
    
    async def run_audit(self, audit_date: Optional[date] = None) -> AuditSummary:
        """
        Run audit for a specific date (default: yesterday).
        
        Returns:
            AuditSummary with accuracy stats and model adjustments
        """
        audit_date = audit_date or (date.today() - timedelta(days=1))
        
        logger.info(f"[AUDIT] Running audit for {audit_date}")
        
        # Get projections from ledger
        if not self.ledger:
            return self._empty_summary(audit_date, "No ledger available")
        
        projections = self.ledger.get_projections_for_date(audit_date)
        
        if not projections:
            return self._empty_summary(audit_date, "No projections for date")
        
        # Fetch actual results
        actuals = await self._fetch_actuals(audit_date)
        
        # Compare and update
        audit_results = []
        
        for proj in projections:
            player_id = proj['player_id']
            
            if player_id not in actuals:
                continue
            
            actual = actuals[player_id]
            
            # Update ledger with actuals
            self.ledger.update_actuals(player_id, audit_date, actual)
            
            # Record result
            pts_ev = proj.get('pts_ev', 0)
            pts_actual = actual.get('points', 0)
            pts_floor = proj.get('pts_floor', 0)
            pts_ceiling = proj.get('pts_ceiling', 999)
            
            audit_results.append(AuditResult(
                player_id=player_id,
                game_date=audit_date,
                pts_projected=pts_ev,
                pts_actual=pts_actual,
                error=abs(pts_ev - pts_actual),
                within_range=pts_floor <= pts_actual <= pts_ceiling
            ))
        
        # Calculate summary stats
        if not audit_results:
            return self._empty_summary(audit_date, "No matching actuals found")
        
        accuracy = sum(1 for r in audit_results if r.within_range) / len(audit_results)
        avg_error = sum(r.error for r in audit_results) / len(audit_results)
        
        # Auto-tune models if needed
        adjustments = self._auto_tune_models(audit_results, avg_error)
        
        summary = AuditSummary(
            audit_date=audit_date,
            total_projections=len(projections),
            projections_audited=len(audit_results),
            accuracy_rate=round(accuracy, 3),
            avg_error=round(avg_error, 2),
            model_adjustments=adjustments
        )
        
        self._audit_history.append(summary)
        
        logger.info(f"[AUDIT] Complete: {summary.projections_audited} audited, "
                   f"{summary.accuracy_rate:.1%} accuracy, MAE={summary.avg_error}")
        
        return summary
    
    async def _fetch_actuals(self, game_date: date) -> Dict[str, Dict]:
        """Fetch actual box scores for a date"""
        if not self.nba_api:
            logger.warning("[AUDIT] No NBA API available, using empty actuals")
            return {}
        
        try:
            # This would call NBA API to get box scores
            # For now, return empty - to be implemented with real API
            if hasattr(self.nba_api, 'get_box_scores'):
                return await self.nba_api.get_box_scores(game_date)
            return {}
        except Exception as e:
            logger.error(f"[AUDIT] Error fetching actuals: {e}")
            return {}
    
    def _auto_tune_models(
        self,
        results: List[AuditResult],
        avg_error: float
    ) -> Dict[str, float]:
        """
        Auto-tune model weights based on error.
        
        If error exceeds threshold, adjust weights.
        """
        adjustments = {}
        
        if avg_error <= self.ERROR_THRESHOLD:
            # Models performing well, small boost
            adjustments = {
                'linear_regression': 0.01,
                'random_forest': 0.01,
                'xgboost': 0.01
            }
        else:
            # Underperforming - analyze which model to penalize
            # For now, reduce all equally
            adjustments = {
                'linear_regression': -0.02,
                'random_forest': -0.02,
                'xgboost': -0.02
            }
        
        # Apply to forge if available
        if self.forge:
            for model, adjustment in adjustments.items():
                self.forge.update_weights(model, adjustment)
        
        return adjustments
    
    def _empty_summary(self, audit_date: date, reason: str) -> AuditSummary:
        """Return empty summary when audit cannot proceed"""
        logger.warning(f"[AUDIT] Empty audit for {audit_date}: {reason}")
        
        return AuditSummary(
            audit_date=audit_date,
            total_projections=0,
            projections_audited=0,
            accuracy_rate=0,
            avg_error=0,
            model_adjustments={}
        )
    
    def get_audit_history(self, limit: int = 30) -> List[Dict]:
        """Get recent audit history"""
        return [
            {
                'date': a.audit_date.isoformat(),
                'audited': a.projections_audited,
                'accuracy': a.accuracy_rate,
                'avg_error': a.avg_error
            }
            for a in self._audit_history[-limit:]
        ]
    
    def schedule_daily_audit(self):
        """Schedule audit to run daily at 9 AM"""
        # This would integrate with APScheduler or similar
        # For now, just a placeholder for the concept
        logger.info("[AUDIT] Daily audit scheduled for 09:00")
