"""
Vanguard Surgeon Learning System
=================================
Tracks remediation outcomes and calculates success rates.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SurgeonLearningSystem:
    """Tracks and learns from remediation outcomes."""
    
    async def log_remediation(
        self,
        decision: Dict[str, Any],
        storage
    ):
        """
        Log a remediation decision for future learning.
        
        Args:
            decision: Surgeon decision with action, endpoint, confidence
            storage: Firestore storage client
        """
        try:
            action_id = f"{decision['endpoint'].replace('/', '_')}_{decision['timestamp']}"
            
            await storage.set_document(
                collection="vanguard_surgeon_actions",
                document_id=action_id,
                data={
                    **decision,
                    "outcome": "pending",
                    "logged_at": datetime.utcnow().isoformat()
                }
            )
            
            logger.info("remediation_logged", action=decision["action"], id=action_id)
        except Exception as e:
            logger.error("remediation_log_failed", error=str(e))
    
    async def check_remediation_outcome(
        self,
        endpoint: str,
        action_timestamp: str,
        storage
    ) -> str:
        """
        Check if remediation worked by looking at error rate after action.
        
        Args:
            endpoint: The endpoint that was remediated
            action_timestamp: When the action was taken (ISO 8601)
            storage: Firestore storage client
            
        Returns:
            "success", "failure", or "pending"
        """
        try:
            # Parse action time
            action_time = datetime.fromisoformat(action_timestamp)
            check_time = action_time + timedelta(hours=1)
            
            # Query incidents for this endpoint after the action
            incidents = await storage.query_collection(
                collection="vanguard_incidents",
                filters=[
                    ("endpoint", "==", endpoint),
                    ("timestamp", ">", action_time.isoformat()),
                    ("timestamp", "<", check_time.isoformat())
                ]
            )
            
            if len(incidents) == 0:
                return "success"  # No more errors!
            elif len(incidents) < 5:
                return "pending"  # Still monitoring
            else:
                return "failure"  # Still broken
                
        except Exception as e:
            logger.error("outcome_check_failed", error=str(e))
            return "pending"
    
    async def get_success_rate(
        self,
        action_type: str,
        storage
    ) -> float:
        """
        Get success rate for a specific action type.
        
        Args:
            action_type: MONITOR, RATE_LIMIT, or QUARANTINE
            storage: Firestore storage client
            
        Returns:
            Success rate (0.0 to 1.0)
        """
        try:
            # Get all actions of this type
            actions = await storage.query_collection(
                collection="vanguard_surgeon_actions",
                filters=[("action", "==", action_type)]
            )
            
            if not actions:
                return 0.0
            
            # Count successes
            successes = sum(1 for a in actions if a.get("outcome") == "success")
            return successes / len(actions)
            
        except Exception as e:
            logger.error("success_rate_calculation_failed", error=str(e))
            return 0.0
    
    async def get_all_success_rates(self, storage) -> Dict[str, float]:
        """Get success rates for all action types."""
        return {
            "MONITOR": await self.get_success_rate("MONITOR", storage),
            "RATE_LIMIT": await self.get_success_rate("RATE_LIMIT", storage),
            "QUARANTINE": await self.get_success_rate("QUARANTINE", storage),
            "LOG_ONLY": await self.get_success_rate("LOG_ONLY", storage),
        }
    
    async def update_pending_outcomes(self, storage):
        """
        Background job to update outcomes for actions taken > 1 hour ago.
        Should be run periodically (e.g., every 15 minutes).
        """
        try:
            # Get all pending outcomes
            pending_actions = await storage.query_collection(
                collection="vanguard_surgeon_actions",
                filters=[("outcome", "==", "pending")]
            )
            
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            for action in pending_actions:
                action_time = datetime.fromisoformat(action["timestamp"])
                
                # Only check actions > 1 hour old
                if action_time < cutoff_time:
                    outcome = await self.check_remediation_outcome(
                        endpoint=action["endpoint"],
                        action_timestamp=action["timestamp"],
                        storage=storage
                    )
                    
                    if outcome != "pending":
                        # Update the action with outcome
                        await storage.update_document(
                            collection="vanguard_surgeon_actions",
                            document_id=action["id"],
                            updates={
                                "outcome": outcome,
                                "verified_at": datetime.utcnow().isoformat()
                            }
                        )
                        
                        logger.info(
                            "outcome_updated",
                            action=action["action"],
                            endpoint=action["endpoint"],
                            outcome=outcome
                        )
            
            logger.info(f"updated_outcomes", count=len(pending_actions))
            
        except Exception as e:
            logger.error("update_pending_outcomes_failed", error=str(e))


# Singleton instance
_learning_system: SurgeonLearningSystem | None = None


def get_learning_system() -> SurgeonLearningSystem:
    """Get or create the global learning system."""
    global _learning_system
    if _learning_system is None:
        _learning_system = SurgeonLearningSystem()
    return _learning_system
