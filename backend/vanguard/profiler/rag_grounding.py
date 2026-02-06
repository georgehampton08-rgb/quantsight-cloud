"""
RAG Grounding
=============
Inject system manifest into LLM prompts to prevent hallucinations.
"""

from typing import Dict, Any
from .system_manifest import generate_system_manifest, SystemManifest
from ..utils.logger import get_logger

logger = get_logger(__name__)


def ground_llm_prompt(incident_details: Dict[str, Any]) -> str:
    """
    Create a grounded LLM prompt with system manifest injection.
    
    Args:
        incident_details: Incident data (error type, traceback, metrics)
    
    Returns:
        Complete LLM prompt with RAG grounding
    """
    manifest = generate_system_manifest()
    
    prompt = f"""You are a Site Reliability Engineer for THIS SPECIFIC SYSTEM:

SYSTEM MANIFEST:
- Platform: {manifest['platform']}
- Database: {manifest['database']}
- Cache: {manifest['cache']}

AVAILABLE REMEDIATION ACTIONS (ONLY THESE):
{chr(10).join(f"  - {playbook}" for playbook in manifest['available_playbooks'])}

FAILURE CONTEXT:
- Error Type: {incident_details.get('error_type', 'Unknown')}
- Error Message: {incident_details.get('error_message', 'Unknown')}
- Endpoint: {incident_details.get('endpoint', 'Unknown')}
- Traceback: {incident_details.get('traceback', 'Not available')[:500]}

TASK:
1. Classify this failure using ONLY the available playbook entries above.
2. DO NOT suggest remediation actions outside this list (no Kubernetes, no Docker commands).
3. Provide a confidence score (0-100%).
4. Recommend the appropriate playbook entry or escalate to HUMAN_HANDOFF.

RESPONSE FORMAT (JSON):
{{
  "root_cause": "Brief classification",
  "confidence": 85,
  "recommended_action": "Connection Timeout Syndrome" or "HUMAN_HANDOFF",
  "evidence": "Why you believe this diagnosis"
}}
"""
    
    logger.debug("llm_prompt_grounded", incident=incident_details.get('fingerprint'))
    return prompt
