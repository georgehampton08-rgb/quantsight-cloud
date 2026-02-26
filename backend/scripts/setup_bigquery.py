"""
Phase 9 — BigQuery Setup Script
=================================
Creates the quantsight_ml dataset and incident/circuit event tables
in BigQuery for ML training data.

Usage:
    python scripts/setup_bigquery.py

Requires:
    - GOOGLE_CLOUD_PROJECT env var or default project configured
    - BigQuery API enabled
    - bigquery.dataEditor IAM role on the service account
"""

import os
import sys
import logging
from google.cloud import bigquery
from google.api_core.exceptions import Conflict, NotFound

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bq_setup")

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("FIREBASE_PROJECT_ID", "quantsight-prod"))
DATASET_ID = "quantsight_ml"
LOCATION = "US"  # Matches nam5 Firestore multi-region

# ─────────────────────────────────────────────
# Table Schemas
# ─────────────────────────────────────────────
INCIDENTS_SCHEMA = [
    bigquery.SchemaField("fingerprint", "STRING", mode="REQUIRED", description="SHA-256 incident ID"),
    bigquery.SchemaField("endpoint", "STRING", mode="REQUIRED", description="Request path"),
    bigquery.SchemaField("error_type", "STRING", mode="REQUIRED", description="HTTPError type"),
    bigquery.SchemaField("error_message", "STRING", mode="NULLABLE", description="Human-readable error"),
    bigquery.SchemaField("severity", "STRING", mode="REQUIRED", description="RED / YELLOW / GREEN"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED", description="active / resolved"),
    bigquery.SchemaField("occurrence_count", "INTEGER", mode="REQUIRED", description="Total occurrences"),
    bigquery.SchemaField("first_seen", "TIMESTAMP", mode="REQUIRED", description="First occurrence"),
    bigquery.SchemaField("last_seen", "TIMESTAMP", mode="REQUIRED", description="Last occurrence"),
    bigquery.SchemaField("method", "STRING", mode="NULLABLE", description="HTTP method"),
    bigquery.SchemaField("status_code", "INTEGER", mode="NULLABLE", description="HTTP status code"),
    bigquery.SchemaField("traceback_preview", "STRING", mode="NULLABLE", description="First 500 chars of traceback"),
    bigquery.SchemaField("error_category", "STRING", mode="NULLABLE", description="Auto-label: error_category"),
    bigquery.SchemaField("service_label", "STRING", mode="NULLABLE", description="Auto-label: service"),
    bigquery.SchemaField("root_cause_label", "STRING", mode="NULLABLE", description="Auto-label: root_cause"),
    bigquery.SchemaField("ai_confidence", "INTEGER", mode="NULLABLE", description="AI analysis confidence (0-100)"),
    bigquery.SchemaField("ai_root_cause", "STRING", mode="NULLABLE", description="AI root cause text"),
    bigquery.SchemaField("ai_ready_to_resolve", "BOOLEAN", mode="NULLABLE", description="AI resolution verdict"),
    bigquery.SchemaField("heuristic_match", "STRING", mode="NULLABLE", description="Heuristic rule that matched"),
    bigquery.SchemaField("heuristic_confidence", "INTEGER", mode="NULLABLE", description="Heuristic confidence (0-100)"),
    bigquery.SchemaField("ml_label", "STRING", mode="NULLABLE", description="ML classification label (target)"),
    bigquery.SchemaField("exported_at", "TIMESTAMP", mode="REQUIRED", description="Export timestamp"),
]

CIRCUIT_EVENTS_SCHEMA = [
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED", description="Unique event ID"),
    bigquery.SchemaField("endpoint", "STRING", mode="REQUIRED", description="Affected endpoint"),
    bigquery.SchemaField("event_type", "STRING", mode="REQUIRED", description="state_change / prediction"),
    bigquery.SchemaField("from_state", "STRING", mode="NULLABLE", description="Previous CB state"),
    bigquery.SchemaField("to_state", "STRING", mode="REQUIRED", description="New CB state"),
    bigquery.SchemaField("failure_rate", "FLOAT", mode="NULLABLE", description="Failure rate at transition"),
    bigquery.SchemaField("request_count", "INTEGER", mode="NULLABLE", description="Requests in window"),
    bigquery.SchemaField("latency_p95_ms", "FLOAT", mode="NULLABLE", description="p95 latency at transition"),
    bigquery.SchemaField("error_rate_velocity", "FLOAT", mode="NULLABLE", description="Rate of change of errors"),
    bigquery.SchemaField("prediction_confidence", "FLOAT", mode="NULLABLE", description="ML prediction confidence"),
    bigquery.SchemaField("occurred_at", "TIMESTAMP", mode="REQUIRED", description="Event timestamp"),
    bigquery.SchemaField("exported_at", "TIMESTAMP", mode="REQUIRED", description="Export timestamp"),
]

PLAYER_STATS_SCHEMA = [
    bigquery.SchemaField("player_id", "STRING", mode="REQUIRED", description="NBA player ID"),
    bigquery.SchemaField("player_name", "STRING", mode="NULLABLE", description="Player full name"),
    bigquery.SchemaField("team_id", "STRING", mode="NULLABLE", description="Team ID"),
    bigquery.SchemaField("pts_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("reb_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("ast_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("stl_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("blk_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("tov_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("pts_std", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("reb_std", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("ast_std", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("min_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("fga_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("fg_pct_ema", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("snapshot_date", "DATE", mode="REQUIRED", description="Stats snapshot date"),
    bigquery.SchemaField("exported_at", "TIMESTAMP", mode="REQUIRED", description="Export timestamp"),
]

TABLES = {
    "incidents": {
        "schema": INCIDENTS_SCHEMA,
        "description": "Vanguard incident data for ML classifier training",
        "partition_field": "exported_at",
        "clustering_fields": ["error_type", "severity"],
    },
    "circuit_events": {
        "schema": CIRCUIT_EVENTS_SCHEMA,
        "description": "Circuit breaker state transitions for predictive model training",
        "partition_field": "occurred_at",
        "clustering_fields": ["endpoint", "event_type"],
    },
    "player_stats": {
        "schema": PLAYER_STATS_SCHEMA,
        "description": "Player statistical snapshots for Aegis ML predictor training",
        "partition_field": "snapshot_date",
        "clustering_fields": ["player_id", "team_id"],
    },
}


def create_dataset(client: bigquery.Client) -> bigquery.Dataset:
    """Create the quantsight_ml dataset if it doesn't exist."""
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"

    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = LOCATION
    dataset.description = (
        "QuantSight ML training data — incidents, circuit events, player stats. "
        "Phase 9 Machine Learning Integration."
    )
    dataset.default_table_expiration_ms = 90 * 24 * 60 * 60 * 1000  # 90 days

    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        logger.info(f"✅ Dataset {dataset_ref} ready (location={dataset.location})")
        return dataset
    except Exception as e:
        logger.error(f"❌ Failed to create dataset: {e}")
        raise


def create_table(
    client: bigquery.Client,
    table_name: str,
    schema: list,
    description: str,
    partition_field: str,
    clustering_fields: list,
) -> bigquery.Table:
    """Create a partitioned, clustered BigQuery table."""
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

    table = bigquery.Table(table_ref, schema=schema)
    table.description = description

    # Time-based partitioning
    if partition_field:
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_field,
        )

    # Clustering for query optimization
    if clustering_fields:
        table.clustering_fields = clustering_fields

    try:
        table = client.create_table(table, exists_ok=True)
        logger.info(f"✅ Table {table_ref} ready "
                     f"(partitioned={partition_field}, clustered={clustering_fields})")
        return table
    except Exception as e:
        logger.error(f"❌ Failed to create table {table_name}: {e}")
        raise


def verify_setup(client: bigquery.Client):
    """Verify all tables are accessible and have correct schemas."""
    logger.info("─── Verification ───")
    for table_name, config in TABLES.items():
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
        try:
            table = client.get_table(table_ref)
            logger.info(
                f"  {table_name}: {table.num_rows} rows, "
                f"{len(table.schema)} columns, "
                f"partition={table.time_partitioning.field if table.time_partitioning else 'none'}"
            )
        except NotFound:
            logger.error(f"  ❌ {table_name}: NOT FOUND")


def main():
    logger.info("=" * 60)
    logger.info("Phase 9 — BigQuery Setup")
    logger.info(f"Project: {PROJECT_ID}")
    logger.info(f"Dataset: {DATASET_ID}")
    logger.info(f"Location: {LOCATION}")
    logger.info("=" * 60)

    client = bigquery.Client(project=PROJECT_ID)

    # Step 1: Create dataset
    create_dataset(client)

    # Step 2: Create tables
    for table_name, config in TABLES.items():
        create_table(
            client,
            table_name=table_name,
            schema=config["schema"],
            description=config["description"],
            partition_field=config["partition_field"],
            clustering_fields=config["clustering_fields"],
        )
    
    # Step 2b: Create staging tables for MERGE dedup pattern
    for table_name in ["incidents"]:
        staging_name = f"{table_name}_staging"
        staging_ref = f"{PROJECT_ID}.{DATASET_ID}.{staging_name}"
        staging_table = bigquery.Table(staging_ref, schema=TABLES[table_name]["schema"])
        staging_table.description = f"Staging table for {table_name} MERGE dedup (auto-truncated)"
        try:
            client.create_table(staging_table, exists_ok=True)
            logger.info(f"✅ Staging table {staging_ref} ready")
        except Exception as e:
            logger.error(f"❌ Failed to create staging table {staging_name}: {e}")

    # Step 3: Verify
    verify_setup(client)

    logger.info("=" * 60)
    logger.info("✅ BigQuery setup complete. Ready for data export.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
