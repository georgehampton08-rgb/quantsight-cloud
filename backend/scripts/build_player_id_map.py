#!/usr/bin/env python3
"""
build_player_id_map.py
======================
Builds a complete NBA-player-ID → ESPN-athlete-ID mapping by:
  1. Fetching all 30 ESPN team rosters (ESPN IDs + names)
  2. Matching against existing Firestore `player_injuries` (has espnId already)
  3. Fetching ESPN summary for recent games and extracting box-score athlete IDs
  4. Writing `player_id_map/{nbaPlayerId}` docs to Firestore

After this runs once, every other service can call:
    db.collection("player_id_map").document(nba_id).get()
    → { espn_id, name, team, updated_at }

Run from: quantsight_cloud_build/backend/
    python scripts/build_player_id_map.py
"""
import sys, os, json, time, urllib.request, logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from firestore_db import get_firestore_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.espn.com/nba/",
}


def espn_get(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 ** attempt)
            else:
                log.warning(f"ESPN fetch failed: {url} — {e}")
    return {}


# ── Step 1: Get all ESPN team IDs ────────────────────────────────────────────

def get_espn_teams() -> list[dict]:
    data = espn_get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=40")
    sports = data.get("sports", [{}])
    leagues = sports[0].get("leagues", [{}])
    teams = leagues[0].get("teams", [])
    return [t.get("team", t) for t in teams]


# ── Step 2: Get ESPN roster for each team ────────────────────────────────────

def get_team_roster(espn_team_id: str) -> list[dict]:
    """Returns list of {espn_id, name, team_abbr}"""
    data = espn_get(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{espn_team_id}/roster"
    )
    players = []
    for athlete in data.get("athletes", []):
        espn_id = str(athlete.get("id", ""))
        name = athlete.get("fullName", athlete.get("displayName", ""))
        team_abbr = (data.get("team") or {}).get("abbreviation", "")
        if espn_id:
            players.append({"espn_id": espn_id, "name": name, "team": team_abbr})
    return players


# ── Step 3: Build name→espn_id lookup ────────────────────────────────────────

def build_espn_name_map() -> dict:
    """Dict of normalized_name → {espn_id, name, team}"""
    log.info("Fetching all 30 ESPN team rosters...")
    teams = get_espn_teams()
    name_map = {}
    for team in teams:
        tid = str(team.get("id", ""))
        if not tid:
            continue
        roster = get_team_roster(tid)
        for p in roster:
            key = p["name"].lower().strip()
            name_map[key] = p
        log.info(f"  {team.get('abbreviation', tid)}: {len(roster)} players")
        time.sleep(0.4)
    log.info(f"Total ESPN athletes: {len(name_map)}")
    return name_map


# ── Step 4: Match Firestore player_injuries → get NBA IDs ───────────────────

def get_nba_to_espn_from_injuries(db) -> dict:
    """
    player_injuries docs keyed by ESPN athlete ID contain:
      { playerId (espn), playerName, nbaId (optional), team, ... }
    Returns dict: nba_id → { espn_id, name, team }
    """
    mapping = {}
    docs = db.collection("player_injuries").stream()
    for doc in docs:
        data = doc.to_dict()
        espn_id = str(doc.id)
        nba_id = str(data.get("nbaId") or data.get("nba_id") or "")
        name = data.get("playerName") or data.get("name") or ""
        team = data.get("team") or ""
        if nba_id and nba_id != "None":
            mapping[nba_id] = {"espn_id": espn_id, "name": name, "team": team}
    log.info(f"Injury collection matches: {len(mapping)} NBA→ESPN ID pairs")
    return mapping


# ── Step 5: Match via ESPN game summaries (box score has athlete IDs) ─────────

