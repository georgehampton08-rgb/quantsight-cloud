"""
Phase 9 — Incident Classifier Feature Engineering
====================================================
Extracts ML features from raw incident data for classification.

Feature categories:
    1. Error type features (one-hot encoded HTTP status codes)
    2. Endpoint features (prefix extraction, depth, length)
    3. Temporal features (hour of day, day of week, recurrence rate)
    4. Severity features (occurrence count, severity level)
    5. Text features (error message TF-IDF — optional)

All features are designed to work with the small corpus (~159 incidents)
and must NOT require external data beyond the incident document itself.
"""

import re
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger("ml.incident_classifier.features")

# ─────────────────────────────────────────────
# Feature Constants
# ─────────────────────────────────────────────

# Known HTTP status codes in the corpus
HTTP_CODES = [400, 401, 403, 404, 405, 422, 429, 500, 502, 503, 504]

# Known endpoint prefixes
ENDPOINT_PREFIXES = [
    "/api", "/live", "/vanguard", "/aegis", "/health",
    "/matchup", "/players", "/teams", "/schedule", "/admin",
]

# Target labels (from incident_exporter.py)
TARGET_LABELS = [
    "MISSING_ROUTE",
    "VALIDATION_ERROR",
    "SERVER_ERROR",
    "DEPENDENCY_TIMEOUT",
    "CONNECTION_FAILURE",
    "AUTH_FAILURE",
    "CODE_ERROR",
    "IMPORT_FAILURE",
    "MEMORY_PRESSURE",
    "RATE_LIMIT",
    "NBA_API_ERROR",
    "DATABASE_ERROR",
    "UNKNOWN",
]


def extract_status_code(error_type: str) -> int:
    """Extract HTTP status code from error_type string."""
    match = re.search(r"(\d{3})", str(error_type))
    return int(match.group(1)) if match else 0


def extract_endpoint_prefix(endpoint: str) -> str:
    """Extract the first path segment as the endpoint prefix."""
    parts = str(endpoint).strip("/").split("/")
    return f"/{parts[0]}" if parts and parts[0] else "/unknown"


def extract_endpoint_depth(endpoint: str) -> int:
    """Count the number of path segments."""
    return len([p for p in str(endpoint).strip("/").split("/") if p])


