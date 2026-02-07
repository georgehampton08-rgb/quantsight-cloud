"""
Vanguard Escalation Engine
==========================
Autonomously adjusts Vanguard's operation mode based on system health.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Any

from vanguard.core.config import get_vanguard_config, VanguardMode
from vanguard.health_scoring import get_score_calculator
from vanguard.health_monitor import get_health_monitor

logger = logging.getLogger(__name__)

class EscalationEngine:
    """
    Monitors health scores and escalates Vanguard's operational mode.
    
    Escalation Rules:
    - Score > 90: SILENT_OBSERVER (Monitoring)
    - Score 70-89: SILENT_OBSERVER (Warning)
    - Score < 70: CIRCUIT_BREAKER (Active Protection)
    - Score < 40: FULL_SOVEREIGN (Autonomous Healing - Requires human approval for now)
    """
    
    def __init__(self):
        self.config = get_vanguard_config()
        self.monitor = get_health_monitor()
        self.calculator = get_score_calculator()
        self._running = False
        self._last_score = 100.0
        self._consecutive_low_scores = 0
        
    async def start(self):
        """Start the escalation monitoring loop."""
        if self._running:
            return
        
        self._running = True
        logger.info("Escalation Engine STARTED")
        asyncio.create_task(self._monitoring_loop())
        # Trigger an immediate check instead of waiting for loop
        asyncio.create_task(self._trigger_immediate_check())
        
    async def _trigger_immediate_check(self):
        """Run one check immediately."""
        await asyncio.sleep(5) # Give subsystems a second to breath
        await self._check_once()

    async def _monitoring_loop(self):
        """Background loop to check health and escalate."""
        while self._running:
            await self._check_once()
            await asyncio.sleep(120)
            
    async def _check_once(self):
        """Perform a single health check and escalation decision."""
        try:
            # 1. Fetch current health results
            health_results = await self.monitor.run_all_checks()
            
            # Exclude Redis from scoring on Cloud Run (not configured)
            if os.getenv('K_SERVICE') and 'redis' in health_results:
                health_results = {k: v for k, v in health_results.items() if k != 'redis'}
            
            # 2. Calculate score
            # Note: component_score is 0-60 based on core systems
            component_score = self.calculator.calculate_component_score(health_results)
            
            # Only log when score changes (reduce noise)
            if component_score != self._last_score:
                logger.info(f"Escalation Check: Health Score = {component_score:.1f} (was {self._last_score:.1f})")
            else:
                logger.debug(f"Escalation Check: Health Score = {component_score:.1f} (unchanged)")
            
            self._last_score = component_score
            
            # 3. Decision Logic
            # If core systems (NBA, Firestore) are down, we MUST protect
            # component_score < 40 means at least one core system is critical (or all warning)
            if component_score < 45: 
                await self._escalate(VanguardMode.CIRCUIT_BREAKER, f"Health dropped to {component_score:.1f}")
            elif component_score >= 55 and self.config.mode == VanguardMode.CIRCUIT_BREAKER:
                await self._deescalate(VanguardMode.SILENT_OBSERVER, "Health recovered")
                
        except Exception as e:
            logger.error(f"Escalation check failed: {e}")
                
    async def _escalate(self, target_mode: VanguardMode, reason: str):
        """Escalate Vanguard mode."""
        if self.config.mode == target_mode:
            return
            
        old_mode = self.config.mode
        self.config.mode = target_mode
        
        logger.warning(f"🚨 ESCALATION: {old_mode} -> {target_mode} | Reason: {reason}")
        
    async def _deescalate(self, target_mode: VanguardMode, reason: str):
        """De-escalate Vanguard mode."""
        if self.config.mode == target_mode:
            return
            
        old_mode = self.config.mode
        self.config.mode = target_mode
        
        logger.info(f"🛡️ DE-ESCALATION: {old_mode} -> {target_mode} | Reason: {reason}")

# Singleton
_escalation_engine = None

def get_escalation_engine() -> EscalationEngine:
    global _escalation_engine
    if _escalation_engine is None:
        _escalation_engine = EscalationEngine()
    return _escalation_engine
