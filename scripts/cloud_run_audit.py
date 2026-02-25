"""
Cloud Run API Audit Script
===========================
Hits all known endpoints against the Cloud Run base URL.
Saves report to reports/cloud_run_audit_<timestamp>.json
"""
import requests
import json
import time
import os
from datetime import datetime

BASE = "https://quantsight-cloud-458498663186.us-central1.run.app"
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

ENDPOINTS = [
    # ── Core Health ──────────────────────────────────────────────────
    {"name": "health",               "method": "GET",  "path": "/health"},
    {"name": "status",               "method": "GET",  "path": "/status"},
    {"name": "root",                 "method": "GET",  "path": "/"},

    # ── Schedule / Live ───────────────────────────────────────────────
    {"name": "schedule",             "method": "GET",  "path": "/schedule"},
    {"name": "matchup_lab_games",    "method": "GET",  "path": "/matchup-lab/games"},
    {"name": "live_games",           "method": "GET",  "path": "/live/games"},
    {"name": "live_leaders",         "method": "GET",  "path": "/live/leaders"},
    {"name": "live_pulse_status",    "method": "GET",  "path": "/live/status"},

    # ── Teams / Roster / Injuries ──────────────────────────────────────
    {"name": "teams",                "method": "GET",  "path": "/teams"},
    {"name": "injuries",             "method": "GET",  "path": "/injuries"},
    {"name": "roster_LAL",           "method": "GET",  "path": "/roster/LAL"},
    {"name": "roster_BOS",           "method": "GET",  "path": "/roster/BOS"},
    {"name": "team_by_abbrev",       "method": "GET",  "path": "/teams/LAL"},

    # ── Players ───────────────────────────────────────────────────────
    {"name": "players_search_q",     "method": "GET",  "path": "/players/search?q=lebron"},
    {"name": "players_all",          "method": "GET",  "path": "/players"},
    {"name": "player_by_id",         "method": "GET",  "path": "/players/2544"},

    # ── Matchup Engine ─────────────────────────────────────────────────
    {"name": "player_matchup",       "method": "GET",  "path": "/matchup/2544/LAL"},
    {"name": "matchup_analyze",      "method": "GET",  "path": "/matchup/analyze?home_team=LAL&away_team=BOS"},
    {"name": "radar_player",         "method": "GET",  "path": "/radar/2544"},

    # ── Aegis ─────────────────────────────────────────────────────────
    {"name": "aegis_player",         "method": "GET",  "path": "/aegis/player/2544"},
    {"name": "aegis_player_stats",   "method": "GET",  "path": "/aegis/player/2544/stats"},
    {"name": "aegis_matchup_qp",     "method": "GET",  "path": "/aegis/matchup?home_team_id=LAL&away_team_id=BOS"},
    {"name": "aegis_stats",          "method": "GET",  "path": "/aegis/stats"},

    # ── Nexus ─────────────────────────────────────────────────────────
    {"name": "nexus_health",         "method": "GET",  "path": "/nexus/health"},
    {"name": "nexus_overview",       "method": "GET",  "path": "/nexus/overview"},
    {"name": "nexus_cooldowns",      "method": "GET",  "path": "/nexus/cooldowns"},
    {"name": "nexus_route_matrix",   "method": "GET",  "path": "/nexus/route-matrix"},

    # ── Vanguard ─────────────────────────────────────────────────────
    {"name": "vanguard_health",      "method": "GET",  "path": "/vanguard/health"},
]


def test_endpoint(ep):
    url = BASE + ep["path"]
    method = ep.get("method", "GET")
    body = ep.get("body")
    headers = {"Content-Type": "application/json"}

    try:
        start = time.time()
        if method == "POST":
            resp = requests.post(url, json=body, headers=headers, timeout=20)
        else:
            resp = requests.get(url, headers=headers, timeout=20)
        latency_ms = int((time.time() - start) * 1000)

        try:
            resp_json = resp.json()
        except Exception:
            resp_json = None

        snippet = resp.text[:500] if resp.text else ""

        return {
            "name": ep["name"],
            "path": ep["path"],
            "method": method,
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "pass": resp.status_code < 400,
            "snippet": snippet,
            "json": resp_json,
            "error": None,
        }
    except requests.exceptions.Timeout:
        return {
            "name": ep["name"], "path": ep["path"], "method": method,
            "status_code": None, "latency_ms": 20000, "pass": False,
            "snippet": None, "json": None, "error": "TIMEOUT"
        }
    except Exception as exc:
        return {
            "name": ep["name"], "path": ep["path"], "method": method,
            "status_code": None, "latency_ms": None, "pass": False,
            "snippet": None, "json": None, "error": str(exc)
        }


def main():
    print(f"\n{'='*70}")
    print(f"QuantSight Cloud Run Audit — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base URL: {BASE}")
    print(f"{'='*70}\n")

    results = []
    for ep in ENDPOINTS:
        result = test_endpoint(ep)
        results.append(result)
        status_char = "✅" if result["pass"] else "❌"
        code = result["status_code"] or result["error"]
        lat = f"{result['latency_ms']}ms" if result['latency_ms'] else "n/a"
        print(f"{status_char} [{code}] {ep['name']:<30} {lat}")

    # Summary
    passed = sum(1 for r in results if r["pass"])
    failed = len(results) - passed
    print(f"\n{'='*70}")
    print(f"SUMMARY: {passed} PASS / {failed} FAIL out of {len(results)} endpoints")
    print(f"{'='*70}\n")

    # Category breakdown for failures
    print("FAILURES DETAIL:")
    for r in results:
        if not r["pass"]:
            error_class = "ROUTE MISSING" if r["status_code"] == 404 else \
                          "METHOD MISMATCH" if r["status_code"] == 405 else \
                          "VALIDATION ERROR" if r["status_code"] in (400, 422) else \
                          "AUTH/ACCESS" if r["status_code"] in (401, 403) else \
                          "DEPENDENCY FAIL (500)" if r["status_code"] == 500 else \
                          "TIMEOUT/NETWORK" if r["error"] == "TIMEOUT" else \
                          f"UNKNOWN [{r['status_code']}]"
            print(f"  - {r['name']:<30} [{r['status_code']}] {error_class}")
            if r["snippet"]:
                print(f"    Response: {r['snippet'][:200]}")

    # Key data checks
    print("\nKEY DATA CHECKS:")
    for r in results:
        if r["name"] == "health" and r["json"]:
            d = r["json"]
            print(f"  health.status        = {d.get('status')}")
            print(f"  health.nba_api       = {d.get('nba_api')}")
            print(f"  health.database      = {d.get('database')}")
        if r["name"] == "schedule" and r["json"]:
            d = r["json"]
            print(f"  schedule.games       = {d.get('total', len(d.get('games',[])))} games")
            print(f"  schedule.source      = {d.get('source')}")
            print(f"  schedule.error       = {d.get('error')}")
        if r["name"] == "live_games" and r["json"]:
            d = r["json"]
            meta = d.get("meta", {})
            print(f"  live_games.count     = {meta.get('game_count', 'N/A')}")
            print(f"  live_games.live      = {meta.get('live_count', 'N/A')}")
            print(f"  live_games.error     = {d.get('error', 'none')}")
        if r["name"] == "live_leaders" and r["json"]:
            d = r["json"]
            print(f"  live_leaders.count   = {d.get('count', 'N/A')}")
            print(f"  live_leaders.leaders = {len(d.get('leaders', []))} returned")
            print(f"  live_leaders.error   = {d.get('error', 'none')}")

    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"cloud_run_audit_{ts}.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "results": results
        }, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
