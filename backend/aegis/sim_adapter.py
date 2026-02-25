"""
Aegis Simulation Adapter — Firestore → Monte Carlo bridge
===========================================================
Phase 6: Bridges Firestore player/team data to the DeepMonteCarloEngine
input format, enabling real simulation in Cloud Run.

Feature flag: FEATURE_AEGIS_SIM_ENABLED
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FirestoreSimAdapter:
    """
    Reads player stats and opponent defense from Firestore,
    normalizes them to the Monte Carlo engine's expected input format.
    """

    def __init__(self):
        self._db = None

    def _get_db(self):
        if self._db is None:
            try:
                from firebase_admin import firestore
                self._db = firestore.client()
            except Exception as e:
                logger.error("[aegis-adapter] Firestore unavailable: %s", e)
        return self._db

    async def get_player_stats(self, player_id: str) -> Optional[Dict[str, float]]:
        """
        Load player stats from Firestore and map to engine format.

        Expected engine keys: pts_ema, reb_ema, ast_ema, stl_ema, blk_ema, tov_ema,
                              pts_std, reb_std, ast_std, min_ema, fga_ema, fg_pct_ema
        """
        db = self._get_db()
        if not db:
            return None

        try:
            # Try player_stats collection first
            doc = db.collection("player_stats").document(player_id).get()
            if doc.exists:
                return self._normalize_player_stats(doc.to_dict())

            # Fallback: try player_vitals
            doc = db.collection("player_vitals").document(player_id).get()
            if doc.exists:
                return self._normalize_player_stats(doc.to_dict())

            logger.warning("[aegis-adapter] No stats found for player %s", player_id)
            return None
        except Exception as e:
            logger.error("[aegis-adapter] Failed to load player stats: %s", e)
            return None

    async def get_opponent_defense(self, team_id: str) -> Optional[Dict[str, float]]:
        """
        Load opponent defensive ratings from Firestore.

        Expected engine keys: def_rating, pace, opp_fg_pct, opp_3pt_pct
        """
        db = self._get_db()
        if not db:
            return None

        try:
            doc = db.collection("team_stats").document(team_id).get()
            if doc.exists:
                data = doc.to_dict()
                return {
                    "def_rating": data.get("def_rating", 110.0),
                    "pace": data.get("pace", 100.0),
                    "opp_fg_pct": data.get("opp_fg_pct", 0.46),
                    "opp_3pt_pct": data.get("opp_3pt_pct", 0.36),
                }
            return None
        except Exception as e:
            logger.error("[aegis-adapter] Failed to load opponent defense: %s", e)
            return None

    @staticmethod
    def _normalize_player_stats(raw: Dict[str, Any]) -> Dict[str, float]:
        """
        Map various Firestore field names to the engine's expected format.
        Gracefully handles missing fields with sensible defaults.
        """
        def _get(keys, default=0.0):
            for k in keys:
                if k in raw and raw[k] is not None:
                    try:
                        return float(raw[k])
                    except (ValueError, TypeError):
                        continue
            return default

        return {
            "pts_ema": _get(["pts_ema", "pts_avg", "pts", "points"]),
            "reb_ema": _get(["reb_ema", "reb_avg", "reb", "rebounds"]),
            "ast_ema": _get(["ast_ema", "ast_avg", "ast", "assists"]),
            "stl_ema": _get(["stl_ema", "stl_avg", "stl", "steals"]),
            "blk_ema": _get(["blk_ema", "blk_avg", "blk", "blocks"]),
            "tov_ema": _get(["tov_ema", "tov_avg", "tov", "turnovers"]),
            "pts_std": _get(["pts_std", "pts_stddev"], 5.0),
            "reb_std": _get(["reb_std", "reb_stddev"], 2.0),
            "ast_std": _get(["ast_std", "ast_stddev"], 2.0),
            "min_ema": _get(["min_ema", "min_avg", "minutes"], 30.0),
            "fga_ema": _get(["fga_ema", "fga_avg", "fga"], 15.0),
            "fg_pct_ema": _get(["fg_pct_ema", "fg_pct", "fg_percentage"], 0.45),
        }
