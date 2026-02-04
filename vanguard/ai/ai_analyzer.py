"""
Vanguard AI Analyzer
====================
Gemini-powered incident analysis with 24-hour caching.
Uses the new google.genai SDK.
"""
import json
import re
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pydantic import BaseModel
import logging

from .knowledge_base import CodebaseKnowledgeBase
from ..services.github_context import GitHubContextFetcher

logger = logging.getLogger(__name__)


class IncidentAnalysis(BaseModel):
    """AI-generated incident analysis"""
    fingerprint: str
    root_cause: str
    impact: str
    recommended_fix: List[str]
    ready_to_resolve: bool
    ready_reasoning: str
    confidence: int  # 0-100
    generated_at: str
    expires_at: str


class VanguardAIAnalyzer:
    """
    Gemini-powered incident analyzer with intelligent caching
    """
    
    def __init__(self):
        self.kb = CodebaseKnowledgeBase()
        self.github = GitHubContextFetcher()
        self.client = None
        self._genai_loaded = False
    
    def _lazy_load_genai(self):
        """Lazy load genai to prevent import errors from breaking vanguard"""
        if self._genai_loaded:
            return self.client is not None
        
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            logger.warning("GEMINI_API_KEY not set - AI analysis will be unavailable")
            self._genai_loaded = True
            return False
        
        try:
            from google import genai
            # Configure client with API key
            self.client = genai.Client(api_key=api_key)
            self._genai_loaded = True
            logger.info("Gemini AI initialized successfully (google.genai)")
            return True
        except ImportError as e:
            logger.error(f"google-genai package not installed: {e}")
            self._genai_loaded = True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self._genai_loaded = True
            return False
    
    async def analyze_incident(
        self,
        incident: Dict,
        storage,
        force_regenerate: bool = False
    ) -> IncidentAnalysis:
        """
        Generate AI analysis for an incident
        
        Args:
            incident: Incident dict from Firestore
            storage: Incident storage instance
            force_regenerate: Skip cache and regenerate
        
        Returns:
            IncidentAnalysis with AI-generated insights
        """
        fingerprint = incident["fingerprint"]
        
        # Lazy load genai if needed
        logger.info(f"[AI_DEBUG] Starting analysis for {fingerprint}")
        if not self._lazy_load_genai():
            logger.warning(f"[AI_DEBUG] Genai not available, returning fallback for {fingerprint}")
            return self._create_fallback_analysis(incident)
        
        # Check cache first (unless forced)
        if not force_regenerate:
            cached = await self._get_cached_analysis(fingerprint, storage)
            if cached:
                logger.info(f"Using cached analysis for {fingerprint}")
                return cached
        
        logger.info(f"[AI_DEBUG] Generating new AI analysis for {fingerprint}")
        logger.info(f"[AI_DEBUG] Incident details - endpoint: {incident.get('endpoint')}, error: {incident.get('error_type')}")
        
        # Get codebase context
        context = self.kb.get_context_for_endpoint(incident["endpoint"])
        logger.info(f"[AI_DEBUG] Retrieved codebase context: {len(context)} chars")
        
        # Fetch GitHub code context for anti-hallucination
        try:
            code_contexts = self.github.fetch_context(
                incident.get('endpoint', ''),
                incident.get('error_type', '')
            )
            logger.info(f"[AI_DEBUG] Fetched {len(code_contexts)} code files from GitHub")
        except Exception as e:
            logger.error(f"[AI_DEBUG] GitHub fetch failed: {e}")
            code_contexts = []
        
        # Build AI prompt with code context
        logger.info(f"[AI_DEBUG] Building prompt with {len(code_contexts)} code contexts")
        prompt = await self._build_analysis_prompt(incident, context, code_contexts)
        logger.info(f"[AI_DEBUG] Prompt built: {len(prompt)} chars")
        
        try:
            # Generate analysis using new API
            logger.info(f"[AI_DEBUG] Calling Gemini API with model gemini-2.0-flash-exp")
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            logger.info(f"[AI_DEBUG] Gemini API responded successfully")
            
            # Parse AI response
            analysis = self._parse_ai_response(response.text, incident)
            
            # Cache for 24 hours
            await self._cache_analysis(analysis, storage)
            
            return analysis
        except Exception as e:
            logger.error(f"[AI_DEBUG] AI analysis failed with error: {e}")
            logger.error(f"[AI_DEBUG] Error type: {type(e).__name__}")
            import traceback
            logger.error(f"[AI_DEBUG] Full traceback:\n{traceback.format_exc()}")
            return self._create_fallback_analysis(incident)
    
    async def _build_analysis_prompt(self, incident: Dict, context: str, code_contexts: List[Dict] = None) -> str:
        """Build comprehensive analysis prompt for Gemini"""
        
        # Get metadata
        metadata = incident.get("metadata", {})
        traceback = metadata.get("traceback", "N/A")
        if len(traceback) > 1500:
            traceback = traceback[:1500] + "\n... (truncated)"
        
        prompt = f"""
You are analyzing a production incident in the QuantSight NBA analytics system.

{context}

## INCIDENT DETAILS
- **Fingerprint**: {incident['fingerprint'][:16]}...
- **Error Type**: {incident['error_type']}
- **Endpoint**: {incident['endpoint']}
- **Occurrences**: {incident['occurrence_count']}
- **Severity**: {incident['severity']}
- **Labels**: {json.dumps(incident.get('labels', {}))}
- **First Seen**: {incident['first_seen']}
- **Last Seen**: {incident['last_seen']}

## STACK TRACE
{traceback}

## CODEBASE CONTEXT (Source Code with Line Numbers)
{self._format_code_contexts(code_contexts or [])}

## YOUR TASK
Provide a concise incident analysis in the following JSON format:

{{
  "root_cause": "2-3 sentence explanation of what's broken",
  "impact": "1 sentence on who/what is affected",
  "recommended_fix": ["specific step 1", "specific step 2", "specific step 3"],
  "ready_to_resolve": false,
  "ready_reasoning": "Why it's not ready OR why it is",
  "confidence": 85
}}

## READINESS CRITERIA
Set `ready_to_resolve: true` ONLY if:
1. Error occurred more than 30 minutes ago
2. No recent occurrences (check last_seen vs current time)
3. Code changes likely deployed (check recent git commits)

Otherwise set `ready_to_resolve: false` with clear reasoning.

**IMPORTANT**: Return ONLY valid JSON, no extra text.
"""
        return prompt.strip()
    
    def _parse_ai_response(self, response: str, incident: Dict) -> IncidentAnalysis:
        """Parse Gemini's JSON response"""
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        
        if not json_match:
            raise ValueError(f"AI response is not valid JSON: {response[:200]}")
        
        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI JSON: {e}")
        
        # Validate required fields
        required = ["root_cause", "impact", "recommended_fix", "ready_to_resolve", "ready_reasoning", "confidence"]
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Create analysis object
        now = datetime.utcnow()
        expires = now + timedelta(hours=24)
        
        return IncidentAnalysis(
            fingerprint=incident["fingerprint"],
            root_cause=data["root_cause"],
            impact=data["impact"],
            recommended_fix=data["recommended_fix"] if isinstance(data["recommended_fix"], list) else [data["recommended_fix"]],
            ready_to_resolve=bool(data["ready_to_resolve"]),
            ready_reasoning=data["ready_reasoning"],
            confidence=int(data["confidence"]),
            generated_at=now.isoformat() + "Z",
            expires_at=expires.isoformat() + "Z"
        )
    
    def _create_fallback_analysis(self, incident: Dict) -> IncidentAnalysis:
        """Create basic analysis when AI is unavailable"""
        now = datetime.utcnow()
        expires = now + timedelta(hours=24)
        
        return IncidentAnalysis(
            fingerprint=incident["fingerprint"],
            root_cause=f"{incident['error_type']} on {incident['endpoint']} - AI analysis unavailable",
            impact="Unable to assess impact without AI analysis",
            recommended_fix=[
                "Check error logs for details",
                "Review recent code changes",
                "Test endpoint manually"
            ],
            ready_to_resolve=False,
            ready_reasoning="AI analysis unavailable - manual review required",
            confidence=0,
            generated_at=now.isoformat() + "Z",
            expires_at=expires.isoformat() + "Z"
        )
    
    async def _cache_analysis(self, analysis: IncidentAnalysis, storage):
        """Store analysis in Firestore with 24hr TTL"""
        try:
            doc_ref = storage.firestore_client.collection("vanguard_analysis").document(
                analysis.fingerprint
            )
            
            await doc_ref.set(analysis.dict())
            logger.info(f"Cached analysis for {analysis.fingerprint} (expires: {analysis.expires_at})")
        except Exception as e:
            logger.warning(f"Failed to cache analysis: {e}")
    
    async def _get_cached_analysis(
        self,
        fingerprint: str,
        storage
    ) -> Optional[IncidentAnalysis]:
        """Retrieve cached analysis if not expired"""
        try:
            doc_ref = storage.firestore_client.collection("vanguard_analysis").document(fingerprint)
            doc = await doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            
            # Check expiration
            expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
            if expires_at < datetime.utcnow():
                logger.info(f"Cached analysis expired for {fingerprint}")
                return None
            
            return IncidentAnalysis(**data)
        except Exception as e:
            logger.warning(f"Failed to retrieve cached analysis: {e}")
            return None
    
    def _format_code_contexts(self, code_contexts: List) -> str:
        """Format GitHub code contexts with line numbers for anti-hallucination"""
        if not code_contexts:
            return "No source code available - endpoint not mapped."
        
        sections = []
        for ctx in code_contexts:
            recent_commits_text = "\n".join(
                f"- {commit}" for commit in (ctx.recent_commits[:3] if ctx.recent_commits else [])
            ) or "- No recent commits"
            
            section = f"""
### File: `{ctx.file_path}` (Lines {ctx.start_line}-{ctx.end_line})

Recent commits:
{recent_commits_text}

```python
{ctx.format_for_prompt()}
```
"""
            sections.append(section.strip())
        
        return "\n\n".join(sections)
