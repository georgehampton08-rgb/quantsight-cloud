"""
Vanguard Vaccine — Plan Engine
==============================
Given an incident fingerprint, produces a structured remediation plan:
  - root cause bucket
  - candidate files with confidence
  - verification + rollback steps
  - risk score
"""

import logging
import re
import traceback as tb_module
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


# ── Allowed edit roots (Cloud-only scope) ────────────────────────────────────
ALLOWED_ROOTS = [
    "vanguard/",
    "backend/vanguard/",
    "scripts/",
    "shared_core/",
]

# Known root-cause buckets — expanded
ROOT_CAUSE_BUCKETS = {
    # Python exceptions
    "ImportError":          "missing_dependency",
    "ModuleNotFoundError":  "missing_dependency",
    "AttributeError":       "api_contract_drift",
    "KeyError":             "schema_drift",
    "TypeError":            "type_mismatch",
    "ValueError":           "invalid_input",
    "FileNotFoundError":    "missing_resource",
    "ConnectionError":      "network_failure",
    "TimeoutError":         "network_failure",
    "RuntimeError":         "runtime_assertion",
    "PermissionError":      "iam_or_acl",
    "RecursionError":       "infinite_loop",
    "ZeroDivisionError":    "numeric_edge_case",
    "UnicodeDecodeError":   "encoding_drift",
    "JSONDecodeError":      "schema_drift",
    "json.JSONDecodeError":  "schema_drift",
    "StopIteration":        "iterator_exhausted",
    "OverflowError":        "numeric_edge_case",
    "requests.exceptions":  "network_failure",
    # HTTP status codes
    "404":  "missing_route",
    "400":  "validation_failure",
    "500":  "internal_error",
    "422":  "validation_failure",
    "429":  "rate_limit",
    "503":  "service_unavailable",
}

# Root causes that carry extra risk — requires human review
_HIGH_RISK_BUCKETS = {"infinite_loop", "iam_or_acl", "runtime_assertion"}



@dataclass
class FixCandidate:
    """A single file/symbol identified as needing a fix."""
    file: str
    symbol: str
    confidence: float  # 0.0 – 1.0
    reason: str


@dataclass
class VaccinePlan:
    """Structured remediation plan for a single incident."""
    fingerprint: str
    root_cause_bucket: str
    fix_candidates: List[FixCandidate]
    proposed_changes_summary: str
    verification_plan: List[str]
    rollback_plan: List[str]
    risk_score: float  # 0.0 (safe) – 1.0 (dangerous)
    requires_human_approval: bool = True
    created_at: str = ""
    incident_summary: str = ""
    ai_analysis_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fix_candidates"] = [asdict(fc) for fc in self.fix_candidates]
        return d


