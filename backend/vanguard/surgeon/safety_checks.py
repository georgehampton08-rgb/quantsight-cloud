"""
Safety Checks
=============
Pre-checks before executing remediation actions.
"""

from typing import Dict, Any
from ..utils.logger import get_logger

logger = get_logger(__name__)


async def run_safety_checks(playbook_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run safety pre-checks before executing a playbook.
    
    Args:
        playbook_name: Name of playbook to execute
        context: Incident context and metrics
    
    Returns:
        {
            "safe": bool,
            "reason": str,
            "recommendations": List[str]
        }
    """
    logger.info("safety_check_started", playbook=playbook_name)
    
    # Default: safe unless proven otherwise
    result = {
        "safe": True,
        "reason": "All safety checks passed",
        "recommendations": []
    }
    
    # Playbook-specific checks
    if playbook_name == "Connection Timeout Syndrome":
        # Check: DB pool not already at max
        current_pool_size = context.get("db_pool_size", 0)
        max_pool_size = context.get("db_pool_max", 100)
        
        if current_pool_size >= max_pool_size:
            result["safe"] = False
            result["reason"] = "DB pool already at maximum capacity"
            result["recommendations"].append("HUMAN_HANDOFF: Cannot scale pool further")
    
    elif playbook_name == "Memory Leak Cascade":
        # Check: Memory actually above baseline
        current_memory = context.get("memory_mb", 0)
        baseline_memory = context.get("baseline_memory_mean", 500)
        
        if current_memory < baseline_memory * 2:
            result["safe"] = False
            result["reason"] = "Memory not significantly above baseline"
            result["recommendations"].append("SKIP: Memory appears normal")
    
    # Log result
    if result["safe"]:
        logger.info("safety_check_passed", playbook=playbook_name)
    else:
        logger.warning("safety_check_failed", playbook=playbook_name, reason=result["reason"])
    
    return result
