"""Phase 8 parse + import validation."""
import ast
import sys
import os

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

files = [
    "services/ws_connection_manager.py",
    "services/ws_message_handler.py",
    "services/presence_manager.py",
    "services/annotation_service.py",
    "services/ws_heartbeat.py",
    "api/websocket_routes.py",
    "telemetry/custom_metrics.py",
]

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []

# Phase 1: AST parse validation
for f in files:
    fpath = os.path.join(backend_dir, f)
    try:
        with open(fpath, encoding="utf-8") as fh:
            ast.parse(fh.read())
        print(f"PARSE OK: {f}")
    except Exception as e:
        errors.append(f"PARSE FAIL: {f}: {e}")
        print(f"PARSE FAIL: {f}: {e}")

# Phase 2: Feature flag check
try:
    from vanguard.core.feature_flags import _FLAG_DEFAULTS
    assert _FLAG_DEFAULTS["FEATURE_WEBSOCKET_ENABLED"] is True
    print("FLAG OK: FEATURE_WEBSOCKET_ENABLED=True")
except Exception as e:
    errors.append(f"FLAG FAIL: {e}")
    print(f"FLAG FAIL: {e}")

# Phase 3: Connection manager sync
try:
    from services.ws_connection_manager import WebSocketConnectionManager, get_ws_manager
    mgr = get_ws_manager()
    stats = mgr.get_stats()
    assert stats["websocket_connections_active"] == 0
    assert stats["websocket_enabled"] is True
    print(f"MANAGER OK: {stats}")
except Exception as e:
    errors.append(f"MANAGER FAIL: {e}")
    print(f"MANAGER FAIL: {e}")

# Phase 4: Route structure
try:
    from api.websocket_routes import router
    paths = [str(getattr(r, "path", "")) for r in router.routes]
    assert "/live/ws" in paths, f"/live/ws not in {paths}"
    assert any("presence" in p for p in paths), f"No presence route in {paths}"
    assert any("annotations" in p for p in paths), f"No annotations route in {paths}"
    print(f"ROUTES OK: {paths}")
except Exception as e:
    errors.append(f"ROUTES FAIL: {e}")
    print(f"ROUTES FAIL: {e}")

print()
if errors:
    print(f"FAILURES: {len(errors)}")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("ALL PHASE 8 VALIDATION PASSED")
