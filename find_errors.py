import json

log_file = "c:/Users/georg/quantsight_engine/quantsight_cloud_build/incident_logs.json"
try:
    with open(log_file, "r", encoding="utf-8") as f:
        logs = json.load(f)
        
    errors = []
    for log in logs:
        text = log.get("textPayload", "")
        if "The request was aborted because there was no available instance" in text:
            continue
        errors.append(log)
        
    for e in errors[:30]:
        print(f"{e.get('timestamp')} [{e.get('severity', 'UNKNOWN')}] {e.get('textPayload', e.get('jsonPayload', str(e)))}")
        
    print(f"\nFound {len(errors)} significant logs out of {len(logs)} total.")
except Exception as e:
    print("Error:", e)
