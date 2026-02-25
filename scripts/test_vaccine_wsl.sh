#!/usr/bin/env bash
# Quick import check for vaccine modules
set -e
cd ~/dev/quantsight_cloud_build
source .venv/bin/activate

echo "== Checking vaccine files exist =="
ls -la vanguard/vaccine/plan_engine.py vanguard/vaccine/patch_applier.py vanguard/vaccine/generator.py vanguard/api/vaccine_routes.py 2>&1

echo ""
echo "== Testing imports =="
python -c "
from vanguard.vaccine.plan_engine import VaccinePlanEngine, get_plan_engine
print('plan_engine OK')

from vanguard.vaccine.patch_applier import VaccinePatchApplier, get_patch_applier
print('patch_applier OK')

from vanguard.vaccine.generator import VaccineGenerator, get_vaccine
print('generator OK')

from vanguard.api.vaccine_routes import router
print(f'vaccine_routes OK: {len(router.routes)} routes')

from vanguard.core.config import VanguardConfig
c = VanguardConfig()
print(f'config OK: max_daily={c.vaccine_max_daily_fixes}')
"

echo ""
echo "== Running vaccine smoke =="
python scripts/vaccine_smoke.py
