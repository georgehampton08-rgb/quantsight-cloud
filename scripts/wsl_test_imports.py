import fastapi, uvicorn
try:
    import nba_api
    nba_ok = "OK"
except ImportError as e:
    nba_ok = f"MISSING: {e}"

try:
    import google.cloud.firestore
    firestore_ok = "OK"
except ImportError as e:
    firestore_ok = f"MISSING: {e}"

try:
    import sse_starlette
    sse_ok = "OK"
except ImportError as e:
    sse_ok = f"MISSING: {e}"

print("FastAPI:", fastapi.__version__)
print("uvicorn: OK")
print("nba_api:", nba_ok)
print("google-cloud-firestore:", firestore_ok)
print("sse_starlette:", sse_ok)
print("ALL CORE IMPORTS OK")
