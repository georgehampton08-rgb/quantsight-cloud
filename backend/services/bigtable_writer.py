"""
Bigtable Analytics Writer — Phase 6 Step 6.5
==============================================
Feature-flagged write path for high-velocity pulse analytics data.

Migrates live_games and live_leaders writes from Firestore to Bigtable
when FEATURE_BIGTABLE_WRITES=true. Falls back to Firestore silently.

Row key design:
    live_games:   {game_id}#{ISO_timestamp}
    live_leaders: {team}#{player_id}#{ISO_timestamp}

Column families:
    cf_game:   game state data (scores, clock, period, status)
    cf_player: player stats (PIE, ts_pct, efg_pct, usage, etc.)
    cf_meta:   metadata (garbage_time, heat_scale, matchup_difficulty)

Prerequisites:
    - google-cloud-bigtable in requirements.txt
    - BIGTABLE_INSTANCE_ID env var set
    - Bigtable instance provisioned in GCP
    - Tables created: pulse_games, pulse_leaders
"""
import os
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Feature flag check
def _bigtable_enabled() -> bool:
    """Check if Bigtable writes are enabled."""
    try:
        from vanguard.core.feature_flags import flag
        return flag("FEATURE_BIGTABLE_WRITES")
    except Exception:
        return False


class BigtableAnalyticsWriter:
    """
    Writes pulse analytics data to Bigtable.
    Falls back to Firestore if Bigtable is unavailable.
    """

    def __init__(self):
        self._client = None
        self._instance = None
        self._games_table = None
        self._leaders_table = None
        self._available = False
        self._write_count = 0
        self._error_count = 0

        if not _bigtable_enabled():
            logger.info("Bigtable writer DISABLED (FEATURE_BIGTABLE_WRITES=false)")
            return

        try:
            from google.cloud import bigtable
            from google.cloud.bigtable import column_family

            project_id = os.getenv("FIREBASE_PROJECT_ID", os.getenv("GCP_PROJECT_ID"))
            instance_id = os.getenv("BIGTABLE_INSTANCE_ID", "quantsight-analytics")

            self._client = bigtable.Client(project=project_id, admin=False)
            self._instance = self._client.instance(instance_id)

            # Connect to tables (must exist — created via gcloud CLI or Terraform)
            self._games_table = self._instance.table("pulse_games")
            self._leaders_table = self._instance.table("pulse_leaders")

            self._available = True
            logger.info(
                f"Bigtable writer ENABLED: "
                f"project={project_id}, instance={instance_id}"
            )
        except ImportError:
            logger.warning("google-cloud-bigtable not installed — Bigtable writer unavailable")
        except Exception as e:
            logger.warning(f"Bigtable init failed: {e} — falling back to Firestore")

    @property
    def is_available(self) -> bool:
        return self._available and _bigtable_enabled()

    async def write_game_state(self, game_data: Dict[str, Any]) -> bool:
        """
        Write a game state snapshot to Bigtable pulse_games table.

        Row key: {game_id}#{ISO_timestamp}
        Column family: cf_game
        """
        if not self.is_available:
            return False

        try:
            game_id = game_data.get("game_id", "")
            timestamp = datetime.now(timezone.utc).isoformat()
            row_key = f"{game_id}#{timestamp}"

            row = self._games_table.direct_row(row_key)

            # cf_game columns
            for key in ("home_team", "away_team", "clock", "status"):
                val = str(game_data.get(key, ""))
                row.set_cell("cf_game", key, val.encode("utf-8"))

            for key in ("home_score", "away_score", "period"):
                val = game_data.get(key, 0)
                row.set_cell("cf_game", key, str(val).encode("utf-8"))

            # cf_meta
            row.set_cell("cf_meta", "is_garbage_time",
                         str(game_data.get("is_garbage_time", False)).encode("utf-8"))
            row.set_cell("cf_meta", "written_at", timestamp.encode("utf-8"))

            row.commit()
            self._write_count += 1
            return True

        except Exception as e:
            self._error_count += 1
            logger.warning(f"Bigtable game write failed: {e}")
            return False

    async def write_leaders(self, leaders: List[Dict[str, Any]]) -> bool:
        """
        Write player leader stats to Bigtable pulse_leaders table.

        Row key: {team}#{player_id}#{ISO_timestamp}
        Column families: cf_player, cf_meta
        """
        if not self.is_available:
            return False

        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            rows = []

            for leader in leaders:
                team = leader.get("team", "UNK")
                player_id = str(leader.get("player_id", ""))
                row_key = f"{team}#{player_id}#{timestamp}"

                row = self._leaders_table.direct_row(row_key)

                # cf_player columns
                for key in ("name", "team", "opponent"):
                    row.set_cell("cf_player", key,
                                 str(leader.get(key, "")).encode("utf-8"))

                for key in ("pie", "plus_minus", "ts_pct", "efg_pct",
                            "usage_rate", "minutes"):
                    val = leader.get(key)
                    row.set_cell("cf_player", key,
                                 str(val if val is not None else "").encode("utf-8"))

                # cf_player: nested stats
                stats = leader.get("stats", {})
                for stat_key in ("pts", "reb", "ast", "stl", "blk", "fg3m", "pf", "tov"):
                    row.set_cell("cf_player", f"stat_{stat_key}",
                                 str(stats.get(stat_key, 0)).encode("utf-8"))

                # cf_meta columns
                row.set_cell("cf_meta", "is_garbage_time",
                             str(leader.get("is_garbage_time", False)).encode("utf-8"))
                row.set_cell("cf_meta", "usage_vacuum",
                             str(leader.get("usage_vacuum", False)).encode("utf-8"))
                row.set_cell("cf_meta", "matchup_difficulty",
                             str(leader.get("matchup_difficulty", "")).encode("utf-8"))
                row.set_cell("cf_meta", "heat_scale",
                             str(leader.get("heat_scale", "")).encode("utf-8"))
                row.set_cell("cf_meta", "written_at", timestamp.encode("utf-8"))

                rows.append(row)

            # Batch commit
            for row in rows:
                row.commit()

            self._write_count += len(rows)
            return True

        except Exception as e:
            self._error_count += 1
            logger.warning(f"Bigtable leaders write failed: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return writer status for health checks."""
        return {
            "enabled": _bigtable_enabled(),
            "available": self._available,
            "write_count": self._write_count,
            "error_count": self._error_count,
            "instance_id": os.getenv("BIGTABLE_INSTANCE_ID", "quantsight-analytics"),
        }


# ── Singleton ────────────────────────────────────────────────────

_writer: Optional[BigtableAnalyticsWriter] = None


def get_bigtable_writer() -> BigtableAnalyticsWriter:
    """Get or create the global Bigtable analytics writer."""
    global _writer
    if _writer is None:
        _writer = BigtableAnalyticsWriter()
    return _writer
