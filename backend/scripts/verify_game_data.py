#!/usr/bin/env python3
"""
verify_game_data.py — QuantSight Data Integrity Checker
=========================================================
Verifies consistency across Firestore collections for one or more NBA game dates.

Checks performed per date:
  1. game_id_map   — how many NBA/ESPN IDs are mapped to the date
  2. pulse_stats   — timezone bleed (games recorded on wrong UTC date)
  3. Unmapped games — pulse_stats games with no game_id_map entry
  4. PBP presence  — ESPN-mapped games with zero play-by-play events
  5. Calendar index — ESPN-mapped games missing from calendar/{date}/games/

Run from: quantsight_cloud_build/backend/

Usage:
  python scripts/verify_game_data.py                  # yesterday
  python scripts/verify_game_data.py --date 2026-03-15
  python scripts/verify_game_data.py --days 7         # last 7 days
"""

import sys
import argparse
import logging
from datetime import datetime, timedelta

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from firestore_db import get_firestore_db
except ImportError:
    print("Fatal: Could not import get_firestore_db. Run from the backend directory.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _check_calendar(db, date_str: str, espn_id: str) -> bool:
    """Return True if espn_id exists in calendar/{date}/games/."""
    try:
        doc = db.collection("calendar").document(date_str).collection("games").document(espn_id).get()
        return doc.exists
    except Exception:
        return False


def verify_date(db, date_str: str) -> bool:
    """
    Run all integrity checks for a single date.
    Returns True if no blocking issues found.
    """
    logger.info(f"{'─' * 55}")
    logger.info(f"Verifying: {date_str}")

    from google.cloud.firestore_v1.base_query import FieldFilter

    issues_found = False

    # ── 1. game_id_map ────────────────────────────────────────────────────────
    mapped_nba_ids: dict[str, str] = {}   # nba_id  → espn_id
    mapped_espn_ids: set[str] = set()
    for doc in db.collection("game_id_map").where(filter=FieldFilter("date", "==", date_str)).stream():
        d = doc.to_dict()
        nba_id  = d.get("nba_id", "")
        espn_id = d.get("espn_id", "")
        if nba_id:
            mapped_nba_ids[nba_id] = espn_id
        if espn_id:
            mapped_espn_ids.add(espn_id)

    logger.info(
        f"  game_id_map  : {len(mapped_nba_ids)} NBA IDs | "
        f"{len(mapped_espn_ids)} ESPN IDs mapped to {date_str}"
    )

    # ── 2. pulse_stats (raw tracking) & timezone bleed ────────────────────────
    pulse_docs = list(db.collection("pulse_stats").document(date_str).collection("games").stream())
    pulse_nba_ids = [d.id for d in pulse_docs]
    logger.info(f"  pulse_stats  : {len(pulse_nba_ids)} games recorded on {date_str} (UTC)")

    bled = []
    for nba_id in pulse_nba_ids:
        doc = db.collection("game_id_map").document(nba_id).get()
        if doc.exists:
            actual = doc.to_dict().get("date")
            if actual and actual != date_str:
                bled.append((nba_id, actual))

    if bled:
        logger.warning(f"  ⚠️  TIMEZONE BLEED: {len(bled)} game(s) in pulse_stats belong to a different date")
        for nba_id, actual in bled:
            logger.warning(f"      NBA {nba_id} → actually {actual}")
        # Bleed is a warning, not a hard failure (it's a known UTC/ET edge case)

    # ── 3. Unmapped games ─────────────────────────────────────────────────────
    unmapped = [
        nba_id for nba_id in pulse_nba_ids
        if nba_id not in mapped_nba_ids
        and not db.collection("game_id_map").document(nba_id).get().exists
    ]
    if unmapped:
        logger.warning(f"  ⚠️  UNMAPPED GAMES: {len(unmapped)} pulse_stats game(s) have no game_id_map entry")
        for nba_id in unmapped:
            logger.warning(f"      NBA {nba_id} — no ESPN mapping found")
        issues_found = True

    # ── 4. PBP presence check ─────────────────────────────────────────────────
    pbp_missing = []
    cal_missing = []
    for espn_id in sorted(mapped_espn_ids):
        if not espn_id:
            continue
        # PBP events
        events = list(
            db.collection("pbp_events").document(espn_id).collection("events").limit(1).stream()
        )
        if not events:
            pbp_missing.append(espn_id)

        # ── 5. Calendar index cross-check ──────────────────────────────────
        if not _check_calendar(db, date_str, espn_id):
            cal_missing.append(espn_id)

    if pbp_missing:
        logger.error(f"  ✗  PBP MISSING: {len(pbp_missing)} ESPN game(s) have 0 play-by-play events")
        for eid in pbp_missing:
            logger.error(f"      ESPN {eid}")
        issues_found = True
    else:
        logger.info(f"  ✓  PBP: all {len(mapped_espn_ids)} mapped ESPN game(s) have play data")

    if cal_missing:
        logger.warning(f"  ⚠️  CALENDAR INDEX: {len(cal_missing)} ESPN game(s) not in calendar/{date_str}/games/")
        for eid in cal_missing:
            logger.warning(f"      ESPN {eid}")
        issues_found = True
    else:
        logger.info(f"  ✓  CALENDAR: all {len(mapped_espn_ids)} ESPN game(s) indexed in calendar/")

    status = "FAILED ✗" if issues_found else "PASSED ✓"
    logger.info(f"  Result: {status}")
    return not issues_found


def main():
    parser = argparse.ArgumentParser(description="QuantSight game data integrity checker")
    parser.add_argument("--date",  help="Single date YYYY-MM-DD to check")
    parser.add_argument("--days",  type=int, default=1, help="Number of previous days to check (default: 1 = yesterday)")
    args = parser.parse_args()

    db = get_firestore_db()

    if args.date:
        dates = [args.date]
    else:
        today = datetime.now()
        dates = [
            (today - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(1, args.days + 1)
        ]

    all_passed = True
    for d in dates:
        if not verify_date(db, d):
            all_passed = False

    logger.info("═" * 55)
    if all_passed:
        logger.info("All dates PASSED integrity checks.")
        sys.exit(0)
    else:
        logger.error("One or more dates FAILED integrity checks.")
        sys.exit(1)


if __name__ == "__main__":
    main()
