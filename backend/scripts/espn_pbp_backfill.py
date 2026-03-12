#!/usr/bin/env python3
"""
ESPN PBP Historical Backfill Script — ESPN-Only Edition
=========================================================
Uses ESPN as the sole data source. No NBA API dependency.

Strategy for each date:
  1. Query ESPN scoreboard for that date to get all game IDs
  2. For each game found on ESPN, fetch full PBP from summary endpoint
  3. Store plays under pbp_events/{espnId}/events/
  4. Update game_id_map with NBA<->ESPN mapping (matching by team/date)
  5. Already-have-data games are skipped (idempotent)

Covers: 2026-02-01 through today (or --date / --start for custom range)

Run from: quantsight_cloud_build/backend/
Usage:
  python scripts/espn_pbp_backfill.py                   # full backfill Feb 1 → today
  python scripts/espn_pbp_backfill.py --date 2026-03-07 # single date
  python scripts/espn_pbp_backfill.py --start 2026-03-01# custom start
  python scripts/espn_pbp_backfill.py --dry-run         # no writes
  python scripts/espn_pbp_backfill.py --force           # re-fetch even if already stored
  python scripts/espn_pbp_backfill.py --resume          # skip dates already completed

Rate limits (tunable via flags):
  --delay-game N   seconds between game fetches (default: 1.2)
  --delay-date N   seconds between dates (default: 2.0)
"""

import sys, asyncio, argparse, logging, json, os
from datetime import datetime, timedelta, date as DateType

sys.path.insert(0, '.')

import aiohttp
from firestore_db import get_firestore_db
from services.nba_pbp_service import map_espn_to_unified
from services.firebase_pbp_service import FirebasePBPService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("espn_backfill")

# ── ESPN endpoints ─────────────────────────────────────────────────────────────
ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/"
    "scoreboard?dates={date}&limit=30"
)
# Alternate: broader event list via ESPN calendar (catches All-Star + edge cases)
ESPN_EVENTS_ALT = (
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events"
    "?dates={date}&limit=50"
)
ESPN_SUMMARY = (
    "https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.espn.com/nba/",
}

# Backfill range — go back to Feb 1
BACKFILL_START = DateType(2026, 2, 1)

# Progress checkpoint file (sits in backend/ dir, gitignored)
PROGRESS_FILE = ".backfill_progress.json"

# ── Tricode normalization: ESPN → NBA standard ─────────────────────────────────
ESPN_TRICODE_MAP = {
    "GS":   "GSW",   # Golden State
    "NY":   "NYK",   # New York
    "NO":   "NOP",   # New Orleans
    "SA":   "SAS",   # San Antonio
    "UTAH": "UTA",   # Utah (4-char ESPN variant)
    "UT":   "UTA",   # Utah alt
    "LA":   "LAC",   # LA Clippers (ESPN "LA" = Clippers; LAL stays as LAL)
    "WSH":  "WAS",   # Washington
    "GOS":  "GSW",   # Golden State alt
}

def norm(t: str) -> str:
    return ESPN_TRICODE_MAP.get(t.upper(), t.upper())


# ── Firestore helpers ──────────────────────────────────────────────────────────

def get_existing_espn_ids(db) -> set:
    """Get all ESPN IDs that already have data in pbp_events."""
    ids = set()
    top_docs = list(db.collection("pbp_events").limit(100).stream())
    for d in top_docs:
        ids.add(d.id)
    return ids


def get_existing_map_by_espn(db) -> dict:
    """Return {espn_id: nba_id} from game_id_map."""
    result = {}
    for d in db.collection("game_id_map").stream():
        data = d.to_dict()
        espn = data.get("espn_id", "")
        nba = data.get("nba_id", "")
        if espn:
            result[espn] = nba
    return result


