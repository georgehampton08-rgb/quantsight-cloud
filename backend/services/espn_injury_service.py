"""
ESPN Injury Poller Service
===========================
Polls ESPN game summaries before/during games to extract injury reports
and stores them in Firestore under:

  player_injuries/{playerId}    ← current status for each player
  team_injuries/{teamTricode}   ← per-team injury summary for today's games

Data source: ESPN game summary endpoint (no extra API key needed)
  https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espnId}

The `injuries` key in the summary contains both teams' lists with:
  - athlete: {id, displayName, position}
  - type: {name}              e.g. "Knee", "Hamstring"
  - status: "Out" | "Questionable" | "Doubtful" | "Day-To-Day" | "Probable"
  - details: {type, side, detail, fantasyStatus}
  - longComment / shortComment: description string

Poll schedule:
  - Every 30 minutes by default
  - On game days: every 10 minutes within 2h of tip-off
  - Injuries cleared for a date at midnight

Run mode: background asyncio.Task started from main.py lifespan
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD  = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_SUMMARY     = "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.espn.com/nba/",
}

POLL_INTERVAL_NORMAL  = 30 * 60   # 30 min on non-game days / early morning
POLL_INTERVAL_GAMEDAY = 10 * 60   # 10 min on game days

# Firestore collections
COLLECTION_PLAYER = "player_injuries"
COLLECTION_TEAM   = "team_injuries"


class ESPNInjuryPoller:
    """
    Background service that polls ESPN for NBA injury reports and stores
    them in Firestore. Designed to run as a long-lived asyncio task inside
    Cloud Run.
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._db = None
        logger.info("🏥 ESPNInjuryPoller initialized")

    # ── DB accessor (lazy) ──────────────────────────────────────────────────

    def _get_db(self):
        if self._db is None:
            from firestore_db import get_firestore_db
            self._db = get_firestore_db()
        return self._db

    # ── Public lifecycle ────────────────────────────────────────────────────

    async def start(self):
        if self._running:
            logger.warning("ESPNInjuryPoller already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="espn_injury_poller")
        logger.info("✅ ESPNInjuryPoller started")

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 ESPNInjuryPoller stopped")

    # ── Core poll loop ──────────────────────────────────────────────────────

    async def _poll_loop(self):
        logger.info("🏥 Injury poll loop running")
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            while self._running:
                try:
                    await self._run_poll(session)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[InjuryPoller] Poll error: {e}", exc_info=True)

                interval = await self._next_interval(session)
                logger.info(f"[InjuryPoller] Next poll in {interval // 60}m")
                await asyncio.sleep(interval)

    async def _next_interval(self, session: aiohttp.ClientSession) -> int:
        """Return shorter interval on game days, longer otherwise."""
        try:
            async with session.get(ESPN_SCOREBOARD, timeout=aiohttp.ClientTimeout(total=8)) as r:
                data = await r.json()
            events = data.get("events", [])
            # Check if any game is within 2h of tip-off or currently live
            now = datetime.now(timezone.utc)
            for e in events:
                state = e.get("status", {}).get("type", {}).get("state", "")
                if state in ("in", "pre"):
                    return POLL_INTERVAL_GAMEDAY
        except Exception:
            pass
        return POLL_INTERVAL_NORMAL

    async def _run_poll(self, session: aiohttp.ClientSession):
        """Fetch today's games from ESPN scoreboard, then pull injuries per game."""
        logger.info("[InjuryPoller] Polling ESPN for today's injury data...")

        # Step 1: Get today's game IDs from ESPN scoreboard (no date = today)
        try:
            async with session.get(ESPN_SCOREBOARD, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
        except Exception as e:
            logger.warning(f"[InjuryPoller] Scoreboard fetch failed: {e}")
            return

        events = data.get("events", [])
        if not events:
            logger.info("[InjuryPoller] No games today — skipping")
            return

        logger.info(f"[InjuryPoller] Found {len(events)} games today")
        today_str = datetime.now().strftime("%Y-%m-%d")

        all_injuries: dict[str, list] = {}   # teamTricode -> [injury dicts]
        player_updates: dict[str, dict] = {}  # playerId   -> injury doc

        for event in events:
            event_id = event.get("id", "")
            comps = event.get("competitions", [{}])[0]
            teams = comps.get("competitors", [])
            home = next((t["team"]["abbreviation"] for t in teams if t["homeAway"] == "home"), "")
            away = next((t["team"]["abbreviation"] for t in teams if t["homeAway"] == "away"), "")

            if not event_id:
                continue

            # Step 2: Pull full game summary for injury data
            await asyncio.sleep(0.5)      # gentle rate limit between games
            try:
                url = ESPN_SUMMARY.format(event_id=event_id)
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
                    summary = await r.json()
            except Exception as e:
                logger.debug(f"[InjuryPoller] Summary fetch failed for {event_id}: {e}")
                continue

            injuries_raw = summary.get("injuries", [])
            # injuries is a list of {team: {$ref}, injuries: [{athlete, type, status...}]}
            for team_block in injuries_raw:
                team_info = team_block.get("team", {})
                team_tricode = team_info.get("abbreviation", "")
                team_injuries = team_block.get("injuries", [])

                if not team_injuries:
                    continue

                team_list = []
                for inj in team_injuries:
                    athlete = inj.get("athlete", {})
                    pid = str(athlete.get("id", ""))
                    name = athlete.get("displayName", "")
                    pos  = athlete.get("position", {}).get("abbreviation", "")
                    status = inj.get("status", "")
                    inj_type = inj.get("type", {}).get("name", "")
                    details = inj.get("details", {})
                    detail_str = details.get("detail", "")
                    side = details.get("side", "")
                    comment = inj.get("longComment", inj.get("shortComment", ""))

                    label = f"{side} {inj_type} ({detail_str})".strip(" ()")
                    if not label:
                        label = inj_type

                    team_list.append({
                        "playerId":   pid,
                        "playerName": name,
                        "position":   pos,
                        "status":     status,
                        "injuryType": label,
                        "comment":    comment,
                        "teamTricode": team_tricode,
                    })

                    # Per-player record
                    if pid:
                        player_updates[pid] = {
                            "playerId":    pid,
                            "playerName":  name,
                            "position":    pos,
                            "teamTricode": team_tricode,
                            "status":      status,
                            "injuryType":  label,
                            "comment":     comment,
                            "updatedAt":   datetime.now(timezone.utc).isoformat(),
                            "gameDate":    today_str,
                        }

                if team_tricode:
                    all_injuries[team_tricode] = team_list

        # Step 3: Write to Firestore
        await self._write_to_firestore(today_str, all_injuries, player_updates)

    async def _write_to_firestore(
        self,
        today_str: str,
        team_injuries: dict[str, list],
        player_updates: dict[str, dict],
    ):
        db = self._get_db()
        batch = db.batch()
        write_count = 0

        # Per-team injury summary (easy to query by tricode)
        for tricode, injuries in team_injuries.items():
            ref = db.collection(COLLECTION_TEAM).document(tricode)
            batch.set(ref, {
                "teamTricode": tricode,
                "date":        today_str,
                "injuries":    injuries,
                "updatedAt":   datetime.now(timezone.utc).isoformat(),
                "count":       len(injuries),
            }, merge=True)
            write_count += 1

        # Per-player injury record
        for pid, doc in player_updates.items():
            ref = db.collection(COLLECTION_PLAYER).document(pid)
            batch.set(ref, doc, merge=True)
            write_count += 1

        if write_count:
            try:
                batch.commit()
                logger.info(
                    f"[InjuryPoller] ✅ Wrote {len(team_injuries)} team injury summaries "
                    f"+ {len(player_updates)} player records"
                )
            except Exception as e:
                logger.error(f"[InjuryPoller] Firestore write failed: {e}")
        else:
            logger.info("[InjuryPoller] No injuries found today — collections unchanged")


# ── Singleton & lifecycle helpers ──────────────────────────────────────────────

_poller: Optional[ESPNInjuryPoller] = None


def get_injury_poller() -> ESPNInjuryPoller:
    global _poller
    if _poller is None:
        _poller = ESPNInjuryPoller()
    return _poller


async def start_injury_poller():
    await get_injury_poller().start()


async def stop_injury_poller():
    await get_injury_poller().stop()
