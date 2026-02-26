"""
Phase 9 — Player Stats BigQuery Exporter
==========================================
Exports player statistical snapshots from Firestore to BigQuery
for Aegis ML predictor training.

Usage:
    python -m services.player_bq_exporter
"""

import os
import logging
from datetime import datetime, timezone, date
from typing import Dict, Any, List

import pandas as pd

logger = logging.getLogger("services.player_bq_exporter")


class PlayerBQExporter:
    """Exports player stats from Firestore to BigQuery for ML training."""
    
    # Stat fields matching sim_adapter.py feature vector
    STAT_FIELDS = {
        "pts_ema": ["pts_ema", "pts_avg", "pts", "points"],
        "reb_ema": ["reb_ema", "reb_avg", "reb", "rebounds"],
        "ast_ema": ["ast_ema", "ast_avg", "ast", "assists"],
        "stl_ema": ["stl_ema", "stl_avg", "stl", "steals"],
        "blk_ema": ["blk_ema", "blk_avg", "blk", "blocks"],
        "tov_ema": ["tov_ema", "tov_avg", "tov", "turnovers"],
        "pts_std": ["pts_std", "pts_stddev"],
        "reb_std": ["reb_std", "reb_stddev"],
        "ast_std": ["ast_std", "ast_stddev"],
        "min_ema": ["min_ema", "min_avg", "minutes"],
        "fga_ema": ["fga_ema", "fga_avg", "fga"],
        "fg_pct_ema": ["fg_pct_ema", "fg_pct", "fg_percentage"],
    }
    
    # Defaults from sim_adapter.py
    DEFAULTS = {
        "pts_ema": 0.0, "reb_ema": 0.0, "ast_ema": 0.0,
        "stl_ema": 0.0, "blk_ema": 0.0, "tov_ema": 0.0,
        "pts_std": 5.0, "reb_std": 2.0, "ast_std": 2.0,
        "min_ema": 30.0, "fga_ema": 15.0, "fg_pct_ema": 0.45,
    }
    
    def __init__(
        self,
        project_id: str = None,
        dataset_id: str = "quantsight_ml",
        table_id: str = "player_stats",
    ):
        self.project_id = project_id or os.getenv(
            "GOOGLE_CLOUD_PROJECT",
            os.getenv("FIREBASE_PROJECT_ID", "quantsight-prod")
        )
        self.dataset_id = dataset_id
        self.table_id = table_id
        self._bq_client = None
    
    def _get_bq_client(self):
        if self._bq_client is None:
            from google.cloud import bigquery
            self._bq_client = bigquery.Client(project=self.project_id)
        return self._bq_client
    
    def _extract_stat(self, doc: Dict[str, Any], field_name: str) -> float:
        """Extract a stat value from a Firestore document using fallback field names.
        
        Matches the sim_adapter.py normalization pattern.
        """
        aliases = self.STAT_FIELDS.get(field_name, [field_name])
        for alias in aliases:
            val = doc.get(alias)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return self.DEFAULTS.get(field_name, 0.0)
    
    async def fetch_player_stats(self) -> List[Dict[str, Any]]:
        """Fetch player stats from Firestore."""
        try:
            import firebase_admin
            from firebase_admin import firestore as fs
            
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            
            db = fs.client()
            
            # Try player_stats collection first, then players
            rows = []
            for collection_name in ["player_stats", "players"]:
                docs = db.collection(collection_name).stream()
                for doc in docs:
                    data = doc.to_dict()
                    player_id = data.get("player_id", doc.id)
                    
                    row = {
                        "player_id": str(player_id),
                        "player_name": data.get("full_name", data.get("player_name")),
                        "team_id": str(data.get("team_id", "")),
                        "snapshot_date": date.today().isoformat(),
                        "exported_at": datetime.now(timezone.utc).isoformat(),
                    }
                    
                    # Extract all stat fields with fallback aliases
                    for field_name in self.STAT_FIELDS:
                        row[field_name] = self._extract_stat(data, field_name)
                    
                    rows.append(row)
                
                if rows:
                    logger.info(f"Fetched {len(rows)} player stats from {collection_name}")
                    break
            
            return rows
            
        except Exception as e:
            logger.error(f"Failed to fetch player stats: {e}")
            raise
    
    def transform_to_dataframe(self, rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """Transform player stats into a BQ-ready DataFrame."""
        df = pd.DataFrame(rows)
        
        if df.empty:
            logger.warning("No player stats to transform")
            return df
        
        # Ensure correct types
        df["exported_at"] = pd.to_datetime(df["exported_at"], utc=True, errors="coerce")
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
        
        for col in self.STAT_FIELDS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        logger.info(f"Transformed {len(df)} player stat rows")
        return df
    
    def export_to_bigquery(self, df: pd.DataFrame) -> int:
        """Export DataFrame to BigQuery."""
        from google.cloud import bigquery
        
        client = self._get_bq_client()
        table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        
        job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        job.result()
        
        logger.info(f"✅ Exported {job.output_rows} player stats to {table_ref}")
        return job.output_rows
    
    async def run_export(self) -> int:
        """Full pipeline: Firestore → Transform → BigQuery."""
        rows = await self.fetch_player_stats()
        
        if not rows:
            logger.warning("No player stats found")
            return 0
        
        df = self.transform_to_dataframe(rows)
        return self.export_to_bigquery(df)


if __name__ == "__main__":
    import asyncio
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    exporter = PlayerBQExporter()
    count = asyncio.run(exporter.run_export())
    print(f"\nExported {count} player stats to BigQuery")