def get_pulse_games_by_date(db, date_str: str) -> dict:
    """
    Return {frozenset({home,away}): nba_id} from pulse_stats.
    Checks the given date PLUS ±1 day to handle ESPN/NBA timezone drift.
    """
    result = {}
    from datetime import datetime, timedelta
    base = datetime.strptime(date_str, "%Y-%m-%d")
    for delta in [0, -1, 1]:  # check same day first, then yesterday, then tomorrow
        check_date = (base + timedelta(days=delta)).strftime("%Y-%m-%d")
        docs = db.collection("pulse_stats").document(check_date).collection("games").stream()
        for d in docs:
            data = d.to_dict()
            home = data.get("home_team", "")
            away = data.get("away_team", "")
            if home and away:
                key = frozenset([home, away])
                if key not in result:  # don't overwrite same-day matches
                    result[key] = d.id
    return result


def has_pbp(db, espn_id: str) -> bool:
    docs = list(
        db.collection("pbp_events")
        .document(str(espn_id))
        .collection("events")
        .limit(1)
        .stream()
    )
    return bool(docs)


# ── ESPN fetch ─────────────────────────────────────────────────────────────────

async def get_all_espn_games_for_date(session: aiohttp.ClientSession, date_str: str) -> list:
    """
    Return list of {espn_id, home_team, away_team, status} for every NBA game on date_str.

    Strategy:
    1. ESPN main scoreboard (most data, caps at ~30)
    2. ESPN core events API (catches games missing from main scoreboard)
    """
    espn_date = date_str.replace("-", "")
    games = []
    seen_ids = set()

    # Strategy 1: main scoreboard
    try:
        url = ESPN_SCOREBOARD.format(date=espn_date)
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as r:
            data = await r.json()
        for e in data.get("events", []):
            g = _parse_espn_event(e)
            if g and g["espn_id"] not in seen_ids:
                games.append(g)
                seen_ids.add(g["espn_id"])
    except Exception as ex:
        log.debug(f"  scoreboard error: {ex}")

    if games:
        return games

    # Strategy 2: ESPN core events calendar (broader — catches All-Star weekend etc)
    try:
        url2 = ESPN_EVENTS_ALT.format(date=espn_date)
        async with session.get(url2, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as r:
            data2 = await r.json()
        items = data2.get("items", [])
        for item in items:
            ref = item.get("$ref", "")
            eid = ref.split("/events/")[-1].split("?")[0] if "/events/" in ref else ""
            if eid and eid not in seen_ids:
                # Fetch the event summary to get teams
                try:
                    async with session.get(
                        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={eid}",
                        headers=HEADERS, timeout=aiohttp.ClientTimeout(total=12)
                    ) as er:
                        ed = await er.json()
                    header = ed.get("header", {})
                    comps = header.get("competitions", [{}])[0] if header.get("competitions") else {}
                    teams = comps.get("competitors", [])
                    away_raw = next((t.get("team", {}).get("abbreviation", "") for t in teams if t.get("homeAway") == "away"), "")
                    home_raw = next((t.get("team", {}).get("abbreviation", "") for t in teams if t.get("homeAway") == "home"), "")
                    if away_raw and home_raw:
                        games.append({"espn_id": eid, "home_team": norm(home_raw), "away_team": norm(away_raw), "score_home": 0, "score_away": 0, "status": "Final"})
                        seen_ids.add(eid)
                        await asyncio.sleep(0.3)
                except Exception:
                    pass
    except Exception as ex:
        log.debug(f"  events alt error: {ex}")

    return games


def _parse_espn_event(e: dict) -> dict | None:
    comps = e.get("competitions", [{}])[0]
    teams = comps.get("competitors", [])
    away_raw = next((t["team"]["abbreviation"] for t in teams if t["homeAway"] == "away"), "")
    home_raw = next((t["team"]["abbreviation"] for t in teams if t["homeAway"] == "home"), "")
    if not away_raw or not home_raw:
        return None
    away_score = next((int(t.get("score", 0) or 0) for t in teams if t["homeAway"] == "away"), 0)
    home_score = next((int(t.get("score", 0) or 0) for t in teams if t["homeAway"] == "home"), 0)
    return {
        "espn_id": e["id"],
        "home_team": norm(home_raw),
        "away_team": norm(away_raw),
        "score_home": home_score,
        "score_away": away_score,
        "status": comps.get("status", {}).get("type", {}).get("description", ""),
    }


def _parse_cdn_event(e: dict) -> dict | None:
    comps = e.get("competitions", [{}])[0] if e.get("competitions") else {}
    teams = comps.get("competitors", []) if comps else e.get("competitors", [])
    away_raw = next((t.get("abbreviation", t.get("team", {}).get("abbreviation", "")) for t in teams if t.get("homeAway") == "away"), "")
    home_raw = next((t.get("abbreviation", t.get("team", {}).get("abbreviation", "")) for t in teams if t.get("homeAway") == "home"), "")
    eid = e.get("id", "")
    if not away_raw or not home_raw or not eid:
        return None
    return {
        "espn_id": eid,
        "home_team": norm(home_raw),
        "away_team": norm(away_raw),
        "score_home": 0,
        "score_away": 0,
        "status": "Final",
    }


async def fetch_espn_plays(session: aiohttp.ClientSession, espn_id: str, retries: int = 3) -> list:
    """Fetch plays from ESPN summary with exponential backoff on failure."""
    url = ESPN_SUMMARY.format(event_id=espn_id)
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                r.raise_for_status()
                data = await r.json()
            return data.get("plays", [])
        except Exception as e:
            wait = 2 ** attempt  # 2s, 4s, 8s
            if attempt < retries:
                log.warning(f"    ESPN summary attempt {attempt}/{retries} failed ({e}) — retrying in {wait}s")
                await asyncio.sleep(wait)
            else:
                log.warning(f"    ESPN summary failed after {retries} attempts: {e}")
    return []


# ── Per-date processor ─────────────────────────────────────────────────────────

async def process_date(
    session: aiohttp.ClientSession,
    db,
    date_str: str,
    dry_run: bool,
    force: bool,
    delay_game: float = 1.2,
) -> dict:
    log.info(f"\n{'='*55}\nDate: {date_str}")

    # Who do we already have PBP data for?
    existing_map = get_existing_map_by_espn(db)  # espn_id -> nba_id

    # Pulse stats games for this date (for NBA<->ESPN mapping)
    pulse_by_teams = get_pulse_games_by_date(db, date_str)  # frozenset({h,a}) -> nba_id

    # Get all ESPN games for this date
    espn_games = await get_all_espn_games_for_date(session, date_str)
    log.info(f"  ESPN returned {len(espn_games)} games | pulse_stats: {len(pulse_by_teams)} games")

    if not espn_games:
        log.warning(f"  No ESPN games found for {date_str} — skipping")
        return {"date": date_str, "skipped": True}

    results = {"date": date_str, "written": 0, "skipped": 0, "failed": 0, "plays": 0}

    for g in espn_games:
        espn_id = g["espn_id"]
        home = g["home_team"]
        away = g["away_team"]

        label = f"{away}@{home} (ESPN={espn_id})"

        # Skip if already have PBP data and not forcing
        if not force and has_pbp(db, espn_id):
            log.info(f"  ✓ {label} — already stored, skipping fetching plays")
            # STill need to ensure game_id_map is up to date!
            key = frozenset([home, away])
            nba_id = pulse_by_teams.get(key, "")
            
            db.collection("game_id_map").document(espn_id).set({
                "espn_id": espn_id,
                "nba_id": nba_id,
                "date": date_str,
                "home_team": home,
                "away_team": away,
            }, merge=True)
            if nba_id:
                db.collection("game_id_map").document(nba_id).set({
                    "espn_id": espn_id,
                    "nba_id": nba_id,
                    "date": date_str,
                    "home_team": home,
                    "away_team": away,
                }, merge=True)
            results["skipped"] += 1
            continue

        # Find matching NBA ID from pulse_stats
        key = frozenset([home, away])
        nba_id = pulse_by_teams.get(key, "")

        # Fetch plays
        log.info(f"  → {label} | nba={nba_id or 'unknown'}")
        raw_plays = await fetch_espn_plays(session, espn_id)

        if not raw_plays:
            log.warning(f"    No plays returned — skipping")
            results["failed"] += 1
            await asyncio.sleep(0.5)
            continue

        log.info(f"    {len(raw_plays)} plays fetched")

        # Map to PlayEvent schema
        play_events = []
        for p in raw_plays:
            try:
                play_events.append(map_espn_to_unified(p))
            except Exception as ex:
                log.debug(f"    Mapping error: {ex}")

        if dry_run:
            log.info(f"    [DRY RUN] Would write {len(play_events)} plays for {away}@{home}")
            results["written"] += 1
            results["plays"] += len(play_events)
            await asyncio.sleep(0.3)
            continue

        # Write to pbp_events/{espnId}/events/
        written = FirebasePBPService.save_plays_batch_v2(
            game_id=espn_id,
            plays=play_events,
            game_date=date_str,
            home_team=home,
            away_team=away,
        )

        # Update game_id_map (even if nba_id is unknown — still record the ESPN game)
        db.collection("game_id_map").document(espn_id).set({
            "espn_id": espn_id,
            "nba_id": nba_id,
            "date": date_str,
            "home_team": home,
            "away_team": away,
        }, merge=True)
        # Also index by NBA ID if we have one
        if nba_id:
            db.collection("game_id_map").document(nba_id).set({
                "espn_id": espn_id,
                "nba_id": nba_id,
                "date": date_str,
                "home_team": home,
                "away_team": away,
            }, merge=True)

        log.info(f"    ✅ {written} plays written to pbp_events/{espn_id}/")
        results["written"] += 1
        results["plays"] += written

        # Polite rate limit between games
        await asyncio.sleep(delay_game)

    return results


# ── Date range generator ───────────────────────────────────────────────────────

def date_range(start: DateType, end: DateType):
    d = start
    while d <= end:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


# ── Progress checkpoint helpers ────────────────────────────────────────────────

def load_progress() -> set:
    """Return set of dates already completed (from checkpoint file)."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                return set(json.load(f).get("completed", []))
        except Exception:
            pass
    return set()


def save_progress(completed: set):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"completed": sorted(completed), "updated": datetime.now().isoformat()}, f, indent=2)


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="ESPN PBP Backfill — ESPN-only")
    parser.add_argument("--date", help="Single date YYYY-MM-DD")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (default: 2026-02-01)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if data exists")
    parser.add_argument("--resume", action="store_true", help="Skip dates already in checkpoint file")
    parser.add_argument("--delay-game", type=float, default=1.2, help="Seconds between games (default: 1.2)")
    parser.add_argument("--delay-date", type=float, default=2.0, help="Seconds between dates (default: 2.0)")
    args = parser.parse_args()

    db = get_firestore_db()

    if args.date:
        dates = [args.date]
    else:
        start = DateType.fromisoformat(args.start) if args.start else BACKFILL_START
        end = DateType.today()
        dates = list(date_range(start, end))
        log.info(f"Backfill range: {dates[0]} → {dates[-1]} ({len(dates)} dates)")

    if args.dry_run:
        log.info("*** DRY RUN — no Firestore writes ***")

    # Load checkpoint for resume
    completed = load_progress() if args.resume else set()
    if completed:
        log.info(f"Resuming — {len(completed)} dates already completed, skipping them")

    totals = {"games": 0, "plays": 0, "dates_done": 0}

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for date_str in dates:
            if date_str in completed:
                log.info(f"  ↷ {date_str} already completed — skipping")
                continue

            result = await process_date(
                session, db, date_str,
                dry_run=args.dry_run,
                force=args.force,
                delay_game=args.delay_game,
            )
            totals["games"] += result.get("written", 0)
            totals["plays"] += result.get("plays", 0)
            totals["dates_done"] += 1

            # Save checkpoint after each date
            if not args.dry_run:
                completed.add(date_str)
                save_progress(completed)

            await asyncio.sleep(args.delay_date)

    log.info(f"\n{'='*55}")
    log.info(f"BACKFILL COMPLETE")
    log.info(f"  Dates processed : {totals['dates_done']}")
    log.info(f"  Games written   : {totals['games']}")
    log.info(f"  Plays written   : {totals['plays']}")
    log.info(f"{'='*55}")


if __name__ == "__main__":
    asyncio.run(main())
