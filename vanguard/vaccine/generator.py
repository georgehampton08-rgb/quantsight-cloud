"""
Vanguard Vaccine - AI-Powered Code Fix Generator
=================================================
Analyzes AI Analyzer output and generates code patches for automatic PR creation.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CodePatch:
    """Represents a generated code fix."""
    fingerprint: str
    file_path: str
    original_code: str
    fixed_code: str
    explanation: str
    confidence: float
    created_at: str
    line_start: int = 0
    line_end: int = 0


class VaccineGenerator:
    """
    Generates code fixes from AI Analyzer output.
    Uses Gemini to create minimal, safe patches.
    """
    
    VERSION = "1.0.0"
    
    # Safety limits
    MAX_LINES_CHANGED = 50
    MIN_CONFIDENCE = 85  # Only generate fixes for high-confidence analysis
    MAX_DAILY_FIXES = 5
    
    # Restricted files that should never be auto-patched
    RESTRICTED_FILES = [
        '.env',
        'config.py',
        'secrets.py',
        'requirements.txt',
        'Dockerfile',
        'cloudbuild.yaml',
    ]
    
    RESTRICTED_PATHS = [
        'migrations/',
        'scripts/',
        '.git/',
    ]
    
    def __init__(self):
        self.enabled = os.getenv("VANGUARD_VACCINE_ENABLED", "false").lower() == "true"
        self.github_token = os.getenv("VANGUARD_VACCINE_GITHUB_TOKEN")
        self.repo = os.getenv("VANGUARD_VACCINE_REPO")
        self.base_branch = os.getenv("VANGUARD_VACCINE_BASE_BRANCH", "main")
        self._client = None
        self._daily_count = 0
        self._last_reset = datetime.now(timezone.utc).date()
        
        if self.enabled:
            logger.info(f"💉 VaccineGenerator v{self.VERSION} initialized (ENABLED)")
        else:
            logger.info(f"💉 VaccineGenerator v{self.VERSION} initialized (DISABLED)")
    
    def _get_genai_client(self):
        """Lazy-load Gemini client."""
        if not self._client:
            try:
                from google import genai
                api_key = os.getenv("GEMINI_API_KEY")
                if api_key:
                    self._client = genai.Client(api_key=api_key)
                    logger.debug("Vaccine GenAI client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize GenAI: {e}")
        return self._client
    
    def _reset_daily_counter(self):
        """Reset daily fix counter if new day."""
        today = datetime.now(timezone.utc).date()
        if today > self._last_reset:
            self._daily_count = 0
            self._last_reset = today
    
    async def can_generate_fix(self, analysis: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if we should generate a fix for this analysis.
        Returns (can_generate, reason).
        """
        if not self.enabled:
            return False, "Vaccine disabled"
        
        self._reset_daily_counter()
        if self._daily_count >= self.MAX_DAILY_FIXES:
            return False, f"Daily limit reached ({self.MAX_DAILY_FIXES})"
        
        confidence = analysis.get('confidence', 0)
        if confidence < self.MIN_CONFIDENCE:
            return False, f"Confidence too low ({confidence}% < {self.MIN_CONFIDENCE}%)"
        
        code_refs = analysis.get('code_references', [])
        if not code_refs:
            return False, "No code references in analysis"
        
        # Check for restricted files
        for ref in code_refs:
            file_path = ref.get('file', '')
            
            # Check restricted filenames
            for restricted in self.RESTRICTED_FILES:
                if file_path.endswith(restricted):
                    return False, f"Restricted file: {restricted}"
            
            # Check restricted paths
            for restricted_path in self.RESTRICTED_PATHS:
                if restricted_path in file_path:
                    return False, f"Restricted path: {restricted_path}"
        
        return True, "OK"
    
    async def generate_fix(self, analysis: Dict[str, Any]) -> Optional[CodePatch]:
        """
        Generate a code fix from AI analysis.
        
        Args:
            analysis: AI Analyzer output with code_references, root_cause, etc.
            
        Returns:
            CodePatch if successful, None if not possible
        """
        can_generate, reason = await self.can_generate_fix(analysis)
        if not can_generate:
            logger.info(f"💉 Skipping fix generation: {reason}")
            return None
        
        client = self._get_genai_client()
        if not client:
            logger.error("💉 Cannot generate fix: No GenAI client")
            return None
        
        try:
            # Extract first code reference
            code_refs = analysis.get('code_references', [])
            if not code_refs:
                return None
            
            ref = code_refs[0]
            file_path = ref.get('file', '')
            line_start = ref.get('line', 1)
            line_end = ref.get('line_end', line_start + 10)
            code_snippet = ref.get('snippet', '')
            
            # Build prompt
            prompt = self._build_fix_prompt(analysis, ref)
            
            # Call Gemini
            model = os.getenv("VANGUARD_LLM_MODEL", "gemini-2.0-flash")
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            
            fixed_code = self._parse_fix_response(response.text)
            if not fixed_code:
                logger.warning("💉 Could not parse fix from Gemini response")
                return None
            
            # Validate fix
            if not self._validate_fix(code_snippet, fixed_code):
                logger.warning("💉 Generated fix failed validation")
                return None
            
            self._daily_count += 1
            
            patch = CodePatch(
                fingerprint=analysis.get('fingerprint', 'unknown'),
                file_path=file_path,
                original_code=code_snippet,
                fixed_code=fixed_code,
                explanation=analysis.get('recommended_fix', 'AI-generated fix'),
                confidence=analysis.get('confidence', 0),
                created_at=datetime.now(timezone.utc).isoformat(),
                line_start=line_start,
                line_end=line_end
            )
            
            logger.info(f"💉 Generated fix for {file_path}:{line_start}-{line_end}")
            return patch
            
        except Exception as e:
            logger.error(f"💉 Fix generation failed: {e}")
            return None
    
    def _build_fix_prompt(self, analysis: Dict[str, Any], code_ref: Dict[str, Any]) -> str:
        """Build prompt for Gemini to generate fix."""
        return f"""You are a code repair specialist. Generate a minimal fix for this error.

ERROR:
{analysis.get('error_message', 'Unknown error')}

ROOT CAUSE (from AI analysis):
{analysis.get('root_cause', 'Unknown')}

AFFECTED CODE ({code_ref.get('file', '')}:{code_ref.get('line', 0)}):
```python
{code_ref.get('snippet', '')}
```

RECOMMENDED FIX APPROACH:
{analysis.get('recommended_fix', 'Fix the error')}

Generate ONLY the fixed code block. No explanations.
The fix should be:
1. Minimal - change only what's necessary
2. Safe - no breaking changes
3. Include inline comment explaining fix

Output format (REQUIRED):
```python
# Fixed code here
```
"""
    
    def _parse_fix_response(self, response_text: str) -> Optional[str]:
        """Extract code from Gemini response."""
        try:
            # Look for Python code block
            if "```python" in response_text:
                start = response_text.index("```python") + 9
                end = response_text.index("```", start)
                return response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.index("```") + 3
                end = response_text.index("```", start)
                return response_text[start:end].strip()
            return None
        except ValueError:
            return None
    
    def _validate_fix(self, original: str, fixed: str) -> bool:
        """Validate generated fix meets safety criteria."""
        if not fixed or not fixed.strip():
            return False
        
        # Check line count
        original_lines = len(original.strip().split('\n')) if original else 0
        fixed_lines = len(fixed.strip().split('\n'))
        
        if fixed_lines > original_lines + self.MAX_LINES_CHANGED:
            logger.warning(f"💉 Fix too large: {fixed_lines} lines (max +{self.MAX_LINES_CHANGED})")
            return False
        
        # Basic syntax check (try to compile)
        try:
            compile(fixed, '<vaccine_fix>', 'exec')
        except SyntaxError as e:
            logger.warning(f"💉 Fix has syntax error: {e}")
            return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current Vaccine status."""
        self._reset_daily_counter()
        return {
            "version": self.VERSION,
            "enabled": self.enabled,
            "daily_fixes": self._daily_count,
            "daily_limit": self.MAX_DAILY_FIXES,
            "min_confidence": self.MIN_CONFIDENCE,
            "has_github_token": bool(self.github_token),
            "repo": self.repo,
            "base_branch": self.base_branch
        }


# Singleton instance
_vaccine_instance: Optional[VaccineGenerator] = None


def get_vaccine() -> VaccineGenerator:
    """Get or create Vaccine singleton."""
    global _vaccine_instance
    if _vaccine_instance is None:
        _vaccine_instance = VaccineGenerator()
    return _vaccine_instance
