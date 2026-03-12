import subprocess
import json

query = 'resource.type="cloud_run_revision" AND resource.labels.service_name="quantsight-cloud" AND timestamp>="2026-03-10T13:29:00-05:00" AND timestamp<="2026-03-10T13:31:00-05:00"'

cmd = [
    "gcloud.cmd", "logging", "read",
    query,
    "--project", "quantsight-prod",
    "--format", "json"
]

print("Executing:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)

out_file = "c:/Users/georg/quantsight_engine/quantsight_cloud_build/incident_logs.json"
with open(out_file, "w", encoding="utf-8") as f:
    f.write(res.stdout)

print(f"Logs written to {out_file} (bytes: {len(res.stdout)})")
if res.stderr:
    print("STDERR:", res.stderr)
