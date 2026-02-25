"""
Vanguard Vaccine - AI-Powered Code Fix Generator
=================================================
Analyzes AI Analyzer output and generates code patches for automatic PR creation.

v2.0 upgrades (non-breaking):
  - Richer prompt: real file snippet + full stacktrace + AI root cause
  - Live snippet fetcher: reads ±30 lines from disk at reported line
  - Error-type confidence booster/suppressor
  - In-memory patch cache (avoids repeated Gemini calls per session)
  - Expanded RESTRICTED_FILES + hallucinated-import warning
"""

import logging
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Error-type confidence adjustments ────────────────────────────────────────
_CONFIDENCE_ADJUSTMENTS: Dict[str, int] = {
    # Localized, single-cause errors → boost
    "ImportError":          +8,
    "ModuleNotFoundError":  +8,
    "AttributeError":       +5,
    "NameError":            +5,
    "KeyError":             +3,
    "TypeError":            +3,
    "IndexError":           +3,
    "ZeroDivisionError":    +2,
    # Systemic / architecture issues → suppress
    "ConnectionError":      -10,
    "TimeoutError":         -10,
    "ServerTimeoutError":   -10,
    "RecursionError":       -15,
    "MemoryError":          -20,
    "PermissionError":      -8,
}

# How many lines of context either side of the error line to include
_SNIPPET_CONTEXT_LINES = 30


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

    VERSION = "2.0.0"

    # Safety limits
    MAX_LINES_CHANGED = 50
    MIN_CONFIDENCE = 85
    MAX_DAILY_FIXES = 5

    # Restricted files — never auto-patched
    RESTRICTED_FILES = [
        '.env',
        'config.py',
        'secrets.py',
        'requirements.txt',
        'Dockerfile',
        'cloudbuild.yaml',
        'cloudrun-service.yaml',
        'main.py',           # entry point — too risky
    ]

    RESTRICTED_PATHS = [
        'migrations/',
        '.git/',
    ]

    def __init__(self):
        self.enabled = os.getenv("VANGUARD_VACCINE_ENABLED", "false").lower() == "true"
        self.github_token = os.getenv("VANGUARD_VACCINE_GITHUB_TOKEN")
        self.repo = os.getenv("VANGUARD_VACCINE_REPO")
        self.base_branch = os.getenv("VANGUARD_VACCINE_BASE_BRANCH", "main")
        self.min_confidence = int(os.getenv("VANGUARD_VACCINE_MIN_CONFIDENCE", str(self.MIN_CONFIDENCE)))
        self.max_daily_fixes = int(os.getenv("VANGUARD_VACCINE_MAX_DAILY", str(self.MAX_DAILY_FIXES)))
        self._client = None
        self._daily_count = 0
        self._last_reset = datetime.now(timezone.utc).date()
        self._patch_cache: Dict[str, CodePatch] = {}  # fingerprint+hash → CodePatch
        self._repo_root = self._detect_repo_root()

        if self.enabled:
            logger.info(f"💉 VaccineGenerator v{self.VERSION} initialized (ENABLED)")
        else:
            logger.info(f"💉 VaccineGenerator v{self.VERSION} initialized (DISABLED)")

    @staticmethod
    def _detect_repo_root() -> str:
        """Detect repo root from common Cloud Run / local dev paths."""
        if os.path.exists("/app/vanguard"):
            return "/app"
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent / "vanguard").is_dir() and (parent / "backend").is_dir():
                return str(parent)
        return str(Path.cwd())

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

    # ── Confidence adjustment ─────────────────────────────────────────────────

    def _adjust_confidence(self, confidence: int, error_type: str) -> int:
        """
        Boost or suppress confidence based on error type.
        ImportError/AttributeError are localized and fixable → boost.
        ConnectionError/RecursionError are systemic → suppress.
        """
        for pattern, delta in _CONFIDENCE_ADJUSTMENTS.items():
            if pattern.lower() in error_type.lower():
                adjusted = confidence + delta
                if delta != 0:
                    logger.debug(f"💉 Confidence {confidence} → {adjusted} ({pattern}: {delta:+d})")
                return max(0, min(100, adjusted))
        return confidence

    # ── Gate check ────────────────────────────────────────────────────────────

    async def can_generate_fix(self, analysis: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if we should generate a fix for this analysis.
        Returns (can_generate, reason).
        """
        if not self.enabled:
            return False, "Vaccine disabled"

        self._reset_daily_counter()
        if self._daily_count >= self.max_daily_fixes:
            return False, f"Daily limit reached ({self.max_daily_fixes})"

        raw_confidence = analysis.get('confidence', 0)
        error_type = analysis.get('error_type', '') or analysis.get('root_cause', '')
        confidence = self._adjust_confidence(raw_confidence, error_type)

        if confidence < self.min_confidence:
            return False, f"Confidence too low ({confidence}% < {self.min_confidence}%)"

        code_refs = analysis.get('code_references', [])
        if not code_refs:
            return False, "No code references in analysis"

        # Check for restricted files
        for ref in code_refs:
            file_path = ref.get('file', '') if isinstance(ref, dict) else str(ref)

            for restricted in self.RESTRICTED_FILES:
                if file_path.endswith(restricted):
                    return False, f"Restricted file: {restricted}"

            for restricted_path in self.RESTRICTED_PATHS:
                if restricted_path in file_path:
                    return False, f"Restricted path: {restricted_path}"

        return True, "OK"

    # ── Patch cache ───────────────────────────────────────────────────────────

    def _cache_key(self, analysis: Dict[str, Any]) -> str:
        """Generate a cache key from fingerprint + analysis hash."""
        fp = analysis.get('fingerprint', '')
        content = f"{fp}:{analysis.get('root_cause','')}{analysis.get('error_message','')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_cached_patch(self, analysis: Dict[str, Any]) -> Optional[CodePatch]:
        """Return a previously generated patch for this analysis if cached."""
        key = self._cache_key(analysis)
        patch = self._patch_cache.get(key)
        if patch:
            logger.info(f"💉 Cache hit for {analysis.get('fingerprint','?')[:8]}")
        return patch

    def _store_patch(self, analysis: Dict[str, Any], patch: CodePatch):
        """Store a patch in the in-memory cache."""
        key = self._cache_key(analysis)
        self._patch_cache[key] = patch
        # Keep cache from growing unbounded
        if len(self._patch_cache) > 50:
            oldest = next(iter(self._patch_cache))
            del self._patch_cache[oldest]

    # ── Live file snippet ─────────────────────────────────────────────────────

    def _fetch_live_snippet(self, file_path: str, line_num: int) -> str:
        """
        Read ±N lines around `line_num` from the actual file on disk.
        Returns annotated lines (line_num: content).
        Falls back to empty string if file not found.
        """
        try:
            # Try both repo root and /app prefix
            candidates = [
                Path(self._repo_root) / file_path,
                Path("/app") / file_path,
                Path(file_path),
            ]
            for candidate in candidates:
                if candidate.exists():
                    lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
                    start = max(0, line_num - _SNIPPET_CONTEXT_LINES - 1)
                    end = min(len(lines), line_num + _SNIPPET_CONTEXT_LINES)
                    annotated = [
                        f"{'→ ' if i + 1 == line_num else '  '}{i + 1:4d}: {lines[i]}"
                        for i in range(start, end)
                    ]
                    return "\n".join(annotated)
        except Exception as e:
            logger.debug(f"💉 Live snippet fetch failed for {file_path}: {e}")
        return ""

    # ── Main generate ─────────────────────────────────────────────────────────

    async def generate_fix(self, analysis: Dict[str, Any]) -> Optional[CodePatch]:
        """
        Generate a code fix from AI analysis.

        Args:
            analysis: AI Analyzer output with code_references, root_cause, etc.

        Returns:
            CodePatch if successful, None if not possible
        """
        # Phase 5: feature flag gate
        try:
            from ..core.feature_flags import flag
            if not flag("VANGUARD_VACCINE_ENABLED"):
                logger.debug("💉 Vaccine disabled by feature flag VANGUARD_VACCINE_ENABLED")
                return None
        except ImportError:
            pass  # flag module unavailable — allow fallback to existing can_generate_fix checks

        can_generate, reason = await self.can_generate_fix(analysis)
        if not can_generate:
            logger.info(f"💉 Skipping fix generation: {reason}")
            return None

        # Check session cache first
        cached = self._get_cached_patch(analysis)
        if cached:
            return cached

        client = self._get_genai_client()
        if not client:
            logger.error("💉 Cannot generate fix: No GenAI client")
            return None

        try:
            code_refs = analysis.get('code_references', [])
            if not code_refs:
                return None

            ref = code_refs[0] if isinstance(code_refs[0], dict) else {"file": str(code_refs[0]), "line": 1}
            file_path = ref.get('file', '')
            line_start = ref.get('line', 1)
            line_end = ref.get('line_end', line_start + 10)
            stored_snippet = ref.get('snippet', '')

            # Fetch live file content from disk
            live_snippet = self._fetch_live_snippet(file_path, line_start)
            code_snippet = live_snippet or stored_snippet

            # Build richer prompt
            prompt = self._build_fix_prompt(analysis, ref, code_snippet, code_refs[1:])

            model = os.getenv("VANGUARD_LLM_MODEL", "gemini-2.0-flash")
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            fixed_code = self._parse_fix_response(response.text)
            if not fixed_code:
                logger.warning("💉 Could not parse fix from Gemini response")
                return None

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

            self._store_patch(analysis, patch)
            logger.info(f"💉 Generated fix for {file_path}:{line_start}-{line_end}")
            return patch

        except Exception as e:
            logger.error(f"💉 Fix generation failed: {e}")
            return None

    # ── Prompt builder ────────────────────────────────────────────────────────

    def _build_fix_prompt(
        self,
        analysis: Dict[str, Any],
        primary_ref: Dict[str, Any],
        code_snippet: str,
        secondary_refs: List[Any],
    ) -> str:
        """Build a rich prompt for Gemini that includes live code context."""

        # Stacktrace (last 25 lines, truncated)
        stacktrace = analysis.get('stacktrace', '') or analysis.get('traceback', '')
        if stacktrace:
            st_lines = stacktrace.strip().splitlines()
            if len(st_lines) > 25:
                stacktrace = "\n".join(["... (truncated)", *st_lines[-25:]])

        # AI-cached root cause and recommended steps if available
        ai_root_cause = analysis.get('root_cause', 'Unknown')
        ai_recommended = analysis.get('recommended_fix', '')
        if isinstance(ai_recommended, list):
            ai_recommended = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(ai_recommended))

        # Secondary context refs (other frames in the stacktrace)
        secondary_context = ""
        for ref in secondary_refs[:3]:
            if isinstance(ref, dict):
                sfile = ref.get('file', '')
                sline = ref.get('line', 0)
                ssnip = ref.get('snippet', '') or self._fetch_live_snippet(sfile, sline)
                if sfile and ssnip:
                    secondary_context += f"\n### Secondary context: {sfile}:{sline}\n```python\n{ssnip[:400]}\n```\n"

        return f"""You are a code repair specialist for the QuantSight NBA analytics backend (Python/FastAPI/Firestore).
Generate a minimal, surgical fix for the error below.

## ERROR
Type:    {analysis.get('error_type', 'Unknown')}
Message: {analysis.get('error_message', 'Unknown error')}

## ROOT CAUSE (AI analysis)
{ai_root_cause}

## RECOMMENDED APPROACH
{ai_recommended or '(none provided)'}

## STACKTRACE
```
{stacktrace or 'Not available'}
```

## PRIMARY FILE TO FIX: {primary_ref.get('file', '')} (error at line {primary_ref.get('line', '?')})
```python
{code_snippet or '(source not available)'}
```
{secondary_context}
## RULES
1. Change ONLY what is necessary to fix the error
2. Keep the same function signatures and return types
3. Add a short inline comment on the changed line(s) explaining what was fixed
4. Do NOT add new imports unless absolutely required
5. Do NOT restructure or reformat surrounding code

## OUTPUT FORMAT (required — no extra text)
```python
# fixed code here
```
"""

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse_fix_response(self, response_text: str) -> Optional[str]:
        """Extract code from Gemini response."""
        try:
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

    # ── Validator ─────────────────────────────────────────────────────────────

    def _validate_fix(self, original: str, fixed: str) -> bool:
        """Validate generated fix meets safety criteria."""
        if not fixed or not fixed.strip():
            return False

        original_lines = len(original.strip().split('\n')) if original else 0
        fixed_lines = len(fixed.strip().split('\n'))

        if fixed_lines > original_lines + self.MAX_LINES_CHANGED:
            logger.warning(f"💉 Fix too large: {fixed_lines} lines (max +{self.MAX_LINES_CHANGED})")
            return False

        # Syntax check
        try:
            compile(fixed, '<vaccine_fix>', 'exec')
        except SyntaxError as e:
            logger.warning(f"💉 Fix has syntax error: {e}")
            return False

        # Warn if LLM hallucinated a non-standard import
        self._check_import_hallucination(fixed)

        return True

    def _check_import_hallucination(self, code: str):
        """Warn (don't fail) if generated code imports a module not in requirements."""
        try:
            req_file = Path(self._repo_root) / "backend" / "requirements.txt"
            if not req_file.exists():
                req_file = Path(self._repo_root) / "requirements.txt"
            if not req_file.exists():
                return

            known = req_file.read_text(encoding="utf-8").lower()
            stdlib_safe = {
                "os", "sys", "re", "json", "logging", "datetime", "pathlib",
                "typing", "dataclasses", "hashlib", "asyncio", "collections",
                "functools", "itertools", "contextlib", "traceback",
            }

            import ast
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    for name in names:
                        root_pkg = name.split(".")[0].lower().replace("_", "-")
                        if root_pkg not in stdlib_safe and root_pkg not in known:
                            logger.warning(
                                f"💉 Possible hallucinated import: '{name}' not in requirements.txt"
                            )
        except Exception:
            pass  # Non-blocking

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get current Vaccine status."""
        self._reset_daily_counter()
        return {
            "version": self.VERSION,
            "enabled": self.enabled,
            "daily_fixes": self._daily_count,
            "daily_limit": self.max_daily_fixes,
            "min_confidence": self.min_confidence,
            "has_github_token": bool(self.github_token),
            "repo": self.repo,
            "base_branch": self.base_branch,
            "patch_cache_size": len(self._patch_cache),
            "repo_root": self._repo_root,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
_vaccine_instance: Optional[VaccineGenerator] = None


def get_vaccine() -> VaccineGenerator:
    """Get or create Vaccine singleton."""
    global _vaccine_instance
    if _vaccine_instance is None:
        _vaccine_instance = VaccineGenerator()
    return _vaccine_instance
