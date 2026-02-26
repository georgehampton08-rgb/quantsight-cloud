import json
import re

with open(r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\scripts\scan_frontend_api.json', 'r') as f:
    data = json.load(f)

# Known backend routes
backend_routes = [
    "/admin/init-collections", "/admin/collections/status", "/admin/seed/sample-data", "/admin/collections/{name}/clear",
    "/teams", "/teams/{team_abbrev}", "/players", "/players/{player_id}", "/players/search", "/schedule", "/injuries", "/roster/{team_id}", "/player/{player_id}",
    "/api/game-logs", "/game-logs", "/game-dates", "/boxscore/{game_id}",
    "/api/h2h/populate", "/api/h2h/status/{player_id}/{opponent}", "/api/h2h/fetch/{player_id}/{opponent}",
    "/admin/injuries/add", "/admin/injuries/bulk", "/admin/injuries/remove/{player_id}", "/admin/injuries/all", "/admin/injuries/team/{team_abbr}",
    "/matchup/analyze", "/matchup/{player_id}/{opponent}", "/matchup-lab/games", "/matchup-lab/crucible-sim", "/analyze/crucible", "/analyze/usage-vacuum", "/usage-vacuum/analyze",
    "/radar/{player_id}", "/aegis/matchup", "/aegis/simulate/{player_id}", "/aegis/player/{player_id}", "/player-data/refresh/{player_id}", "/debug/teams-schema", "/settings/gemini-key",
    "/nexus/health", "/nexus/cooldowns", "/nexus/cooldowns/{key}",
    "/live/stream", "/live/leaders", "/live/games", "/live/status",
    "/healthz", "/readyz", "/health", "/health/deps",
    "/vanguard/health", "/vanguard/incidents", "/vanguard/admin/stats", "/vanguard/incidents/{fp}",
    "/vanguard/admin/mode", "/vanguard/admin/incidents", "/vanguard/admin/incidents/{fp}/resolve", "/vanguard/admin/incidents/{fp}/analyze", "/vanguard/admin/incidents/{fp}/analysis", "/vanguard/admin/incidents/analyze-all", "/vanguard/admin/incidents/resolve-all", "/vanguard/admin/incidents/bulk-resolve", "/vanguard/admin/learning/status", "/vanguard/admin/learning/export", "/vanguard/admin/archives", "/vanguard/admin/cron/archive",
    "/vanguard/vaccine/inject", "/vanguard/vaccine/status",
    "/cron/vanguard/purge", "/cron/vanguard/archive",
    "/data/player-hustle/{player_id}", "/aegis/ledger/trace/{player_id}", "/players/{player_id}/play-types"
]

inventory = []
used_routes = set()

for item in data:
    file = item['file']
    code = item['code']
    if 'client.ts' in file: continue
    
    path = "unknown"
    method = "GET"
    transport = "web"
    status = "LIVE"
    func_name = "unknown"
    
    # Try to extract function/hook name
    # We will just use the filename for now, or a rough guess
    func_name = file.split('/')[-1].replace('.tsx', '').replace('.ts', '')
    
    if 'ApiContract.execute' in code:
        transport = 'IPC | web'
        m = re.search(r"path:\s*['`](.*?)['`]", code)
        if m: path = "/" + m.group(1)
        else:
            # check if the first arg is the route
            m2 = re.search(r"execute(?:<.*?>)?\(\s*['`](.*?)['`]", code)
            if m2 and m2.group(1) != "null": 
                func_name_mapped = m2.group(1)
                # We can't always know the path if it's not provided
                path = "ipc-mapped: " + func_name_mapped
            else:
                path = "dynamic/unknown"
    elif 'fetch(' in code:
        transport = 'web'
        m = re.search(r"fetch\(['`](.*?)['`]", code)
        if m: path = m.group(1).split('}')[1] if '}' in m.group(1) else m.group(1)
        if '${base}' in code or 'API_BASE' in code or 'quantsight-cloud' in code:
            parts = code.split('fetch(')[1].split(',')[0]
            m = re.search(r"[`'\"](.*?\})?(/[^`'\?\"]+)", code)
            if m: path = m.group(2)
        
        if 'method:' in code:
            m = re.search(r"method:\s*['`](.*?)['`]", code)
            if m: method = m.group(1)
            
    if 'nexus' in path: 
        status = 'DEAD'
    elif 'aegis/simulate' in path: 
        status = 'NEEDS_STUB'
    elif path.startswith("ipc-mapped: "):
        status = 'LIVE'
    elif path not in ['unknown', 'dynamic/unknown']:
        matched = False
        for r in backend_routes:
            r_clean = re.sub(r'\{.*?\}', '', r)
            p_clean = re.sub(r'\$\{.*?\}', '', path)
            if r_clean in p_clean or p_clean in r_clean:
                matched = True
                used_routes.add(r)
                break
        if not matched: status = 'BROKEN (404)'
        
    inventory.append(f"| {file} | {func_name} | {method} | {path} | {transport} | {status} |")

# Table 2: Dead / Broken Routes
# Identify dead or broken routes
# nexus is dead. aegis simulates need stub.
table2 = [
    "| Path | Current Status | Root Cause | Required Fix |",
    "|---|---|---|---|",
    "| /nexus/* | DEAD | Module import failure in Cloud Run | Disable/Stub in Phase 1 |",
    "| /live/* | BROKEN | Moved from Main API to Pulse Service | Route to VITE_PULSE_API_URL |",
    "| /aegis/simulate | LIVE (Returns 0s) | Feature disabled | Implement stub detection |"
]

# Table 3: Unused Backend Routes
table3 = [
    "| Path | Returns | UI Candidate | Priority |",
    "|---|---|---|---|",
    "| /health/deps | System Health Status | Health Deps Panel (SettingsPage) | High |",
    "| /boxscore/{game_id} | Game Box Score | BoxScore Viewer (CommandCenterPage) | Medium |",
    "| /api/h2h/* | H2H History | H2H History Panel (PlayerProfilePage) | Medium |",
    "| /game-logs | Game Logs | Game Logs Viewer (PlayerProfilePage) | High |",
    "| /admin/injuries/team/{team} | Filtered Injuries | Injury Team Filter (InjuryAdmin) | Low |",
    "| /vanguard/admin/learning/export | JSON Export | Vanguard Learning Export | Low |",
    "| /vanguard/admin/archives | Archives List | Vanguard Archives Viewer | Medium |",
    "| /vanguard/vaccine/* | Vaccine Status | Vaccine Status Panel | High |"
]

# Table 4: Response Shape Mismatches
table4 = [
    "| Endpoint | Frontend Reads | Backend Returns | Delta | Fix Required |",
    "|---|---|---|---|---|",
    "| /players/search | id | player_id / id | id vs player_id | Add normalizePlayerProfile |",
    "| /vanguard/admin/incidents | count | occurrence_count | count vs occurrence_count | Add normalizeVanguardIncidentList |",
    "| /aegis/simulate | expected_value | ev | expected_value vs ev | Add normalizeSimulationResult |",
    "| /matchup/{p1}/{p2} | trend: null | trend: [] | null array | Default to empty array |"
]

# Table 5: Feature Flag States
table5 = [
    "| Flag | Value | Frontend Impact | Required Behavior |",
    "|---|---|---|---|",
    "| FEATURE_NEXUS_ENABLED | False | /nexus routes 404 | Return graceful stubs |",
    "| FEATURE_AEGIS_SIM_ENABLED | False | Returns zeros | Detect 0s + !available flag -> show 'Unavailable' |",
    "| FEATURE_LEGACY_CRUCIBLE | False | Mock returns | Stub behavior |",
    "| FEATURE_USAGE_VACUUM | False | Mock returns | Stub behavior |",
    "| FEATURE_WEBSOCKET_ENABLED | False | Websocket inactive | Use SSE fallback or stub |"
]

with open(r'C:\Users\georg\.gemini\antigravity\brain\bfc40eec-f05d-4bec-a4a9-6990320c20da\phase_0_audit.md', 'w') as f:
    f.write("# Phase 0: Full System Audit\n\n")
    f.write("---\n\n## Table 1: CALLSITE INVENTORY\n\n")
    f.write("| File | Function | Method | Path | Transport | Status |\n")
    f.write("|---|---|---|---|---|---|\n")
    for row in inventory: f.write(row + "\n")
    
    f.write("\n## Table 2: DEAD / BROKEN ROUTES\n\n")
    for row in table2: f.write(row + "\n")
    
    f.write("\n## Table 3: UNUSED BACKEND ROUTES\n\n")
    for row in table3: f.write(row + "\n")
    
    f.write("\n## Table 4: RESPONSE SHAPE MISMATCHES\n\n")
    for row in table4: f.write(row + "\n")
    
    f.write("\n## Table 5: FEATURE FLAG STATES\n\n")
    for row in table5: f.write(row + "\n")

    f.write("\n\n> [!WARNING] Divergence Note: `aegisApi.ts`, `nexusApi.ts`, `prefetchService.ts`, and `useNexusHealth.ts` were removed in a previous dead code audit. The current frontend is running primarily via direct fetches or newly mapped `ApiContract` calls in `src/`. For Phase 1 stubs, these files need to be restored or the stubs applied directly to the hooks (e.g., `useSimulation.ts`).\n")

