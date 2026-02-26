import json
import re

with open(r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\scripts\scan_frontend_api.json', 'r') as f:
    data = json.load(f)

# Hardcoded backend registry for cross-referencing
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
    "/cron/vanguard/purge", "/cron/vanguard/archive"
]

table1 = []
table2 = []

for item in data:
    file = item['file']
    code = item['code']
    if 'client.ts' in file: continue # skip client inner workings
    
    path = "unknown"
    method = "GET"
    transport = "web"
    status = "LIVE"
    
    if 'ApiContract.execute' in code:
        transport = 'IPC | web'
        m = re.search(r"path:\s*['`](.*?)['`]", code)
        if m: path = "/" + m.group(1)
        else: path = "dynamic/unknown"
    elif 'fetch(' in code:
        transport = 'web'
        m = re.search(r"fetch\(['`](.*?)['`]", code)
        if m: path = m.group(1).split('}')[1] if '}' in m.group(1) else m.group(1)
        if '${base}' in code or 'API_BASE' in code or 'quantsight-cloud' in code:
            parts = code.split('fetch(')[1].split(',')[0]
            clean_path = re.sub(r"[`'\"](.*?\})?(/.*?)[\?`'\"]", r"\2", parts)
            path = clean_path if clean_path.startswith('/') else "dynamic"
            # very dirty parsing, let's just extract the raw string
            m = re.search(r"[`'\"](.*?\})?(/[^`'\?\"]+)", code)
            if m: path = m.group(2)
    
        if 'method:' in code:
            m = re.search(r"method:\s*['`](.*?)['`]", code)
            if m: method = m.group(1)
            
    # Check if dead or missing
    if 'nexus' in path: status = 'DEAD'
    elif 'aegis/simulate' in path: status = 'NEEDS_STUB'
    elif path not in ['unknown', 'dynamic']:
        # rough match
        matched = False
        for r in backend_routes:
            # remove path params for matching
            r_clean = re.sub(r'\{.*?\}', '', r)
            p_clean = re.sub(r'\$\{.*?\}', '', path)
            if r_clean in p_clean or p_clean in r_clean:
                matched = True
                break
        if not matched: status = 'BROKEN (404)'
        
    table1.append(f"| {file} | {path} | {method} | {path} | {transport} | {status} |")

print("Table 1: CALLSITE INVENTORY")
print("| File | Function | Method | Path | Transport | Status |")
print("|---|---|---|---|---|---|")
for t in table1: print(t)

