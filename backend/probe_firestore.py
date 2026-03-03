"""Validate the rewritten methods locally"""
import sys
sys.path.insert(0, '.')
from services.firebase_admin_service import FirebaseAdminService

svc = FirebaseAdminService()

print("=== get_game_dates() ===")
dates = svc.get_game_dates()
print(f"Dates: {dates}")

if dates:
    d = '2026-02-28'  # known good date with FINAL
    print(f"\n=== get_box_scores_for_date({d}) ===")
    games = svc.get_box_scores_for_date(d)
    print(f"Found {len(games)} games")
    for g in games:
        print(f"  {g['matchup']} | {g['away_score']}-{g['home_score']} | {g['status']} | winner={g['winner']}")
