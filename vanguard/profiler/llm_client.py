"""
LLM Client
==========
Async Google Gemini client for root cause analysis.
Uses the new google.genai SDK.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from google import genai

from ..core.config import get_vanguard_config
from ..utils.logger import get_logger
from .rag_grounding import ground_llm_prompt

logger = get_logger(__name__)


class LLMClient:
    """Async LLM client for Profiler reasoning using Google Gemini."""
    
    def __init__(self):
        self.config = get_vanguard_config()
        
        if not self.config.llm_enabled:
            logger.warning("llm_disabled", message="Set VANGUARD_LLM_ENABLED=true to activate")
            self.client = None
            return
        
        if not self.config.gemini_api_key:
            logger.error("llm_no_api_key", message="GEMINI_API_KEY not set")
            self.client = None
            return
        
        # Configure Gemini with new API
        self.client = genai.Client(api_key=self.config.gemini_api_key)
        logger.info("llm_client_initialized", model="gemini-1.5-flash")
    
    async def classify_incident(self, incident_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Classify an incident using Google Gemini with RAG grounding.
        
        Args:
            incident_details: Incident data
        
        Returns:
            {
                "root_cause": str,
                "confidence": int,
                "recommended_action": str,
                "evidence": str
            }
        """
        if not self.client:
            logger.warning("llm_not_available")
            return None
        
        try:
            # Generate grounded prompt
            prompt = ground_llm_prompt(incident_details)
            
            # Add SRE system context
            full_prompt = f"""You are a Site Reliability Engineer analyzing a production incident.

{prompt}

Respond ONLY with valid JSON in this exact format:
{{
    "root_cause": "brief diagnosis",
    "confidence": 85,
    "recommended_action": "specific action to take",
    "evidence": "key evidence supporting diagnosis"
}}"""
            
            # Call Gemini with timeout using new API
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model='gemini-1.5-flash',
                    contents=full_prompt,
                    config={
                        'temperature': 0.1,
                        'max_output_tokens': 500
                    }
                ),
                timeout=self.config.llm_timeout_sec
            )
            
            # Parse response
            content = response.text
            result = json.loads(content)
            
            logger.info(
                "llm_classification_complete",
                root_cause=result.get("root_cause"),
                confidence=result.get("confidence")
            )
            
            # Pass to Surgeon for remediation decision (Circuit Breaker mode)
            try:
                from ..surgeon.remediation import get_surgeon
                from ..core.config import get_config
                
                surgeon = get_surgeon()
                config = get_config()
                
                remediation_decision = await surgeon.decide_remediation(
                    incident=incident_details,
                    analysis=result,
                    mode=config.mode
                )
                
                result["remediation"] = remediation_decision
                logger.info("remediation_decided", action=remediation_decision.get("action"))
            except Exception as surgeon_error:
                logger.error("surgeon_decision_failed", error=str(surgeon_error))
                result["remediation"] = {"action": "LOG_ONLY", "reason": "Surgeon unavailable"}
            
            return result
        
        except asyncio.TimeoutError:
            logger.error("llm_timeout", timeout=self.config.llm_timeout_sec)
            return {
                "root_cause": "TIMEOUT",
                "confidence": 0,
                "recommended_action": "HUMAN_HANDOFF",
                "evidence": "LLM classification timed out"
            }
        
        except Exception as e:
            logger.error("llm_classification_error", error=str(e))
            return {
                "root_cause": "ERROR",
                "confidence": 0,
                "recommended_action": "HUMAN_HANDOFF",
                "evidence": f"LLM error: {str(e)}"
            }


# Global LLM client
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
