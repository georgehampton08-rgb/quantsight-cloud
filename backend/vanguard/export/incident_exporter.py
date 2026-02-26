"""
Phase 9 — Incident Exporter (Firestore → BigQuery)
====================================================
Exports Vanguard incidents from Firestore to BigQuery for ML training.

Features:
    - Incremental export (only exports incidents modified since last run)
    - Heuristic triage matching for auto-labeling
    - Flattened schema for ML feature engineering
    - Atomic batch insert via load_table_from_dataframe()

Usage:
    python -m vanguard.export.incident_exporter
    
    # Or as a module:
    from vanguard.export.incident_exporter import IncidentExporter
    await exporter.export_to_bigquery()
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import pandas as pd

logger = logging.getLogger("vanguard.export")


# ─────────────────────────────────────────────
# Heuristic rule matching for auto-labeling
# ─────────────────────────────────────────────
_LABEL_RULES = [
    (re.compile(r"FailedPrecondition|FAILED_PRECONDITION|missing.+index", re.IGNORECASE), "DATABASE_ERROR", 75),
    (re.compile(r"DeadlineExceeded|DEADLINE_EXCEEDED|timeout", re.IGNORECASE), "DEPENDENCY_TIMEOUT", 65),
    (re.compile(r"ConnectionError|ConnectionRefused|ECONNREFUSED", re.IGNORECASE), "CONNECTION_FAILURE", 60),
    (re.compile(r"ReadTimeout|ReadTimeoutError|aiohttp.*timeout", re.IGNORECASE), "DEPENDENCY_TIMEOUT", 60),
    (re.compile(r"PermissionDenied|PERMISSION_DENIED|403|Unauthorized|401", re.IGNORECASE), "AUTH_FAILURE", 70),
    (re.compile(r"KeyError|AttributeError|TypeError", re.IGNORECASE), "CODE_ERROR", 55),
    (re.compile(r"ImportError|ModuleNotFoundError", re.IGNORECASE), "IMPORT_FAILURE", 80),
    (re.compile(r"MemoryError|OOM|OutOfMemory", re.IGNORECASE), "MEMORY_PRESSURE", 70),
    (re.compile(r"RateLimited|429|Too.*Many.*Requests", re.IGNORECASE), "RATE_LIMIT", 65),
    (re.compile(r"nba_api|stats\.nba\.com|NBAStatsHTTP", re.IGNORECASE), "NBA_API_ERROR", 60),
]


def _match_heuristic(error_type: str, error_message: str) -> tuple:
    """Match incident against heuristic rules for auto-labeling.
    
    Returns:
        (rule_name, confidence) or (None, 0)
    """
    text = f"{error_type} {error_message}"
    for pattern, label, confidence in _LABEL_RULES:
        if pattern.search(text):
            return label, confidence
    return None, 0


def _derive_ml_label(incident: Dict[str, Any]) -> str:
    """Derive the ML classification target label from incident data.
    
    Priority:
        1. Existing labels.error_category (if meaningful)
        2. Heuristic pattern match
        3. HTTP status code based fallback
        4. UNKNOWN
    """
    error_type = incident.get("error_type", "")
    error_message = incident.get("error_message", "")
    labels = incident.get("labels", {})
    
    # 1. Try heuristic match first (most precise)
    heuristic_label, _ = _match_heuristic(error_type, error_message)
    if heuristic_label:
        return heuristic_label
    
    # 2. Map by error category label
    error_category = labels.get("error_category", "")
    category_map = {
        "not_found": "MISSING_ROUTE",
        "validation_error": "VALIDATION_ERROR",
        "internal_error": "SERVER_ERROR",
        "timeout": "DEPENDENCY_TIMEOUT",
        "authentication": "AUTH_FAILURE",
    }
    if error_category in category_map:
        return category_map[error_category]
    
    # 3. Map by HTTP status code pattern in error_type
    status_match = re.search(r"(\d{3})", error_type)
    if status_match:
        code = int(status_match.group(1))
        if code == 404:
            return "MISSING_ROUTE"
        elif code == 400:
            return "VALIDATION_ERROR"
        elif code == 422:
            return "VALIDATION_ERROR"
        elif code == 403 or code == 401:
            return "AUTH_FAILURE"
        elif code == 429:
            return "RATE_LIMIT"
        elif code == 500:
            return "SERVER_ERROR"
        elif code == 502 or code == 503 or code == 504:
            return "DEPENDENCY_TIMEOUT"
    
    return "UNKNOWN"


def _flatten_incident(incident: Dict[str, Any], now: str) -> Dict[str, Any]:
    """Flatten a Firestore incident document into a BQ-ready row.
    
    Args:
        incident: Raw Firestore incident document
        now: ISO timestamp for exported_at
        
    Returns:
        Flattened dictionary matching INCIDENTS_SCHEMA
    """
    # Extract nested fields safely
    context = incident.get("context_vector", {})
    labels = incident.get("labels", {})
    ai = incident.get("ai_analysis", {})
    
    # Run heuristic matching
    heuristic_label, heuristic_confidence = _match_heuristic(
        incident.get("error_type", ""),
        incident.get("error_message", "")
    )
    
    # Derive ML target label
    ml_label = _derive_ml_label(incident)
    
    # Truncate traceback for storage efficiency
    traceback = incident.get("traceback", "") or ""
    traceback_preview = traceback[:500] if traceback else None
    
    return {
        "fingerprint": incident.get("fingerprint", ""),
        "endpoint": incident.get("endpoint", ""),
        "error_type": incident.get("error_type", ""),
        "error_message": (incident.get("error_message", "") or "")[:1000],
        "severity": incident.get("severity", "YELLOW"),
        "status": incident.get("status", "active"),
        "occurrence_count": incident.get("occurrence_count", 1),
        "first_seen": incident.get("first_seen", now),
        "last_seen": incident.get("last_seen", now),
        "method": context.get("method"),
        "status_code": context.get("status_code"),
        "traceback_preview": traceback_preview,
        "error_category": labels.get("error_category"),
        "service_label": labels.get("service"),
        "root_cause_label": labels.get("root_cause"),
        "ai_confidence": ai.get("confidence") if ai else None,
        "ai_root_cause": (ai.get("root_cause", "") or "")[:2000] if ai else None,
        "ai_ready_to_resolve": ai.get("ready_to_resolve") if ai else None,
        "heuristic_match": heuristic_label,
        "heuristic_confidence": heuristic_confidence if heuristic_label else None,
        "ml_label": ml_label,
        "exported_at": now,
    }


class IncidentExporter:
    """Exports Vanguard incidents from Firestore to BigQuery."""
    
    def __init__(
        self,
        project_id: str = None,
        dataset_id: str = "quantsight_ml",
        table_id: str = "incidents",
    ):
        self.project_id = project_id or os.getenv(
            "GOOGLE_CLOUD_PROJECT",
            os.getenv("FIREBASE_PROJECT_ID", "quantsight-prod")
        )
        self.dataset_id = dataset_id
        self.table_id = table_id
        self._bq_client = None
    
    def _get_bq_client(self):
        """Lazy-load BigQuery client."""
        if self._bq_client is None:
            from google.cloud import bigquery
            self._bq_client = bigquery.Client(project=self.project_id)
        return self._bq_client
    
    async def fetch_incidents_from_firestore(
        self,
        since: Optional[str] = None,
        limit: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Fetch incidents from Firestore.
        
        Args:
            since: ISO timestamp — only fetch incidents modified after this time
            limit: Maximum number of incidents to fetch
            
        Returns:
            List of incident dictionaries
        """
        try:
            import firebase_admin
            from firebase_admin import firestore as fs
            
            # Initialize Firebase if needed
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            
            db = fs.client()
            query = db.collection("vanguard_incidents")
            
            if since:
                query = query.where("last_seen", ">=", since)
            
            query = query.limit(limit)
            docs = query.stream()
            
            incidents = []
            for doc in docs:
                data = doc.to_dict()
                data["fingerprint"] = doc.id
                incidents.append(data)
            
            logger.info(f"Fetched {len(incidents)} incidents from Firestore"
                       f"{f' (since {since})' if since else ''}")
            return incidents
            
        except Exception as e:
            logger.error(f"Failed to fetch incidents from Firestore: {e}")
            raise
    
    def load_from_export_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Load incidents from a local JSON export file.
        
        Args:
            filepath: Path to JSON export file
            
        Returns:
            List of incident dictionaries
        """
        import json
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        incidents = data.get("incidents", data if isinstance(data, list) else [])
        logger.info(f"Loaded {len(incidents)} incidents from {filepath}")
        return incidents
    
    def transform_incidents(self, incidents: List[Dict[str, Any]]) -> pd.DataFrame:
        """Transform raw incidents into a BQ-ready DataFrame.
        
        Args:
            incidents: List of raw incident dictionaries
            
        Returns:
            pandas DataFrame matching INCIDENTS_SCHEMA
        """
        now = datetime.now(timezone.utc).isoformat()
        
        rows = [_flatten_incident(inc, now) for inc in incidents]
        df = pd.DataFrame(rows)
        
        # Ensure timestamp columns are proper datetime
        for col in ["first_seen", "last_seen", "exported_at"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
        
        # Ensure integer columns
        for col in ["occurrence_count", "status_code", "ai_confidence", "heuristic_confidence"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Log label distribution
        if "ml_label" in df.columns:
            label_counts = df["ml_label"].value_counts()
            logger.info(f"ML label distribution:\n{label_counts.to_string()}")
        
        logger.info(f"Transformed {len(df)} incidents → {len(df.columns)} columns")
        return df
    
    def export_dataframe_to_bigquery(self, df: pd.DataFrame) -> int:
        """Export a DataFrame to BigQuery using load_table_from_dataframe.
        
        Args:
            df: Transformed DataFrame
            
        Returns:
            Number of rows written
        """
        from google.cloud import bigquery
        
        client = self._get_bq_client()
        table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        
        job = client.load_table_from_dataframe(
            df, table_ref, job_config=job_config
        )
        job.result()  # Wait for completion
        
        logger.info(f"✅ Exported {job.output_rows} rows to {table_ref}")
        return job.output_rows
    
    async def export_to_bigquery(
        self,
        since: Optional[str] = None,
        source_file: Optional[str] = None,
    ) -> int:
        """Full export pipeline: Firestore → Transform → BigQuery.
        
        Args:
            since: Optional ISO timestamp for incremental export
            source_file: Optional local JSON file to use instead of Firestore
            
        Returns:
            Number of rows exported
        """
        # Step 1: Fetch data
        if source_file:
            incidents = self.load_from_export_file(source_file)
        else:
            incidents = await self.fetch_incidents_from_firestore(since=since)
        
        if not incidents:
            logger.warning("No incidents to export")
            return 0
        
        # Step 2: Transform
        df = self.transform_incidents(incidents)
        
        # Step 3: Load to BigQuery
        rows_written = self.export_dataframe_to_bigquery(df)
        
        return rows_written


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    exporter = IncidentExporter()
    
    # Check for --file argument
    source_file = None
    if len(sys.argv) > 1 and sys.argv[1] == "--file":
        source_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    rows = asyncio.run(exporter.export_to_bigquery(source_file=source_file))
    print(f"\nExported {rows} incidents to BigQuery")
