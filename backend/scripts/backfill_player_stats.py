#!/usr/bin/env python3
"""
backfill_player_stats.py
========================
Backfills last 14 days of player game logs and shot chart data
from ESPN public APIs into Firestore.

Data stored:
  player_game_logs/{espnPlayerId}/games/{espnGameId}
    → pts, reb, ast, stl, blk, to, fg%, 3p%, ft%, min, date, matchup, wl

  shots/{espnGameId}/attempts/{attemptId}
    → x, y, result, period, clock, player_id, player_name, team

Run from: quantsight_cloud_build/backend/
    python scripts/backfill_player_stats.py
"""
import sys, json, time, logging, urllib.request
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

ET = timezone(timedelta(hours=-4))


def espn_get(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.0 + attempt)
            else:
                log.warning(f"ESPN fetch failed: {url} — {e}")
    return {}


def parse_stat(val) -> float:
    """Parse a raw string or number stat value to float."""
    try:
        return float(val) if val and val != '--' else 0.0
    except:
        return 0.0


def parse_ma(val: str) -> tuple[int, int]:
    """Parse 'made-attempted' string like '4-9' → (4, 9). Returns (0,0) on error."""
    try:
        if isinstance(val, str) and '-' in val:
            parts = val.split('-')
            return int(parts[0]), int(parts[1])
        # Might be a raw number (e.g. '14' for points)
        return 0, 0
    except:
        return 0, 0


def parse_espn_stat_group(stat_names: list, stats_raw: list) -> dict:
    """
    ESPN boxscore stat arrays come in a specific order:
      MIN, FG (X-Y), 3PT (X-Y), FT (X-Y), OREB, DREB, REB, AST, STL, BLK, TO, PF, +/-, PTS
    Map names to values then derive percentages from the X-Y strings.
    """
    stats = {}
    for i, name in enumerate(stat_names):
        if i < len(stats_raw):
            stats[name] = stats_raw[i]

    # FG
    fg_m, fg_a = parse_ma(stats.get('FG', '0-0'))
    fg_pct = round(fg_m / fg_a, 3) if fg_a > 0 else 0.0

    # 3PT
    tp_m, tp_a = parse_ma(stats.get('3PT', '0-0'))
    tp_pct = round(tp_m / tp_a, 3) if tp_a > 0 else 0.0

    # FT
    ft_m, ft_a = parse_ma(stats.get('FT', '0-0'))
    ft_pct = round(ft_m / ft_a, 3) if ft_a > 0 else 0.0

    # MIN: ESPN sometimes returns '33:12' — take only the minutes part
    min_raw = stats.get('MIN', '0')
    if isinstance(min_raw, str) and ':' in min_raw:
        min_val = min_raw  # keep as string, endpoint will handle parsing
    else:
        min_val = str(min_raw)

    return {
        'MIN': min_val,
        'FGM': fg_m, 'FGA': fg_a, 'FG_PCT': fg_pct,
        'FG3M': tp_m, 'FG3A': tp_a, 'FG3_PCT': tp_pct,
        'FTM': ft_m, 'FTA': ft_a, 'FT_PCT': ft_pct,
        'OREB': int(parse_stat(stats.get('OREB', 0))),
        'DREB': int(parse_stat(stats.get('DREB', 0))),
        'REB': int(parse_stat(stats.get('REB', 0))),
        'AST': int(parse_stat(stats.get('AST', 0))),
        'STL': int(parse_stat(stats.get('STL', 0))),
        'BLK': int(parse_stat(stats.get('BLK', 0))),
        'TOV': int(parse_stat(stats.get('TO', 0))),
        'PF': int(parse_stat(stats.get('PF', 0))),
        'PLUS_MINUS': int(parse_stat(stats.get('+/-', 0))),
        'PTS': int(parse_stat(stats.get('PTS', 0))),
    }