class VaccinePlanEngine:
    """
    Transforms an incident document into a structured VaccinePlan.

    Mapping priority:
      1. Stacktrace → extract file:line references directly
      2. Fallback → GitHubContextFetcher.ENDPOINT_MAP
      3. Optional AI analysis cached on the incident
    """

    VERSION = "1.0.0"

    def __init__(self):
        self._endpoint_map: Optional[Dict[str, str]] = None
        logger.info(f"VaccinePlanEngine v{self.VERSION} initialized")

    def _get_endpoint_map(self) -> Dict[str, str]:
        """Lazy-load ENDPOINT_MAP from GitHubContextFetcher."""
        if self._endpoint_map is None:
            try:
                from vanguard.services.github_context import GitHubContextFetcher
                self._endpoint_map = GitHubContextFetcher.ENDPOINT_MAP
            except Exception:
                self._endpoint_map = {}
        return self._endpoint_map

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_plan(self, incident: Dict[str, Any]) -> VaccinePlan:
        """
        Generate a remediation plan for a single incident.

        Args:
            incident: Firestore incident document dict

        Returns:
            VaccinePlan with fix candidates, verification, and rollback
        """
        fingerprint = incident.get("fingerprint", "unknown")
        error_type = incident.get("error_type", "")
        endpoint = incident.get("endpoint", "")
        stacktrace = incident.get("traceback", "") or incident.get("stacktrace", "") or ""
        error_message = incident.get("error_message", "")
        severity = incident.get("severity", "YELLOW")
        ai_analysis = incident.get("ai_analysis", None)

        # 1. Classify root cause
        root_cause = self._classify_root_cause(error_type, error_message)

        # 2. Extract fix candidates
        candidates = self._extract_candidates(
            stacktrace=stacktrace,
            endpoint=endpoint,
            error_type=error_type,
            ai_analysis=ai_analysis,
        )

        # 3. Build summary
        summary = self._build_summary(error_type, error_message, candidates)

        # 4. Build verification plan
        verification = self._build_verification_plan(endpoint, candidates)

        # 5. Build rollback plan
        rollback = self._build_rollback_plan(candidates)

        # 6. Calculate risk
        risk = self._calculate_risk(severity, candidates, root_cause)

        return VaccinePlan(
            fingerprint=fingerprint,
            root_cause_bucket=root_cause,
            fix_candidates=candidates,
            proposed_changes_summary=summary,
            verification_plan=verification,
            rollback_plan=rollback,
            risk_score=risk,
            requires_human_approval=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            incident_summary=f"{error_type}: {error_message[:120]}",
            ai_analysis_used=ai_analysis is not None,
        )

    # ── Root cause classification ─────────────────────────────────────────────

    def _classify_root_cause(self, error_type: str, error_message: str) -> str:
        """Classify the error into a root-cause bucket."""
        # Direct error type match
        for pattern, bucket in ROOT_CAUSE_BUCKETS.items():
            if pattern in error_type:
                return bucket

        # HTTP status code in message
        for code in ["404", "400", "500", "422", "429"]:
            if code in error_message:
                return ROOT_CAUSE_BUCKETS.get(code, "unknown")

        return "unknown"

    # ── Candidate extraction ──────────────────────────────────────────────────

    def _extract_candidates(
        self,
        stacktrace: str,
        endpoint: str,
        error_type: str,
        ai_analysis: Optional[Dict] = None,
    ) -> List[FixCandidate]:
        """
        Extract candidate files from stacktrace, endpoint map, and AI analysis.
        Priority: stacktrace > AI analysis > ENDPOINT_MAP
        """
        candidates: List[FixCandidate] = []
        seen_files: set = set()

        # Strategy 1: Parse stacktrace for file:line references
        if stacktrace:
            for fc in self._parse_stacktrace(stacktrace):
                if fc.file not in seen_files and self._is_allowed_path(fc.file):
                    candidates.append(fc)
                    seen_files.add(fc.file)

        # Strategy 2: Use AI analysis code_references if available
        if ai_analysis:
            for ref in ai_analysis.get("code_references", []):
                file_path = ref.get("file", "")
                if file_path and file_path not in seen_files and self._is_allowed_path(file_path):
                    candidates.append(FixCandidate(
                        file=file_path,
                        symbol=ref.get("function", ref.get("symbol", "unknown")),
                        confidence=min(ref.get("confidence", 0.6), 1.0),
                        reason=f"AI analysis: {ref.get('context', 'referenced in analysis')}",
                    ))
                    seen_files.add(file_path)

        # Strategy 3: ENDPOINT_MAP fallback
        if not candidates and endpoint:
            ep_map = self._get_endpoint_map()
            mapped_file = self._map_endpoint(endpoint, ep_map)
            if mapped_file and mapped_file not in seen_files:
                candidates.append(FixCandidate(
                    file=mapped_file,
                    symbol="endpoint_handler",
                    confidence=0.4,
                    reason=f"ENDPOINT_MAP: {endpoint} → {mapped_file}",
                ))

        return candidates[:5]  # Max 5 candidates

    def _parse_stacktrace(self, stacktrace: str) -> List[FixCandidate]:
        """Extract file:line references from a Python stacktrace."""
        candidates = []
        # Match: File "/app/vanguard/api/admin_routes.py", line 189, in resolve_incident
        pattern = re.compile(
            r'File "(?:/app/)?([^"]+\.py)", line (\d+), in (\w+)'
        )

        for match in pattern.finditer(stacktrace):
            file_path = match.group(1)
            line_num = int(match.group(2))
            func_name = match.group(3)

            # Skip stdlib / venv
            if any(skip in file_path for skip in ["site-packages", "lib/python", "/usr/lib"]):
                continue

            candidates.append(FixCandidate(
                file=file_path,
                symbol=f"{func_name}:{line_num}",
                confidence=0.8,
                reason=f"Stacktrace: line {line_num} in {func_name}",
            ))

        # Reverse so the innermost frame (root cause) is first
        candidates.reverse()
        return candidates

    def _map_endpoint(self, endpoint: str, ep_map: Dict[str, str]) -> Optional[str]:
        """Map an endpoint to a file via ENDPOINT_MAP (exact then prefix)."""
        if endpoint in ep_map:
            return ep_map[endpoint]
        for pattern, file_path in ep_map.items():
            if endpoint.startswith(pattern):
                return file_path
        return None

    def _is_allowed_path(self, path: str) -> bool:
        """Check if a path is within allowed edit roots."""
        normalized = path.lstrip("/").replace("\\", "/")
        return any(normalized.startswith(root) for root in ALLOWED_ROOTS)

    # ── Plan construction helpers ─────────────────────────────────────────────

    def _build_summary(
        self, error_type: str, error_message: str, candidates: List[FixCandidate]
    ) -> str:
        files = ", ".join(c.file.split("/")[-1] for c in candidates[:3])
        return (
            f"Fix {error_type} in {files or 'unknown file(s)'}. "
            f"Error: {error_message[:200]}"
        )

    def _build_verification_plan(
        self, endpoint: str, candidates: List[FixCandidate]
    ) -> List[str]:
        steps = [
            "python -m py_compile <changed_file>  # syntax check",
        ]
        if endpoint:
            steps.append(f"curl -s $BASE_URL{endpoint}  # endpoint smoke test")
        steps.append("python scripts/nba_smoke.py  # regression check")
        if any("vanguard" in c.file for c in candidates):
            steps.append("python scripts/vaccine_smoke.py  # vanguard smoke")
        return steps

    def _build_rollback_plan(self, candidates: List[FixCandidate]) -> List[str]:
        return [
            "git diff --cached  # review staged changes",
            "git checkout -- <changed_files>  # revert all changes",
            "git stash  # stash if changes are experimental",
        ]

    def _calculate_risk(
        self, severity: str, candidates: List[FixCandidate], root_cause: str
    ) -> float:
        """0.0 = safe, 1.0 = dangerous."""
        risk = 0.3  # baseline

        # High severity = higher risk of cascading impact
        if severity == "RED":
            risk += 0.2

        # Low confidence candidates = riskier fix
        if candidates:
            avg_conf = sum(c.confidence for c in candidates) / len(candidates)
            risk += max(0, 0.4 - avg_conf)  # lower confidence → higher risk

        # Unknown root cause = we're guessing
        if root_cause == "unknown":
            risk += 0.15

        # High-risk root cause buckets always flag for human review
        if root_cause in _HIGH_RISK_BUCKETS:
            risk += 0.2

        # Core infrastructure files
        if any("main.py" in c.file or "config.py" in c.file for c in candidates):
            risk += 0.15

        return min(risk, 1.0)



# ── Singleton ─────────────────────────────────────────────────────────────────
_plan_engine: Optional[VaccinePlanEngine] = None


def get_plan_engine() -> VaccinePlanEngine:
    global _plan_engine
    if _plan_engine is None:
        _plan_engine = VaccinePlanEngine()
    return _plan_engine