def parse_timestamp(ts: Any) -> Optional[datetime]:
    """Safely parse a timestamp from various formats."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def extract_features_single(incident: Dict[str, Any]) -> Dict[str, Any]:
    """Extract feature vector from a single incident document.
    
    Args:
        incident: Raw incident dictionary (Firestore or BQ format)
        
    Returns:
        Dictionary of feature name → value
    """
    error_type = str(incident.get("error_type", ""))
    endpoint = str(incident.get("endpoint", ""))
    error_message = str(incident.get("error_message", "") or "")
    severity = str(incident.get("severity", "YELLOW"))
    
    # 1. Status code features
    status_code = extract_status_code(error_type)
    features = {
        "status_code": status_code,
        "is_4xx": 1 if 400 <= status_code < 500 else 0,
        "is_5xx": 1 if 500 <= status_code < 600 else 0,
    }
    
    # One-hot for specific status codes
    for code in HTTP_CODES:
        features[f"status_{code}"] = 1 if status_code == code else 0
    
    # 2. Endpoint features
    prefix = extract_endpoint_prefix(endpoint)
    features["endpoint_depth"] = extract_endpoint_depth(endpoint)
    features["endpoint_length"] = len(endpoint)
    features["has_player_id"] = 1 if re.search(r"/\d{4,}", endpoint) else 0
    features["has_wildcard"] = 1 if "{" in endpoint or "*" in endpoint else 0
    
    # One-hot for endpoint prefixes
    for ep_prefix in ENDPOINT_PREFIXES:
        features[f"prefix_{ep_prefix.strip('/')}"] = 1 if prefix == ep_prefix else 0
    
    # 3. Temporal features
    first_seen = parse_timestamp(incident.get("first_seen"))
    last_seen = parse_timestamp(incident.get("last_seen"))
    
    if first_seen:
        features["hour_of_day"] = first_seen.hour
        features["day_of_week"] = first_seen.weekday()
        features["is_weekend"] = 1 if first_seen.weekday() >= 5 else 0
    else:
        features["hour_of_day"] = 12
        features["day_of_week"] = 0
        features["is_weekend"] = 0
    
    # Duration: how long has this incident been recurring?
    if first_seen and last_seen:
        duration_hours = max(0, (last_seen - first_seen).total_seconds() / 3600)
        features["duration_hours"] = min(duration_hours, 720)  # Cap at 30 days
    else:
        features["duration_hours"] = 0
    
    # 4. Severity & frequency features
    occurrence_count = int(incident.get("occurrence_count", 1))
    features["occurrence_count"] = min(occurrence_count, 1000)  # Cap outliers
    features["log_occurrence_count"] = np.log1p(occurrence_count)
    features["severity_red"] = 1 if severity == "RED" else 0
    features["severity_yellow"] = 1 if severity == "YELLOW" else 0
    features["is_resolved"] = 1 if incident.get("status") == "resolved" else 0
    
    # Recurrence rate (occurrences per hour)
    if features["duration_hours"] > 0:
        features["recurrence_rate"] = occurrence_count / features["duration_hours"]
    else:
        features["recurrence_rate"] = float(occurrence_count)
    features["recurrence_rate"] = min(features["recurrence_rate"], 100)  # Cap
    
    # 5. Error message features (lightweight text)
    features["error_msg_length"] = len(error_message)
    features["has_traceback"] = 1 if incident.get("traceback") else 0
    features["has_firestore_ref"] = 1 if "firestore" in error_message.lower() else 0
    features["has_timeout_ref"] = 1 if "timeout" in error_message.lower() else 0
    features["has_import_ref"] = 1 if "import" in error_message.lower() else 0
    features["has_connection_ref"] = 1 if "connect" in error_message.lower() else 0
    features["has_nba_ref"] = 1 if "nba" in error_message.lower() else 0
    features["has_permission_ref"] = 1 if "permission" in error_message.lower() or "denied" in error_message.lower() else 0
    
    # 6. Context features
    context = incident.get("context_vector", {})
    features["method_get"] = 1 if context.get("method", "").upper() == "GET" else 0
    features["method_post"] = 1 if context.get("method", "").upper() == "POST" else 0
    
    return features


def extract_features_batch(incidents: List[Dict[str, Any]]) -> pd.DataFrame:
    """Extract feature vectors from a batch of incidents.
    
    Args:
        incidents: List of incident dictionaries
        
    Returns:
        DataFrame where each row is a feature vector
    """
    rows = [extract_features_single(inc) for inc in incidents]
    df = pd.DataFrame(rows)
    
    # Fill any NaN with 0
    df = df.fillna(0)
    
    # Ensure all columns are numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    logger.info(f"Extracted {len(df)} feature vectors with {len(df.columns)} features")
    return df


def extract_labels(
    incidents: List[Dict[str, Any]],
    label_field: str = "ml_label",
) -> Tuple[np.ndarray, LabelEncoder]:
    """Extract and encode target labels from incidents.
    
    Args:
        incidents: List of incident dictionaries
        label_field: Field name containing the label
        
    Returns:
        (encoded_labels, label_encoder) tuple
    """
    # Import label derivation from exporter
    from vanguard.export.incident_exporter import _derive_ml_label
    
    labels = []
    for inc in incidents:
        label = inc.get(label_field)
        if not label:
            label = _derive_ml_label(inc)
        labels.append(label)
    
    encoder = LabelEncoder()
    encoder.fit(TARGET_LABELS)  # Fit on all known labels first
    
    # Handle any labels not in TARGET_LABELS
    valid_labels = []
    for lbl in labels:
        if lbl in encoder.classes_:
            valid_labels.append(lbl)
        else:
            valid_labels.append("UNKNOWN")
    
    encoded = encoder.transform(valid_labels)
    
    # Log distribution
    from collections import Counter
    dist = Counter(valid_labels)
    logger.info(f"Label distribution: {dict(dist)}")
    
    return encoded, encoder


def get_feature_names() -> List[str]:
    """Return the ordered list of feature names.
    
    Useful for model inspection and drift detection.
    """
    # Generate a dummy feature vector to get column names
    dummy = extract_features_single({
        "error_type": "HTTPError404",
        "endpoint": "/api/test",
        "severity": "YELLOW",
        "occurrence_count": 1,
    })
    return sorted(dummy.keys())