def get_game_ids_for_date_range(db, days_back: int = 14) -> list[dict]:
    """Get all ESPN game IDs for the last N days from game_id_map."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    today = datetime.now(ET)
    dates = [(today - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(days_back)]
    games = []
    for date in dates:
        try:
            docs = list(db.collection("game_id_map").where(
                filter=FieldFilter("date", "==", date)
            ).stream())
        except Exception:
            docs = list(db.collection("game_id_map").where("date", "==", date).stream())
        for doc in docs:
            data = doc.to_dict()
            espn_id = data.get("espn_id")
            if espn_id:
                games.append({
                    "espn_id": str(espn_id),
                    "date": date,
                    "home": data.get("home_team", ""),
                    "away": data.get("away_team", ""),
                })
    log.info(f"Found {len(games)} games over last {days_back} days")
    return games


def process_game(db, game: dict) -> dict:
    """Fetch ESPN boxscore and store player box scores + shot data."""
    espn_id = game["espn_id"]
    date = game["date"]
    result = {"game_id": espn_id, "players_stored": 0, "shots_stored": 0}

    # ESPN dedicated boxscore endpoint (has historical player stats)
    boxscore_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/boxscore?event={espn_id}"
    data = espn_get(boxscore_url)

    # Fallback: try summary endpoint
    if not data or not data.get("teams"):
        summary_url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espn_id}"
        data = espn_get(summary_url)
        # summary wraps box score under boxScore.players
        if data.get("boxScore"):
            # Restructure to match boxscore API format
            data = {"teams": data.get("boxScore", {}).get("players", [])}

    if not data:
        return result

    now = datetime.now(timezone.utc).isoformat()

    # ── Header/competitor info from boxscore API ─────────────────────────────
    # boxscore endpoint structure: { teams: [ {team, statistics: [{names, labels, athletes}] } ] }
    # competitors: { homeTeam, awayTeam }
    homeTeam = data.get("homeTeam", {}).get("team", {}).get("abbreviation", game["home"])
    awayTeam = data.get("awayTeam", {}).get("team", {}).get("abbreviation", game["away"])
    home_score = int(data.get("homeTeam", {}).get("score", 0) or 0)
    away_score = int(data.get("awayTeam", {}).get("score", 0) or 0)

    # teams[] is the primary player data source
    teams = data.get("teams", [])

    player_batch = db.batch()
    player_count = 0

    for team_data in teams:
        team_abbr = (team_data.get("team") or {}).get("abbreviation", "")
        # ESPN boxscore has homeTeam.team.id and awayTeam.team.id for score lookup
        team_id = str((team_data.get("team") or {}).get("id", ""))
        t_score = int(data.get("homeTeam", {}).get("score", 0) if
                      str(data.get("homeTeam", {}).get("team", {}).get("id", "")) == team_id
                      else data.get("awayTeam", {}).get("score", 0) or 0)
        o_score = away_score if t_score == home_score else home_score
        wl = "W" if t_score > o_score else ("L" if t_score < o_score else "?")
        is_home = str(data.get("homeTeam", {}).get("team", {}).get("id", "")) == team_id
        opp = awayTeam if is_home else homeTeam
        matchup = f"vs {opp}" if is_home else f"@ {opp}"

        for stat_group in team_data.get("statistics", []):
            stat_names = stat_group.get("names", [])

            for athlete_entry in stat_group.get("athletes", []):
                athlete = athlete_entry.get("athlete", {})
                espn_player_id = str(athlete.get("id", ""))
                player_name = athlete.get("displayName", "Unknown")
                stats_raw = athlete_entry.get("stats", [])

                if not espn_player_id or not stats_raw:
                    continue

                s = parse_espn_stat_group(stat_names, stats_raw)
                if s['PTS'] == 0 and s['REB'] == 0 and s['AST'] == 0:
                    continue  # skip DNP rows

                doc = {
                    "espn_player_id": espn_player_id,
                    "espn_game_id": espn_id,
                    "player_name": player_name,
                    "team": team_abbr,
                    "date": date,
                    "matchup": matchup,
                    "MIN": s['MIN'],
                    "PTS": s['PTS'],
                    "REB": s['REB'],
                    "AST": s['AST'],
                    "STL": s['STL'],
                    "BLK": s['BLK'],
                    "TOV": s['TOV'],
                    "PF": s['PF'],
                    "FGM": s['FGM'], "FGA": s['FGA'],
                    "FG_PCT": s['FG_PCT'],
                    "FG3M": s['FG3M'], "FG3A": s['FG3A'],
                    "FG3_PCT": s['FG3_PCT'],
                    "FTM": s['FTM'], "FTA": s['FTA'],
                    "FT_PCT": s['FT_PCT'],
                    "PLUS_MINUS": s['PLUS_MINUS'],
                    "WL": wl,
                    "updated_at": now,
                }

                ref = (db.collection("player_game_logs")
                       .document(espn_player_id)
                       .collection("games")
                       .document(espn_id))
                player_batch.set(ref, doc)
                player_count += 1

                if player_count % 450 == 0:
                    player_batch.commit()
                    player_batch = db.batch()

    if player_count % 450 != 0:
        player_batch.commit()

    result["players_stored"] = player_count


    # ── Shot Chart Attempts ──────────────────────────────────────────────────
    plays = data.get("plays", [])
    shot_batch = db.batch()
    shot_count = 0

    for play in plays:
        if not play.get("coordinate"):
            continue
        coord = play["coordinate"]
        ptype = play.get("type", {})
        shooter = play.get("participants", [{}])[0] if play.get("participants") else {}
        athlete = shooter.get("athlete", {})

        is_shot = ptype.get("id") in (
            "57",   # made 2pt
            "58",   # missed 2pt
            "59",   # made 3pt
            "60",   # missed 3pt
            "61",   # made FT
        )
        if not is_shot:
            continue

        espn_player_id = str(athlete.get("id", ""))
        attempt_id = str(play.get("id", ""))

        doc = {
            "x": coord.get("x", 0),
            "y": coord.get("y", 0),
            "period": play.get("period", {}).get("number", 0),
            "clock": play.get("clock", {}).get("displayValue", ""),
            "result": "made" if ptype.get("id") in ("57", "59", "61") else "missed",
            "is_three": ptype.get("id") in ("59", "60"),
            "score_value": play.get("scoreValue", 0),
            "player_id": espn_player_id,
            "player_name": athlete.get("displayName", ""),
            "team": play.get("team", {}).get("abbreviation", ""),
            "text": play.get("text", ""),
            "date": date,
        }

        ref = db.collection("shots").document(espn_id).collection("attempts").document(attempt_id)
        shot_batch.set(ref, doc)
        shot_count += 1

        if shot_count % 450 == 0:
            shot_batch.commit()
            shot_batch = db.batch()

    if shot_count % 450 != 0:
        shot_batch.commit()

    result["shots_stored"] = shot_count
    return result


def main(days_back: int = 14):
    db = get_firestore_db()
    log.info("=" * 60)
    log.info(f"BACKFILL: Player Stats + Shot Charts — Last {days_back} Days")
    log.info("=" * 60)

    games = get_game_ids_for_date_range(db, days_back=days_back)
    if not games:
        log.warning("No games found in game_id_map. Run espn_pbp_backfill.py first.")
        return

    total_players = 0
    total_shots = 0

    for i, game in enumerate(games):
        log.info(f"[{i+1}/{len(games)}] {game['away']} @ {game['home']} ({game['date']}) ESPN:{game['espn_id']}")
        result = process_game(db, game)
        total_players += result["players_stored"]
        total_shots += result["shots_stored"]
        log.info(f"  → {result['players_stored']} player docs, {result['shots_stored']} shot attempts")
        time.sleep(0.5)  # Be respectful to ESPN CDN

    log.info("=" * 60)
    log.info(f"DONE: {total_players} player game log docs, {total_shots} shot attempts stored")
    log.info("Collections: player_game_logs/{espnId}/games/{gameId}, shots/{gameId}/attempts/")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14, help="Days to backfill (default: 14)")
    args = parser.parse_args()
    main(days_back=args.days)
