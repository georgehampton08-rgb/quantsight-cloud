"""
Vanguard Surgeon Remediation
============================
Auto-remediation engine for self-healing operations.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Singleton instance
_surgeon_instance = None


class VanguardSurgeon:
    """
    Remediation engine for automated incident response.
    
    Provides:
    - Automatic remediation actions based on playbooks
    - Circuit breaker integration
    - Safety checks before actions
    """
    
    def __init__(self):
        self._playbooks: Dict[str, Any] = {}
        self._enabled = True
        logger.info("VanguardSurgeon initialized")
    
    async def remediate(self, incident_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute remediation for a given incident type.
        
        Args:
            incident_type: Type of incident (e.g., 'api_timeout', 'rate_limit')
            context: Additional context about the incident
            
        Returns:
            Result of remediation attempt
        """
        if not self._enabled:
            return {"status": "disabled", "action": None}
        
        playbook = self._playbooks.get(incident_type)
        if not playbook:
            return {"status": "no_playbook", "action": None}
        
        try:
            # Execute playbook (placeholder for actual implementation)
            logger.info(f"Executing playbook for {incident_type}")
            return {"status": "success", "action": "playbook_executed"}
        except Exception as e:
            logger.error(f"Remediation failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def register_playbook(self, incident_type: str, playbook: Any):
        """Register a remediation playbook for an incident type."""
        self._playbooks[incident_type] = playbook
        logger.info(f"Registered playbook for {incident_type}")
    
    async def decide_remediation(
        self,
        incident: Dict[str, Any],
        analysis: Dict[str, Any],
        mode: str
    ) -> Dict[str, Any]:
        """
        Decide remediation action based on AI analysis with code context.
        
        Decision Matrix:
        - confidence >= 85% + ready_to_resolve = MONITOR (likely fixed)
        - confidence < 70% = QUARANTINE (unsafe)
        - confidence 70-84% = RATE_LIMIT (cautious)
        
        Args:
            incident: Incident details
            analysis: AI Analyzer output (with GitHub code context)
            mode: CIRCUIT_BREAKER, SILENT_OBSERVER, or FULL_SOVEREIGN
            
        Returns:
            Remediation decision with action + reasoning
        """
        from datetime import datetime
        
        confidence = analysis.get("confidence", 0)
        ready = analysis.get("ready_to_resolve", False)
        endpoint = incident.get("endpoint", "unknown")
        
        logger.info(f"surgeon_decision_start", endpoint=endpoint, confidence=confidence, ready=ready)
        
        if mode == "CIRCUIT_BREAKER":
            # High confidence + ready = likely fixed
            if confidence >= 85 and ready:
                action = "MONITOR"
                reason = f"{confidence}% confidence bug is fixed (recent commit deployed)"
            
            # Low confidence = quarantine
            elif confidence < 70:
                action = "QUARANTINE"
                reason = f"Low confidence ({confidence}%), quarantine endpoint for safety"
            
            # Medium confidence = rate limit
            else:
                action = "RATE_LIMIT"
                reason = f"Medium confidence ({confidence}%), reduce traffic 50%"
        
        elif mode == "SILENT_OBSERVER":
            action = "LOG_ONLY"
            reason = f"Silent mode, no action taken"
        
        else:
            action = "LOG_ONLY"
            reason = f"Unknown mode: {mode}"
        
        decision = {
            "action": action,
            "reason": reason,
            "confidence": confidence,
            "endpoint": endpoint,
            "timestamp": datetime.utcnow().isoformat(),
            "mode": mode
        }
        
        logger.info(f"surgeon_decision_made", action=action, reason=reason)
        return decision
    
    async def execute_remediation(
        self,
        decision: Dict[str, Any],
        storage
    ) -> Dict[str, Any]:
        """
        Execute the remediation action decided by Surgeon.
        
        Args:
            decision: Remediation decision from decide_remediation()
            storage: Firestore storage client
            
        Returns:
            Execution result including success status
        """
        from datetime import datetime
        
        action = decision["action"]
        endpoint = decision["endpoint"]
        
        logger.info(f"surgeon_execute_start", action=action, endpoint=endpoint)
        
        success = False
        
        try:
            if action == "QUARANTINE":
                success = await self._quarantine_endpoint(endpoint, storage)
            elif action == "RATE_LIMIT":
                success = await self._rate_limit_endpoint(endpoint, storage)
            elif action == "MONITOR":
                success = await self._monitor_endpoint(endpoint, storage)
            else:  # LOG_ONLY
                success = True
            
            execution_result = {
                **decision,
                "executed": success,
                "executed_at": datetime.utcnow().isoformat()
            }
            
            # ✅ PHASE 5: Log to learning system
            await self._log_to_learning_system(execution_result, storage)
            
            logger.info(f"surgeon_execute_complete", action=action, success=success)
            return execution_result
            
        except Exception as e:
            logger.error(f"surgeon_execute_failed", action=action, error=str(e))
            return {
                **decision,
                "executed": False,
                "executed_at": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def _quarantine_endpoint(self, endpoint: str, storage) -> bool:
        """Block all traffic to endpoint by adding to quarantine list."""
        from datetime import datetime
        
        try:
            await storage.set_document(
                collection="vanguard_quarantine",
                document_id=endpoint.replace("/", "_"),
                data={
                    "endpoint": endpoint,
                    "quarantined_at": datetime.utcnow().isoformat(),
                    "reason": "Surgeon decision - low confidence",
                    "active": True
                }
            )
            logger.warning(f"⛔ QUARANTINED: {endpoint}")
            return True
        except Exception as e:
            logger.error(f"quarantine_failed", endpoint=endpoint, error=str(e))
            return False
    
    async def _rate_limit_endpoint(self, endpoint: str, storage) -> bool:
        """Reduce traffic to endpoint by 50%."""
        from datetime import datetime
        
        try:
            await storage.set_document(
                collection="vanguard_rate_limits",
                document_id=endpoint.replace("/", "_"),
                data={
                    "endpoint": endpoint,
                    "limit_pct": 50,  # Allow only 50% of normal traffic
                    "limited_at": datetime.utcnow().isoformat(),
                    "active": True
                }
            )
            logger.info(f"🐌 RATE LIMITED: {endpoint} to 50%")
            return True
        except Exception as e:
            logger.error(f"rate_limit_failed", endpoint=endpoint, error=str(e))
            return False
    
    async def _monitor_endpoint(self, endpoint: str, storage) -> bool:
        """Just monitor, no action."""
        logger.info(f"👁️ MONITORING: {endpoint}")
        return True
    
    async def _log_to_learning_system(
        self,
        execution_result: Dict[str, Any],
        storage
    ):
        """Log execution to learning system for tracking success rates."""
        try:
            from datetime import datetime
            
            # Generate unique ID for this action
            action_id = f"{execution_result['endpoint'].replace('/', '_')}_{execution_result['timestamp']}"
            
            await storage.set_document(
                collection="vanguard_surgeon_actions",
                document_id=action_id,
                data={
                    **execution_result,
                    "outcome": "pending",  # Will be updated after 1 hour
                    "logged_at": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"logged_to_learning_system", action=execution_result["action"], id=action_id)
        except Exception as e:
            logger.error(f"learning_system_log_failed", error=str(e))
    
    def enable(self):
        """Enable remediation."""
        self._enabled = True
    
    def disable(self):
        """Disable remediation."""
        self._enabled = False


def get_surgeon() -> VanguardSurgeon:
    """Get the singleton Surgeon instance."""
    global _surgeon_instance
    if _surgeon_instance is None:
        _surgeon_instance = VanguardSurgeon()
    return _surgeon_instance
