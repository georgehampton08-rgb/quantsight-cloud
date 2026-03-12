"""
Simple Injury Fetcher — ESPN-Powered (v2)
=========================================
Previously used nba_api.stats.endpoints.commonplayerinfo per player, which:
  - Returned no actual injury data (just assumed AVAILABLE)
  - Added 600ms+ latency per player call
  - Was rate-limited/blocked on Cloud Run

Now: reads from Firestore `player_injuries` collection written by
ESPNInjuryPoller — no external API calls at runtime, sub-millisecond reads.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleInjuryFetcher:
    """Injury data via Firestore (written by ESPNInjuryPoller)."""

    def __init__(self, db_path: Optional[str] = None):
        # db_path kept for signature compatibility — not used (Firestore now)
        self._db = None

    def _get_db(self):
        if self._db is None:
            from firestore_db import get_firestore_db
            self._db = get_firestore_db()
        return self._db

    def check_player_injury(self, player_id: str) -> Dict:
        """
        Return injury status for a player from Firestore player_injuries.
        Falls back to AVAILABLE if no record found — same behaviour as before.
        """
        try:
            db = self._get_db()
            doc = db.collection("player_injuries").document(str(player_id)).get()
            if doc.exists:
                data = doc.to_dict()
                status = data.get("status", "AVAILABLE")
                is_available = status.upper() not in ("OUT", "DOUBT", "DOUBTFUL")
                return {
                    "player_id": player_id,
                    "status": status,
                    "injury_desc": data.get("injuryType", ""),
                    "is_available": is_available,
                    "performance_factor": 0.5 if not is_available else 1.0,
                    "source": "espn_firestore",
                    "checked_at": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.warning(f"Firestore injury lookup failed for {player_id}: {e}")

        # Healthy fallback
        return {
            "player_id": player_id,
            "status": "AVAILABLE",
            "injury_desc": "",
            "is_available": True,
            "performance_factor": 1.0,
            "source": "fallback",
            "checked_at": datetime.now().isoformat(),
        }

    def get_team_injuries(self, team_abbr: str, roster: List[str]) -> List[Dict]:
        """Return injuries for all players in a roster list."""
        injuries = []
        for player_id in roster:
            status = self.check_player_injury(player_id)
            if not status["is_available"]:
                injuries.append(status)
        logger.info(f"[InjuryFetcher] {team_abbr}: {len(injuries)} injured players")
        return injuries


# Singleton
_fetcher = None


def get_simple_injury_fetcher() -> SimpleInjuryFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = SimpleInjuryFetcher()
    return _fetcher