def get_espn_ids_from_recent_games(db, name_map: dict) -> dict:
    """
    For recent games in game_id_map, fetch ESPN summary boxscore.
    Each athlete entry has: { id (espn), displayName }
    Returns additional name→espn_id pairs.
    """
    from google.cloud.firestore_v1.base_query import FieldFilter
    ET = timezone(timedelta(hours=-4))
    today = datetime.now(ET)
    dates = [(today - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(14)]

    extra_map = {}
    game_count = 0

    for date in dates:
        try:
            docs = list(db.collection("game_id_map").where(
                filter=FieldFilter("date", "==", date)
            ).stream())
        except Exception as e:
            log.warning(f"game_id_map query failed for {date}: {e}")
            continue

        for doc in docs:
            espn_game_id = doc.to_dict().get("espn_id")
            if not espn_game_id:
                continue
            data = espn_get(
                f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espn_game_id}"
            )
            bs = data.get("boxScore", {})
            for team_data in bs.get("players", []):
                for stat_group in team_data.get("statistics", []):
                    for athlete in stat_group.get("athletes", []):
                        a = athlete.get("athlete", {})
                        espn_id = str(a.get("id", ""))
                        dname = a.get("displayName", "")
                        if espn_id and dname:
                            extra_map[dname.lower().strip()] = {
                                "espn_id": espn_id,
                                "name": dname,
                            }
            game_count += 1
            time.sleep(0.3)

    log.info(f"Box score extraction: {len(extra_map)} players from {game_count} games")
    return extra_map


# ── Step 6: Get NBA players from Firestore players collection ────────────────

def get_nba_players_from_firestore(db) -> list:
    """
    players/{nba_id} docs have: { name, position, is_active, ... }
    Doc ID is the NBA player ID.
    """
    players = []
    seen = set()
    try:
        docs = db.collection("players").where(
            filter=__import__('google.cloud.firestore_v1.base_query', fromlist=['FieldFilter']).FieldFilter("is_active", "==", True)
        ).stream()
    except Exception:
        # Fallback: just stream all if the filter fails
        docs = db.collection("players").stream()

    for doc in docs:
        data = doc.to_dict()
        nba_id = str(doc.id)
        if nba_id in seen:
            continue
        seen.add(nba_id)
        name = data.get("full_name") or data.get("name") or ""
        team = data.get("team_abbreviation") or data.get("team") or ""
        if name:
            players.append({"nba_id": nba_id, "name": name, "team": team})

    log.info(f"NBA players found in players collection: {len(players)}")
    return players



# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    db = get_firestore_db()
    log.info("=" * 60)
    log.info("BUILDING PLAYER ID MAP (NBA → ESPN)")
    log.info("=" * 60)

    # Gather ESPN name→id map from all 30 rosters
    espn_name_map = build_espn_name_map()

    # Also gather from box score data (wider coverage for all active players)
    box_score_map = get_espn_ids_from_recent_games(db, espn_name_map)
    espn_name_map.update(box_score_map)

    # Get existing nba_id→espn_id matches from injury collection
    injury_map = get_nba_to_espn_from_injuries(db)

    # Get NBA players from pulse_stats
    nba_players = get_nba_players_from_firestore(db)

    # Merge: for each NBA player, find their ESPN ID
    final_map = dict(injury_map)  # Start with confirmed injury matches
    matched = len(final_map)
    unmatched = []

    for p in nba_players:
        nba_id = p["nba_id"]
        if nba_id in final_map:
            continue  # Already have it

        name_key = p["name"].lower().strip()
        if name_key in espn_name_map:
            espn_data = espn_name_map[name_key]
            final_map[nba_id] = {
                "espn_id": espn_data["espn_id"],
                "name": p["name"],
                "team": espn_data.get("team", p.get("team", "")),
            }
            matched += 1
        else:
            unmatched.append(p["name"])

    log.info(f"Total mapped: {len(final_map)} | Unmatched: {len(unmatched)}")
    if unmatched:
        log.info(f"Unmatched players: {unmatched[:10]}{'...' if len(unmatched) > 10 else ''}")

    # Write to Firestore in batches of 500
    log.info("Writing player_id_map to Firestore...")
    now = datetime.now(timezone.utc).isoformat()
    batch = db.batch()
    count = 0
    written = 0

    for nba_id, data in final_map.items():
        ref = db.collection("player_id_map").document(str(nba_id))
        batch.set(ref, {**data, "nba_id": str(nba_id), "updated_at": now})
        count += 1
        if count % 499 == 0:
            batch.commit()
            written += count
            log.info(f"  Committed {written} docs...")
            batch = db.batch()
            count = 0

    if count > 0:
        batch.commit()
        written += count

    log.info(f"Done! Wrote {written} player_id_map docs to Firestore.")
    log.info("Collection: player_id_map/{{nba_id}} = { espn_id, name, team, updated_at }")


if __name__ == "__main__":
    main()
