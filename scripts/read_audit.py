import json, sys

path = r'c:\Users\georg\quantsight_engine\quantsight_cloud_build\reports\cloud_run_audit_20260224_095603.json'
with open(path) as f:
    d = json.load(f)

print('TOTAL: {}  PASS: {}  FAIL: {}'.format(d['total'], d['passed'], d['failed']))
print()
for r in d['results']:
    flag = 'PASS' if r['pass'] else 'FAIL'
    code = r['status_code'] or r['error']
    lat = str(r.get('latency_ms','?'))+'ms'
    name = r['name']
    snippet = ''
    if not r['pass'] and r['snippet']:
        snippet = ' => ' + r['snippet'][:180].replace('\n',' ')
    print('{} [{}] {:<30} {}{}'.format(flag, code, name, lat, snippet))
