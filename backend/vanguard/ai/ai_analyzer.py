"""
Vanguard AI Analyzer
====================
Gemini-powered incident analysis with 24-hour caching.
Uses the new google.genai SDK.
"""
import hashlib
import json
import re
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from pydantic import BaseModel
import logging

from .knowledge_base import CodebaseKnowledgeBase
from ..services.github_context import GitHubContextFetcher
from ..core.config import get_vanguard_config

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
    cached: bool = False
    code_references: List[str] = []
    prompt_version: str = "1.0"
    model_id: str = ""
    input_hash: str = ""        # Hash of normalised analysis input
    incident_last_seen: str = ""  # last_seen at analysis time -- stale if incident recurred


class VanguardAIAnalyzer:
    """
    Gemini-powered incident analyzer with intelligent caching
    """

    PROMPT_VERSION = "1.0"  # Bump to invalidate cached analyses when prompt changes

    def __init__(self):
        self.kb = CodebaseKnowledgeBase()
        self.github = GitHubContextFetcher()
        self.client = None
        self._genai_loaded = False

        # Load config for model name
        config = get_vanguard_config()
        self.model_name = config.llm_model

    ANALYSIS_PROMPT_TEMPLATE = """
You are Vanguard Sovereign - QuantSight's AI incident analyst. Provide detailed technical analysis in under 600 words.

{context}

## INCIDENT TIMELINE
**Fingerprint:** `{fingerprint}`
**Error:** `{error_type}` on `{endpoint}`
**Severity:** {severity} | **Hit Count:** {occurrence_count}
**First Seen:** {first_seen}
**Last Seen:** {last_seen}
**Current Time:** {system_time}

## STACK TRACE
{traceback}

## CODE CONTEXT
{code_contexts}

## SYSTEM STATE
**Mode:** {vanguard_mode} | **Revision:** {revision}

---

Provide detailed technical analysis in JSON format. Be specific about:
- Exact component/function that failed
- Technical chain of causation
- Concrete impact metrics
- Actionable fixes with file/line references where possible

{{
  "root_cause": "<2-3 sentences. Name specific files, functions, or config. Explain the technical chain: X called Y which failed because Z.>",
  "impact": "<1-2 sentences. Quantify: how many users, which features, what degradation. Concrete metrics.>",
  "recommended_fix": [
    "IMMEDIATE: <tactical action to mitigate impact right now>",
    "ROOT FIX: <specific code/config change with file paths if known>",
    "PREVENTION: <monitoring, tests, or architecture change to prevent recurrence>"
  ],
  "timeline_analysis": "<1-2 sentences analyzing the gap between first_seen and last_seen. Is this recurring, intermittent, or one-time? Pattern insights.>",
  "ready_to_resolve": false,
  "ready_reasoning": "<Specific reason based on timeline. Example: 'Last occurrence 8min ago, need 30min cold period' or 'No occurrences for 45min + evidence of fix in rev XYZ'>",
  "confidence": 85
}}

**Resolution Criteria:** Set ready_to_resolve=true ONLY when: (1) 30+ minutes since last_seen with zero new hits, AND (2) evidence suggests root cause addressed (new deployment, config fix, etc).

Return ONLY valid JSON. No markdown, no extra text.
"""
    
    def _lazy_load_genai(self):
        """Lazy load genai to prevent import errors from breaking vanguard"""
        if self._genai_loaded:
            return self.client is not None
        
        # Try both GEMINI_API_KEY and GOOGLE_API_KEY (SDK default)
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        
        # Debug: Log which env vars are present (masked)
        gemini_present = "SET" if os.getenv("GEMINI_API_KEY") else "NOT SET"
        google_present = "SET" if os.getenv("GOOGLE_API_KEY") else "NOT SET"
        logger.info(f"[AI_DEBUG] GEMINI_API_KEY: {gemini_present}, GOOGLE_API_KEY: {google_present}")
        
        if not api_key:
            logger.warning("Neither GEMINI_API_KEY nor GOOGLE_API_KEY set - AI analysis will be unavailable")
            self._genai_loaded = True
            return False
        
        try:
            from google import genai
            # Configure client with API key
            self.client = genai.Client(api_key=api_key)
            self._genai_loaded = True
            logger.info(f"Gemini AI initialized successfully with model: {self.model_name}")
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
        force_regenerate: bool = False,
        **kwargs  # Accept system_context and other parameters
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
        
        # Build AI prompt with code context and system context
        logger.info(f"[AI_DEBUG] Building prompt with {len(code_contexts)} code contexts")
        prompt = await self._build_analysis_prompt(
            incident=incident, 
            context=context, 
            code_contexts=code_contexts,
            system_context=kwargs.get('system_context')
        )
        logger.info(f"[AI_DEBUG] Prompt built: {len(prompt)} chars")
        
        # Compute input hash for cache integrity
        input_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        # New google-genai SDK uses bare model name (no "models/" prefix)
        model_id = self.model_name

        try:
            # Generate analysis using new API
            logger.info(f"[AI_DEBUG] Calling Gemini API with model {model_id}")
            response = self.client.models.generate_content(
                model=model_id,
                contents=prompt
            )
            logger.info(f"[AI_DEBUG] Gemini API responded successfully")

            # Parse AI response
            analysis = self._parse_ai_response(response.text, incident)
            analysis.model_id = model_id
            analysis.input_hash = input_hash
            analysis.incident_last_seen = str(incident.get("last_seen", ""))

            # Cache for 24 hours
            await self._cache_analysis(analysis, storage)
            
            return analysis
        except Exception as e:
            logger.error(f"[AI_DEBUG] AI analysis failed with error: {e}")
            logger.error(f"[AI_DEBUG] Error type: {type(e).__name__}")
            import traceback
            logger.error(f"[AI_DEBUG] Full traceback:\n{traceback.format_exc()}")
            return self._create_fallback_analysis(incident)
    
    async def _build_analysis_prompt(self, incident: Dict, context: str, code_contexts: List[Dict] = None, **kwargs) -> str:
        """Build comprehensive analysis prompt for Gemini"""
        
        # Get metadata
        metadata = incident.get("metadata", {})
        traceback = metadata.get("traceback", "N/A")
        if len(traceback) > 1500:
            traceback = traceback[:1500] + "\n... (truncated)"
        
        prompt = self.ANALYSIS_PROMPT_TEMPLATE.format(
            context=context,
            fingerprint=incident['fingerprint'][:16] + "...",
            error_type=incident['error_type'],
            endpoint=incident['endpoint'],
            occurrence_count=incident.get('occurrence_count', 1),
            severity=incident['severity'],
            labels=json.dumps(incident.get('labels', {})),
            first_seen=incident.get('first_seen', incident.get('timestamp', 'unknown')),
            last_seen=incident.get('last_seen', incident.get('timestamp', 'unknown')),
            traceback=traceback,
            code_contexts=self._format_code_contexts(code_contexts or []),
            system_time=datetime.now(timezone.utc).isoformat(),
            vanguard_mode=kwargs.get('system_context', {}).get('mode', 'UNKNOWN'),
            revision=kwargs.get('system_context', {}).get('revision', 'local'),
            available_routes=json.dumps(kwargs.get('system_context', {}).get('routes', []))
        )
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
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)

        # Extract code references from recommended_fix text (file paths)
        code_refs = []
        fix_list = data["recommended_fix"] if isinstance(data["recommended_fix"], list) else [data["recommended_fix"]]
        for fix_text in fix_list:
            refs = re.findall(r'[\w/]+\.(?:py|ts|js|tsx|jsx)\b', str(fix_text))
            code_refs.extend(refs)

        return IncidentAnalysis(
            fingerprint=incident["fingerprint"],
            root_cause=data["root_cause"],
            impact=data["impact"],
            recommended_fix=fix_list,
            ready_to_resolve=bool(data["ready_to_resolve"]),
            ready_reasoning=data["ready_reasoning"],
            confidence=int(data["confidence"]),
            generated_at=now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            expires_at=expires.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            cached=False,
            code_references=list(set(code_refs)),
            prompt_version=self.PROMPT_VERSION
        )

    def _create_fallback_analysis(self, incident: Dict) -> IncidentAnalysis:
        """Create basic analysis when AI is unavailable"""
        now = datetime.now(timezone.utc)
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
            generated_at=now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            expires_at=expires.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            cached=False,
            prompt_version=self.PROMPT_VERSION
        )
    
    
    async def _cache_analysis(self, analysis: IncidentAnalysis, storage):
        """Store analysis in the incident's ai_analysis field"""
        try:
            # Update the incident with the analysis using the new update_incident method
            success = await storage.update_incident(
                analysis.fingerprint, 
                {'ai_analysis': analysis.dict()}
            )
            if success:
                logger.info(f"Saved analysis to incident {analysis.fingerprint} (expires: {analysis.expires_at})")
            else:
                logger.warning(f"Failed to update incident {analysis.fingerprint} with analysis")
        except Exception as e:
            logger.warning(f"Failed to cache analysis: {e}")
    
    async def _get_cached_analysis(
        self,
        fingerprint: str,
        storage
    ) -> Optional[IncidentAnalysis]:
        """Retrieve cached analysis from incident's ai_analysis field"""
        try:
            incident = await storage.load(fingerprint)
            if not incident or 'ai_analysis' not in incident:
                return None

            data = incident['ai_analysis']

            # Check expiration
            # Robust ISO parse: handle both "Z" suffix and "+00:00" suffix
            expires_raw = data["expires_at"].rstrip("Z")
            if "+" not in expires_raw and not expires_raw.endswith("+00:00"):
                expires_raw += "+00:00"
            expires_at = datetime.fromisoformat(expires_raw)
            if expires_at < datetime.now(timezone.utc):
                logger.info(f"Cached analysis expired for {fingerprint}")
                return None

            # Check prompt version -- invalidate if prompt changed
            if data.get("prompt_version", "0") != self.PROMPT_VERSION:
                logger.info(f"Cached analysis has stale prompt version for {fingerprint}")
                return None

            # Check model_id -- invalidate if model changed
            expected_model = self.model_name
            if data.get("model_id") and data["model_id"] != expected_model:
                logger.info(f"Cached analysis used different model for {fingerprint}")
                return None

            # Check incident_last_seen -- invalidate if incident recurred since analysis
            cached_last_seen = data.get("incident_last_seen", "")
            current_last_seen = str(incident.get("last_seen", ""))
            if cached_last_seen and current_last_seen and cached_last_seen != current_last_seen:
                logger.info(f"Incident {fingerprint} recurred since cached analysis (cached: {cached_last_seen}, now: {current_last_seen})")
                return None

            analysis = IncidentAnalysis(**data)
            analysis.cached = True
            return analysis
        except Exception as e:
            logger.warning(f"Failed to retrieve cached analysis: {e}")
            return None
    
    @staticmethod
    def extract_files_from_traceback(incident: Dict) -> List[str]:
        """Parse Python traceback lines for file paths (high-confidence related_files).

        Looks for standard traceback patterns like:
            File "/app/vanguard/api/admin_routes.py", line 42, in func
        Returns de-duplicated list of relative file paths.
        """
        tb = incident.get("metadata", {}).get("traceback", "")
        if not tb:
            return []

        # Standard CPython traceback: File "...", line N
        raw = re.findall(r'File "([^"]+)"', tb)
        seen: set = set()
        result: List[str] = []
        for path in raw:
            # Normalise: strip leading /app/ or /workspace/ prefixes
            rel = re.sub(r'^/(app|workspace|src)/', '', path)
            # Skip stdlib / site-packages
            if "site-packages" in rel or rel.startswith("/usr") or rel.startswith("lib/python"):
                continue
            if rel not in seen:
                seen.add(rel)
                result.append(rel)
        return result

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


# Singleton Instance
_ai_analyzer = None

def get_ai_analyzer() -> VanguardAIAnalyzer:
    "Get the global AI Analyzer instance."
    global _ai_analyzer
    if _ai_analyzer is None:
        _ai_analyzer = VanguardAIAnalyzer()
    return _ai_analyzer
