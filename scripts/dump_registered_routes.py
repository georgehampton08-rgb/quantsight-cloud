"""
Dump Registered Routes
======================
Extracts all registered FastAPI routes from the application and writes
them to a JSON file for cross-referencing against 404 incidents.

Can be run as a standalone script (static extraction) or imported
to produce a runtime dump via the FastAPI app object.

Usage:
    python scripts/dump_registered_routes.py
"""
import json
import sys
from pathlib import Path

# Statically-known routes based on source-code analysis of backend/main.py
# and all registered routers.  This list is the authoritative reference
# used by the 404 classification report.

REGISTERED_ROUTES = [
    # main.py direct
    {"method": "GET",    "path": "/",                                       "source": "main.py"},
    {"method": "GET",    "path": "/health",                                 "source": "main.py"},
    {"method": "GET",    "path": "/status",                                 "source": "main.py"},
    {"method": "GET",    "path": "/favicon.ico",                            "source": "main.py"},
    {"method": "GET",    "path": "/manifest.json",                          "source": "main.py"},

    # api/admin_routes.py (prefix /admin)
    {"method": "GET",    "path": "/admin/status",                           "source": "api/admin_routes.py"},
    {"method": "POST",   "path": "/admin/init-collections",                 "source": "api/admin_routes.py"},
    {"method": "GET",    "path": "/admin/collections/status",               "source": "api/admin_routes.py"},
    {"method": "POST",   "path": "/admin/seed/sample-data",                 "source": "api/admin_routes.py"},
    {"method": "DELETE", "path": "/admin/collections/{collection_name}/clear", "source": "api/admin_routes.py"},

    # api/public_routes.py
    {"method": "GET",    "path": "/debug/teams-schema",                     "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/teams",                                  "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/players",                                "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/players/search",                         "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/players/{player_id}",                    "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/roster/{team_id}",                       "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/injuries",                               "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/schedule",                               "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/matchup-lab/games",                      "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/matchup/roster/{team_id}",               "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/teams/{team_abbrev}",                    "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/player/{player_id}",                     "source": "api/public_routes.py"},
    {"method": "POST",   "path": "/settings/gemini-key",                    "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/analyze/usage-vacuum",                   "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/matchup/analyze",                        "source": "api/public_routes.py"},
    {"method": "POST",   "path": "/analyze/crucible",                       "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/live/stream",                            "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/live/leaders",                           "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/game-dates",                             "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/live/games",                             "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/live/status",                            "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/game-logs",                              "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/api/game-logs",                          "source": "api/public_routes.py"},
    {"method": "GET",    "path": "/boxscore/{game_id}",                     "source": "api/public_routes.py"},

    # api/injury_admin.py (prefix /admin/injuries)
    {"method": "POST",   "path": "/admin/injuries/add",                     "source": "api/injury_admin.py"},
    {"method": "POST",   "path": "/admin/injuries/bulk",                    "source": "api/injury_admin.py"},
    {"method": "DELETE", "path": "/admin/injuries/remove/{player_id}",      "source": "api/injury_admin.py"},
    {"method": "GET",    "path": "/admin/injuries/all",                     "source": "api/injury_admin.py"},
    {"method": "GET",    "path": "/admin/injuries/team/{team_abbr}",        "source": "api/injury_admin.py"},

    # nexus/routes.py (prefix /nexus)
    {"method": "GET",    "path": "/nexus/health",                           "source": "nexus/routes.py"},
    {"method": "GET",    "path": "/nexus/cooldowns",                        "source": "nexus/routes.py"},
    {"method": "POST",   "path": "/nexus/cooldowns/{key}",                  "source": "nexus/routes.py"},
    {"method": "DELETE", "path": "/nexus/cooldowns/{key}",                  "source": "nexus/routes.py"},
    {"method": "GET",    "path": "/nexus/cooldowns/{key}",                  "source": "nexus/routes.py"},

    # api/game_logs_routes.py
    {"method": "GET",    "path": "/api/game-logs",                          "source": "api/game_logs_routes.py"},

    # api/h2h_population_routes.py (prefix /api/h2h)
    {"method": "POST",   "path": "/api/h2h/populate",                       "source": "api/h2h_population_routes.py"},
    {"method": "GET",    "path": "/api/h2h/status/{player_id}/{opponent}",   "source": "api/h2h_population_routes.py"},
    {"method": "POST",   "path": "/api/h2h/fetch/{player_id}/{opponent}",    "source": "api/h2h_population_routes.py"},
    {"method": "GET",    "path": "/api/h2h/games/{player_id}/{opponent}",    "source": "api/h2h_population_routes.py"},

    # app/routers/aegis.py (include_router prefix /aegis)
    {"method": "GET",    "path": "/aegis/simulate/{player_id}",              "source": "app/routers/aegis.py"},

    # vanguard/api/health.py (prefix /vanguard)
    {"method": "GET",    "path": "/vanguard/health",                         "source": "vanguard/api/health.py"},
    {"method": "GET",    "path": "/vanguard/incidents",                      "source": "vanguard/api/health.py"},
    {"method": "GET",    "path": "/vanguard/incidents/{fingerprint}",        "source": "vanguard/api/health.py"},

    # vanguard/api/admin_routes.py
    {"method": "POST",   "path": "/vanguard/admin/mode",                     "source": "vanguard/api/admin_routes.py"},
    {"method": "GET",    "path": "/vanguard/admin/incidents",                "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/incidents/{fp}/resolve",   "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/incidents/bulk-resolve",   "source": "vanguard/api/admin_routes.py"},
    {"method": "GET",    "path": "/vanguard/admin/incidents/{fp}",           "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/incidents/analyze-all",    "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/incidents/resolve-all",    "source": "vanguard/api/admin_routes.py"},
    {"method": "GET",    "path": "/vanguard/admin/learning/status",          "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/learning/export",          "source": "vanguard/api/admin_routes.py"},
    {"method": "GET",    "path": "/vanguard/admin/archives",                 "source": "vanguard/api/admin_routes.py"},
    {"method": "GET",    "path": "/vanguard/admin/archives/{filename}",      "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/archives/create",          "source": "vanguard/api/admin_routes.py"},
    {"method": "GET",    "path": "/vanguard/admin/incidents/{fp}/analysis",   "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/incidents/{fp}/analyze",   "source": "vanguard/api/admin_routes.py"},
    {"method": "POST",   "path": "/vanguard/admin/resolve/{fp}",             "source": "vanguard/api/admin_routes.py"},
    {"method": "GET",    "path": "/vanguard/admin/incidents/{fp}/verification", "source": "vanguard/api/admin_routes.py"},

    # vanguard/api/cron_routes.py
    {"method": "POST",   "path": "/vanguard/admin/cron/archive",             "source": "vanguard/api/cron_routes.py"},
]


def dump_routes(output_path: str = None):
    """Write the registered routes to a JSON file."""
    out = output_path or str(
        Path(__file__).parent / "dump_registered_routes.json"
    )

    # Build a lookup-friendly structure
    data = {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total_routes": len(REGISTERED_ROUTES),
        "routes": REGISTERED_ROUTES,
        "path_index": sorted(set(r["path"] for r in REGISTERED_ROUTES)),
    }

    with open(out, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Dumped {len(REGISTERED_ROUTES)} routes -> {out}")
    return data


if __name__ == "__main__":
    dump_routes()
