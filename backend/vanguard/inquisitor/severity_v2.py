"""
Middleware V2 — Severity Classifier
======================================
Phase 2 upgrade: structured severity classification for Vanguard incidents.

Severity Enum: RED / AMBER / YELLOW / GREEN
  RED    - Unhandled exceptions, 5xx errors. NEVER rate-limited.
  AMBER  - 4xx on known API prefixes (genuine client/routing errors worth tracking).
  YELLOW - Everything else >= 400 (noise, bots, static 404s on non-API paths).
  GREEN  - Suppressed. No incident created (e.g. 404 on /favicon, static, non-API paths).

Feature flag: FEATURE_MIDDLEWARE_V2
  When False: module is a no-op, existing middleware behaviour unchanged.
  When True:  this module's classify_severity() is called by VanguardTelemetryMiddleware.

Path label extraction:
  - team_abbr extracted from /roster/{team} or /matchup/* patterns
  - player_id extracted from /players/{id} or /aegis/simulate/{id} patterns
"""

import os
import re
import time
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known API prefixes — 4xx on these paths deserve AMBER (real API error)
# ---------------------------------------------------------------------------
_API_PREFIXES = (
    "/api",
    "/vanguard",
    "/aegis",
    "/live",
    "/matchup",
    "/players",
    "/player",
    "/teams",
    "/roster",
    "/nexus",
    "/boxscore",
    "/schedule",
    "/radar",
    "/game-logs",
    "/admin",
    "/crucible",
    "/h2h",
    "/injuries",
    "/health",
    "/status",
)

# Paths that should NEVER produce incidents (static noise)
_SUPPRESS_PATHS = frozenset({
    "/favicon.ico",
    "/manifest.json",
    "/robots.txt",
    "/sitemap.xml",
    "/service-worker.js",
    "/apple-touch-icon.png",
})
_SUPPRESS_PREFIXES = ("/static/", "/_next/", "/assets/", "/.well-known/")

# ---------------------------------------------------------------------------
# Label extraction from URL paths
# ---------------------------------------------------------------------------
_TEAM_PATTERN = re.compile(
    r"(?:/roster/|/matchup/roster/|/matchup/analyze[?].*?team=)([A-Z]{2,5})",
    re.IGNORECASE
)
_PLAYER_PATTERN = re.compile(
    r"(?:/players?/|/aegis/simulate/|/radar/)([0-9]+)",
    re.IGNORECASE
)


def extract_path_labels(path: str, query_string: str = "") -> dict:
    """
    Extract structured labels from a URL path for enriched incident tagging.
    Only adds keys that are present in the path to keep the label dict lean.
    """
    labels: dict = {}
    full = path + ("?" + query_string if query_string else "")

    m = _TEAM_PATTERN.search(full)
    if m:
        labels["team"] = m.group(1).upper()

    m = _PLAYER_PATTERN.search(path)
    if m:
        labels["player_id"] = m.group(1)

    # Service / revision from Cloud Run env
    svc = os.getenv("K_SERVICE")
    rev = os.getenv("K_REVISION")
    region = os.getenv("CLOUD_RUN_REGION", "us-central1")
    if svc:
        labels["cloud_service"] = svc
    if rev:
        labels["cloud_revision"] = rev
    labels["region"] = region

    return labels


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

def classify_severity(
    status_code: int,
    path: str,
    is_unhandled_exception: bool = False,
) -> Optional[str]:
    """
    Classify the severity for an HTTP event.

    Returns one of: "RED", "AMBER", "YELLOW", or None (suppressed — no incident).

    Rules:
      - Unhandled exceptions           → RED  (always, regardless of path)
      - 5xx                            → RED
      - 4xx on suppress-list paths     → None (suppress, pure noise)
      - 4xx on known API prefixes      → AMBER
      - 4xx elsewhere                  → None (suppress — bots, static, unknown paths)
      - 2xx/3xx                        → None (no incident)
    """
    if is_unhandled_exception or status_code >= 500:
        return "RED"

    if status_code < 400:
        return None  # success — suppressed

    # 4xx logic
    if path in _SUPPRESS_PATHS or path.startswith(_SUPPRESS_PREFIXES):
        return None  # pure static noise — suppressed

    if any(path.startswith(p) for p in _API_PREFIXES):
        return "AMBER"   # real API error — worth tracking

    return None  # unknown path 4xx — suppress (bots, unknown routes)


# ---------------------------------------------------------------------------
# Structured TelemetryEvent log entry
# ---------------------------------------------------------------------------

def emit_telemetry_event(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    severity: Optional[str],
    error: Optional[str] = None,
    labels: Optional[dict] = None,
    fingerprint: Optional[str] = None,
    sampled: bool = False,
) -> None:
    """
    Emit a structured TelemetryEvent JSON log line to stdout.
    Cloud Run captures stdout as structured JSON if the root key is present.
    """
    event = {
        "type": "TelemetryEvent",
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "severity": severity or "GREEN",
        "sampled": sampled,
        "labels": labels or {},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if error:
        event["error"] = error
    if fingerprint:
        event["fingerprint"] = fingerprint

    # Use structured JSON output so Cloud Run logging can index severity
    logger.info("TelemetryEvent %s", json.dumps(event, separators=(",", ":")))
