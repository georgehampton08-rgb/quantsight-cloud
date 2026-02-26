"""
Heuristic Triage — Phase 5 Step 5.2
======================================
Pattern-matching fallback triage engine that runs when Gemini API is
unavailable. Produces an IncidentAnalysis compatible with the AI
analyzer output, ensuring downstream Surgeon + Vaccine logic works
identically regardless of triage source.

Heuristic rules are purely deterministic — no LLM calls.

Activation:
  Routing table activates this when SYSTEM_SNAPSHOT reports 3
  consecutive gemini_ok=False checks (~90s at 30s intervals).

Deactivation:
  Routing table deactivates when 2 consecutive gemini_ok=True
  checks confirm recovery (~60s).
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ── Known heuristic patterns ────────────────────────────────────────────────
# Each entry: (error_type_pattern, root_cause_template, recommended_fix, confidence)

_HEURISTIC_RULES: List[Tuple[str, str, List[str], int]] = [
    # ── Firestore / gRPC errors ──────────────────────────────────────────
    (
        r"(?i)(FailedPrecondition|FAILED_PRECONDITION|missing.+index)",
        "Firestore composite index missing for query on {endpoint}. "
        "This typically means a new compound query was deployed without creating the required index.",
        [
            "IMMEDIATE: Check Firestore console for missing index links in error messages",
            "ROOT FIX: Create the composite index via Firebase console or firestore.indexes.json",
            "PREVENTION: Run IndexDoctor (FEATURE_INDEX_DOCTOR=true) to auto-detect and PR index patches",
        ],
        75,
    ),
    (
        r"(?i)(DeadlineExceeded|DEADLINE_EXCEEDED|timeout)",
        "Firestore or external API call timed out on {endpoint}. "
        "This indicates either Firestore latency spike or network congestion.",
        [
            "IMMEDIATE: Check Firestore dashboard for latency spikes",
            "ROOT FIX: Add asyncio.wait_for() timeout guards around the slow call",
            "PREVENTION: Add a Firestore latency SLI alert at P95 > 500ms",
        ],
        65,
    ),
    # ── HTTP / Connection errors ─────────────────────────────────────────
    (
        r"(?i)(ConnectionError|ConnectionRefused|ECONNREFUSED|Connection\s*reset)",
        "Upstream connection failure on {endpoint}. "
        "The target service (NBA API, Redis, or downstream) refused or reset the connection.",
        [
            "IMMEDIATE: Verify upstream service health (Redis, NBA API, Firestore)",
            "ROOT FIX: Add retry logic with exponential backoff on the failing connector",
            "PREVENTION: Add circuit breaker for the upstream dependency",
        ],
        60,
    ),
    (
        r"(?i)(ReadTimeout|ReadTimeoutError|aiohttp.*timeout|httpx.*timeout)",
        "HTTP read timeout waiting for upstream response on {endpoint}. "
        "The request was sent but the upstream did not respond in time.",
        [
            "IMMEDIATE: Check NBA API status and rate limits",
            "ROOT FIX: Increase timeout or add fallback data path",
            "PREVENTION: Cache upstream responses to serve stale data during outages",
        ],
        60,
    ),
    # ── Auth / Permission errors ─────────────────────────────────────────
    (
        r"(?i)(PermissionDenied|PERMISSION_DENIED|403|Unauthorized|401)",
        "Authentication or permission failure on {endpoint}. "
        "Service credentials may have expired or IAM bindings are incorrect.",
        [
            "IMMEDIATE: Verify service account credentials and IAM roles",
            "ROOT FIX: Refresh credentials or update IAM policy bindings",
            "PREVENTION: Add credential expiry monitoring to SYSTEM_SNAPSHOT",
        ],
        70,
    ),
    # ── Key / Import errors ──────────────────────────────────────────────
    (
        r"(?i)(KeyError|AttributeError|TypeError)",
        "Code-level error ({error_type}) on {endpoint}. "
        "Likely caused by unexpected data shape or None propagation.",
        [
            "IMMEDIATE: Check recent deployments for breaking changes",
            "ROOT FIX: Add defensive null checks and type validation on the failing path",
            "PREVENTION: Add Pydantic model validation at the data ingestion boundary",
        ],
        55,
    ),
    (
        r"(?i)(ImportError|ModuleNotFoundError)",
        "Missing module import on {endpoint}. "
        "A required dependency is not installed or a circular import exists.",
        [
            "IMMEDIATE: Check requirements.txt for the missing package",
            "ROOT FIX: Add the missing dependency or fix the circular import chain",
            "PREVENTION: Add import validation to test_startup_integrity.py",
        ],
        80,
    ),
    # ── Memory / OOM ─────────────────────────────────────────────────────
    (
        r"(?i)(MemoryError|OOM|OutOfMemory|memory)",
        "Memory pressure incident on {endpoint}. "
        "Container may be approaching OOM threshold.",
        [
            "IMMEDIATE: Check LoadSheddingGovernor status and container memory usage",
            "ROOT FIX: Optimize memory-intensive operations or increase Cloud Run memory limit",
            "PREVENTION: Enable FEATURE_LOAD_SHEDDER to activate automatic shedding",
        ],
        70,
    ),
    # ── Rate limiting / 429 ──────────────────────────────────────────────
    (
        r"(?i)(RateLimited|429|Too\s*Many\s*Requests)",
        "Rate limit exceeded on {endpoint}. "
        "Either our rate limiter rejected the request or an upstream API returned 429.",
        [
            "IMMEDIATE: Check if the caller is a legitimate burst or an abusive client",
            "ROOT FIX: Adjust rate limiter bucket sizes or add per-route overrides",
            "PREVENTION: Add rate limit headroom monitoring to scale alerts",
        ],
        65,
    ),
    # ── NBA API specific ─────────────────────────────────────────────────
    (
        r"(?i)(nba_api|stats\.nba\.com|NBAStatsHTTP)",
        "NBA API failure on {endpoint}. "
        "The NBA stats API is either down, rate-limiting, or returning malformed responses.",
        [
            "IMMEDIATE: Check stats.nba.com availability; API may be in maintenance window",
            "ROOT FIX: Add fallback to cached/stale data when NBA API is unavailable",
            "PREVENTION: Add NBA API health to SYSTEM_SNAPSHOT checks",
        ],
        60,
    ),
]


def generate_heuristic_triage(incident: Dict) -> Dict:
    """
    Generate a heuristic triage analysis for an incident.

    Returns a dict compatible with IncidentAnalysis fields so that the
    downstream pipeline (Surgeon.decide_remediation) works identically
    regardless of whether triage came from Gemini or heuristics.

    The returned dict includes a triage_source="heuristic" field that
    is NOT present in Gemini-sourced analyses.
    """
    from .ai_analyzer import IncidentAnalysis

    error_type = incident.get("error_type", "UnknownError")
    error_message = incident.get("error_message", "")
    endpoint = incident.get("endpoint", "unknown")
    fingerprint = incident.get("fingerprint", "unknown")

    # Combine error_type + error_message for pattern matching
    match_text = f"{error_type} {error_message}"

    root_cause = None
    recommended_fix = None
    confidence = 0

    for pattern, cause_template, fix_list, conf in _HEURISTIC_RULES:
        if re.search(pattern, match_text):
            root_cause = cause_template.format(
                endpoint=endpoint,
                error_type=error_type,
            )
            recommended_fix = fix_list
            confidence = conf
            break

    # Fallback if no pattern matched
    if root_cause is None:
        root_cause = (
            f"{error_type} on {endpoint} — no heuristic pattern matched. "
            f"Manual review recommended."
        )
        recommended_fix = [
            "IMMEDIATE: Check application logs for the full stack trace",
            "ROOT FIX: Review the error type and endpoint for root cause",
            "PREVENTION: Add a heuristic rule for this error pattern once resolved",
        ]
        confidence = 30

    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=24)

    analysis = IncidentAnalysis(
        fingerprint=fingerprint,
        root_cause=root_cause,
        impact=_estimate_impact(incident),
        recommended_fix=recommended_fix,
        ready_to_resolve=False,
        ready_reasoning="Heuristic triage — manual verification required before resolution",
        confidence=confidence,
        generated_at=now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        expires_at=expires.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
        cached=False,
        prompt_version="heuristic-1.0",
        model_id="heuristic-engine",
    )

    logger.info(
        "heuristic_triage_generated",
        fingerprint=fingerprint[:16],
        confidence=confidence,
        error_type=error_type,
    )

    return analysis


def _estimate_impact(incident: Dict) -> str:
    """Estimate impact based on incident severity and occurrence count."""
    severity = incident.get("severity", "YELLOW")
    count = incident.get("occurrence_count", 1)
    endpoint = incident.get("endpoint", "unknown")

    if severity == "RED":
        if count > 10:
            return f"HIGH: {endpoint} is persistently failing ({count} occurrences). Users on this path are fully blocked."
        return f"HIGH: {endpoint} is failing with severity RED. User-facing functionality may be degraded."
    elif severity == "ORANGE":
        return f"MEDIUM: {endpoint} is experiencing issues ({count} occurrences). Some requests may fail."
    else:
        return f"LOW: {endpoint} had a transient issue ({count} occurrences). Minimal user impact expected."
