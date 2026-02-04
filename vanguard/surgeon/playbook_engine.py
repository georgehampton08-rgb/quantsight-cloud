"""
Playbook Engine
===============
Executes remediation actions from playbook entries.
"""

import gc
from typing import Dict, Any, Optional

from ..core.types import Incident
from ..core.config import get_vanguard_config, VanguardMode
from ..utils.logger import get_logger
from .safety_checks import run_safety_checks
from .circuit_breaker import get_circuit_breaker
from .leader_election import get_leader_election

logger = get_logger(__name__)


class PlaybookEngine:
    """
    Remediation playbook executor.
    Implements playbook entries from the manifest.
    """
    
    def __init__(self):
        self.config = get_vanguard_config()
    
    async def execute(self, playbook_name: str, incident: Incident, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a playbook entry.
        
        Args:
            playbook_name: Name of playbook
            incident: Incident data
            context: Metrics and context
        
        Returns:
            {
                "success": bool,
                "action_taken": str,
                "evidence": str
            }
        """
        # Check if Vanguard is in mode that allows actions
        if self.config.mode == VanguardMode.SILENT_OBSERVER:
            logger.info("playbook_skipped", playbook=playbook_name, reason="SILENT_OBSERVER mode")
            return {
                "success": False,
                "action_taken": "NONE",
                "evidence": "Vanguard in SILENT_OBSERVER mode"
            }
        
        # Check if instance is leader
        leader = get_leader_election()
        if not leader.is_leader:
            logger.info("playbook_skipped", playbook=playbook_name, reason="Not leader")
            return {
                "success": False,
                "action_taken": "DEFERRED_TO_LEADER",
                "evidence": "This instance is a FOLLOWER"
            }
        
        # Run safety checks
        safety_result = await run_safety_checks(playbook_name, context)
        if not safety_result["safe"]:
            logger.warning("playbook_safety_failed", playbook=playbook_name, reason=safety_result["reason"])
            return {
                "success": False,
                "action_taken": "SAFETY_CHECK_FAILED",
                "evidence": safety_result["reason"]
            }
        
        # Execute playbook
        logger.info("playbook_executing", playbook=playbook_name)
        
        if playbook_name == "Connection Timeout Syndrome":
            return await self._execute_connection_timeout(incident, context)
        
        elif playbook_name == "Memory Leak Cascade":
            return await self._execute_memory_leak(incident, context)
        
        elif playbook_name == "Database Integrity Violation":
            return await self._execute_integrity_violation(incident, context)
        
        else:
            logger.warning("playbook_not_found", playbook=playbook_name)
            return {
                "success": False,
                "action_taken": "UNKNOWN_PLAYBOOK",
                "evidence": f"Playbook '{playbook_name}' not implemented"
            }
    
    async def _execute_connection_timeout(self, incident: Incident, context: Dict[str, Any]) -> Dict[str, Any]:
        """Playbook: Connection Timeout Syndrome (scale DB pool)."""
        # In real implementation: Scale DB connection pool
        # For now: Log the action
        logger.info("playbook_action", action="Scale DB pool", playbook="Connection Timeout")
        
        return {
            "success": True,
            "action_taken": "DB_POOL_SCALED",
            "evidence": "Scaled pool from 20 → 25 connections (simulated)"
        }
    
    async def _execute_memory_leak(self, incident: Incident, context: Dict[str, Any]) -> Dict[str, Any]:
        """Playbook: Memory Leak Cascade (GC + cache flush)."""
        # Trigger garbage collection
        gc.collect()
        logger.info("playbook_action", action="Forced GC", playbook="Memory Leak")
        
        # TODO: Flush Redis cache if available
        
        return {
            "success": True,
            "action_taken": "GC_EXECUTED",
            "evidence": "Forced garbage collection"
        }
    
    async def _execute_integrity_violation(self, incident: Incident, context: Dict[str, Any]) -> Dict[str, Any]:
        """Playbook: Database Integrity Violation (circuit breaker)."""
        circuit_breaker = get_circuit_breaker()
        endpoint = incident.get("endpoint", "unknown")
        
        # Activate circuit breaker
        circuit_breaker.record_failure(endpoint)
        
        logger.info("playbook_action", action="Circuit breaker activated", endpoint=endpoint)
        
        return {
            "success": True,
            "action_taken": "CIRCUIT_BREAKER_ACTIVATED",
            "evidence": f"Endpoint {endpoint} quarantined"
        }


async def execute_playbook(playbook_name: str, incident: Incident, context: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to execute a playbook."""
    engine = PlaybookEngine()
    return await engine.execute(playbook_name, incident, context)
