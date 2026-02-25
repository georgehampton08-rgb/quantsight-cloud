import json, glob, os

reports = sorted(glob.glob(r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\reports\cloud_run_audit_*.json'))
path = reports[-1]
print('Report:', os.path.basename(path))

with open(path, encoding='utf-8') as f:
    d = json.load(f)

print('TOTAL: {}  PASS: {}  FAIL: {}'.format(d['total'], d['passed'], d['failed']))
print()
for r in d['results']:
    flag = 'PASS' if r['pass'] else 'FAIL'
    code = r['status_code'] or r['error']
    lat = str(r.get('latency_ms','?'))+'ms'
    name = r['name']
    # Show snippet for all relevant endpoints
    show = not r['pass'] or name in ('live_games','live_leaders','nexus_overview','nexus_route_matrix','aegis_player','aegis_player_stats','radar')
    snippet = ''
    if show and r['snippet']:
        snippet = ' => ' + r['snippet'][:200].replace('\n',' ')
    print('{} [{}] {:<30} {}{}'.format(flag, code, name, lat, snippet))
