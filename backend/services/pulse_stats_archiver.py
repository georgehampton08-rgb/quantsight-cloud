"""
Pulse Stats Archival Service
=============================
Saves player stats at quarter ends and game finals.

Firestore Structure (matches matchups pattern):
pulse_stats (collection)
  └── {date} (document like "2026-02-04")
      └── games (subcollection)
          └── {game_id} (document like "0022500715")
              └── quarters (subcollection)
                  ├── Q1 (document)
                  ├── Q2 (document)
                  ├── Q3 (document)
                  ├── Q4 (document)
                  └── FINAL (document)
                      └── players (map field)
                          ├── player_id → stats
                          └── ...
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PulseStatsArchiver:
    """
    Archives player stats at quarter ends to Firestore.
    Mirrors the matchups collection structure.
    """
    
    def __init__(self, firebase_service=None):
        self._firebase = firebase_service
        self._last_quarters: Dict[str, int] = {}  # game_id -> last_quarter_saved
        logger.info("✅ PulseStatsArchiver initialized")
    
    def set_firebase(self, firebase_service):
        """Set Firebase service after initialization."""
        self._firebase = firebase_service
    
    async def check_and_archive(
        self,
        game_id: str,
        current_quarter: int,
        game_status: str,
        player_stats: List[Dict[str, Any]],
        home_team: str = "",
        away_team: str = "",
        home_score: int = 0,
        away_score: int = 0
    ):
        """
        Check if we need to archive stats for quarter end or final.
        
        Args:
            game_id: NBA game ID (e.g., "0022500715")
            current_quarter: Current quarter/period (1, 2, 3, 4, or OT)
            game_status: "LIVE", "FINAL", "NOT_STARTED"
            player_stats: List of player stat dictionaries
            home_team: Home team tricode
            away_team: Away team tricode
            home_score: Current home score
            away_score: Current away score
        """
        if not self._firebase:
            return
        
        last_quarter = self._last_quarters.get(game_id, 0)
        
        # Detect quarter change (Q1 end → 2, Q2 end → 3, etc.)
        # We save at the START of new quarter (meaning previous quarter ended)
        if current_quarter > last_quarter and last_quarter > 0:
            quarter_label = f"Q{last_quarter}"
            await self._save_quarter_stats(
                game_id=game_id,
                quarter_label=quarter_label,
                player_stats=player_stats,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score
            )
            logger.info(f"📊 Archived {quarter_label} stats for game {game_id}")
        
        # Update tracking
        self._last_quarters[game_id] = current_quarter
        
        # Check for FINAL
        if game_status == "FINAL":
            # ── Save the LAST quarter (Q4, OT1, etc.) explicitly ──
            # The transition detector above only fires on Q→Q+1, but
            # there is no Q5. So Q4 (or the last OT) would never be
            # saved without this block. We use current_quarter to
            # label it correctly (Q4, OT1=Q5, OT2=Q6, …).
            if current_quarter >= 4:
                quarter_label = f"Q{current_quarter}" if current_quarter == 4 else f"OT{current_quarter - 4}"
                await self._save_quarter_stats(
                    game_id=game_id,
                    quarter_label=quarter_label,
                    player_stats=player_stats,
                    home_team=home_team,
                    away_team=away_team,
                    home_score=home_score,
                    away_score=away_score
                )
                logger.info(f"📊 Archived {quarter_label} stats for game {game_id}")

            # Save FINAL snapshot (full-game totals)
            await self._save_quarter_stats(
                game_id=game_id,
                quarter_label="FINAL",
                player_stats=player_stats,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                is_final=True
            )
            logger.info(f"🏁 Archived FINAL stats for game {game_id}")
            
            # Clean up tracking
            if game_id in self._last_quarters:
                del self._last_quarters[game_id]
    
    async def _save_quarter_stats(
        self,
        game_id: str,
        quarter_label: str,
        player_stats: List[Dict[str, Any]],
        home_team: str = "",
        away_team: str = "",
        home_score: int = 0,
        away_score: int = 0,
        is_final: bool = False
    ):
        """
        Save stats to Firestore in hierarchical structure.
        
        Structure:
        pulse_stats/{date}/games/{game_id}/quarters/{quarter_label}
        """
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            # Build player stats map
            players_map = {}
            for p in player_stats:
                player_id = str(p.get("player_id", ""))
                if player_id:
                    players_map[player_id] = {
                        "name": p.get("name", ""),
                        "team": p.get("team", ""),
                        "pts": p.get("stats", {}).get("pts", 0),
                        "reb": p.get("stats", {}).get("reb", 0),
                        "ast": p.get("stats", {}).get("ast", 0),
                        "stl": p.get("stats", {}).get("stl", 0),
                        "blk": p.get("stats", {}).get("blk", 0),
                        "to": p.get("stats", {}).get("to", 0),
                        "min": p.get("stats", {}).get("min", 0),
                        "fg3m": p.get("stats", {}).get("fg3m", 0),
                        "fga": p.get("stats", {}).get("fga", 0),
                        "fgm": p.get("stats", {}).get("fgm", 0),
                        "fta": p.get("stats", {}).get("fta", 0),
                        "ftm": p.get("stats", {}).get("ftm", 0),
                        "plus_minus": p.get("stats", {}).get("plus_minus", 0),
                        "pie": p.get("pie", 0),
                        "ts_pct": p.get("ts_pct", 0),
                        "efg_pct": p.get("efg_pct", 0),
                        "usage_pct": p.get("usage_pct", 0)
                    }
            
            # Create document data
            doc_data = {
                "quarter": quarter_label,
                "game_id": game_id,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "player_count": len(players_map),
                "players": players_map,
                "archived_at": datetime.utcnow().isoformat(),
                "is_final": is_final
            }
            
            # Write to Firestore: pulse_stats/{date}/games/{game_id}/quarters/{quarter}
            # Using nested document paths
            doc_path = f"pulse_stats/{today}/games/{game_id}/quarters/{quarter_label}"
            
            await self._firebase.set_document_nested(
                path=doc_path,
                data=doc_data
            )
            
            # Also update date document metadata
            await self._firebase.set_document_nested(
                path=f"pulse_stats/{today}",
                data={
                    "date": today,
                    "updated_at": datetime.utcnow().isoformat()
                },
                merge=True
            )
            
            # Update game document metadata
            await self._firebase.set_document_nested(
                path=f"pulse_stats/{today}/games/{game_id}",
                data={
                    "game_id": game_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "updated_at": datetime.utcnow().isoformat()
                },
                merge=True
            )
            
            logger.debug(f"Saved {quarter_label} with {len(players_map)} players to {doc_path}")

            # ── Auto-populate player_game_stats on FINAL ─────────────────
            # Denormalize per-player stats so /player-data/logs/{pid}
            # returns instantly from player_game_stats/{pid}/games/
            if is_final and players_map:
                try:
                    from firestore_db import get_firestore_db
                    db = get_firestore_db()
                    batch = db.batch()
                    batch_count = 0

                    for pid, pdata in players_map.items():
                        team = pdata.get("team", "")
                        if team == away_team:
                            matchup = f"{team} @ {home_team}"
                            wl = "W" if away_score > home_score else "L"
                        elif team == home_team:
                            matchup = f"{team} vs. {away_team}"
                            wl = "W" if home_score > away_score else "L"
                        else:
                            matchup = f"{home_team} vs {away_team}"
                            wl = ""

                        raw_min = pdata.get("min", 0)
                        if isinstance(raw_min, str) and ":" in raw_min:
                            raw_min = float(raw_min.split(":")[0])

                        fga = int(pdata.get("fga", 1) or 1)
                        fgm = int(pdata.get("fgm", 0) or 0)
                        fg3m = int(pdata.get("fg3m", 0) or 0)
                        fg3a = int(pdata.get("fg3a", 1) or 1)
                        fta = int(pdata.get("fta", 1) or 1)
                        ftm = int(pdata.get("ftm", 0) or 0)

                        doc_id = f"{today}_{game_id}"
                        player_log = {
                            "GAME_ID": game_id,
                            "GAME_DATE": today,
                            "MATCHUP": matchup,
                            "WL": wl,
                            "MIN": float(raw_min or 0),
                            "PTS": int(pdata.get("pts", 0) or 0),
                            "REB": int(pdata.get("reb", 0) or 0),
                            "AST": int(pdata.get("ast", 0) or 0),
                            "STL": int(pdata.get("stl", 0) or 0),
                            "BLK": int(pdata.get("blk", 0) or 0),
                            "TOV": int(pdata.get("to", 0) or 0),
                            "FG_PCT": round(fgm / max(fga, 1), 3),
                            "FG3_PCT": round(fg3m / max(fg3a, 1), 3),
                            "FT_PCT": round(ftm / max(fta, 1), 3),
                            "PLUS_MINUS": float(pdata.get("plus_minus", 0) or 0),
                            "player_name": pdata.get("name", f"Player {pid}"),
                            "team": team,
                        }

                        ref = (
                            db.collection("player_game_stats")
                            .document(str(pid))
                            .collection("games")
                            .document(doc_id)
                        )
                        batch.set(ref, player_log, merge=True)
                        batch_count += 1

                        if batch_count >= 450:
                            batch.commit()
                            batch = db.batch()
                            batch_count = 0

                    if batch_count > 0:
                        batch.commit()

                    logger.info(
                        f"📋 Auto-populated player_game_stats for {len(players_map)} "
                        f"players from game {game_id}"
                    )
                except Exception as e:
                    logger.warning(f"[player_game_stats] Auto-populate failed: {e}")
            
        except Exception as e:
            logger.error(f"Failed to archive quarter stats: {e}")
    
    async def get_quarter_stats(
        self,
        date: str,
        game_id: str,
        quarter: str = "FINAL"
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve archived stats for a specific quarter.
        
        Args:
            date: Date string (YYYY-MM-DD)
            game_id: NBA game ID
            quarter: Q1, Q2, Q3, Q4, or FINAL
            
        Returns:
            Stats document or None
        """
        if not self._firebase:
            return None
        
        try:
            path = f"pulse_stats/{date}/games/{game_id}/quarters/{quarter}"
            return await self._firebase.get_document_nested(path)
        except Exception as e:
            logger.error(f"Failed to get quarter stats: {e}")
            return None


# Singleton instance
_archiver: Optional[PulseStatsArchiver] = None


def get_pulse_archiver() -> PulseStatsArchiver:
    """Get or create the global pulse archiver singleton."""
    global _archiver
    if _archiver is None:
        _archiver = PulseStatsArchiver()
    return _archiver
