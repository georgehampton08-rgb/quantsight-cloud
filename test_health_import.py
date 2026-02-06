"""
Quick test script to check if vanguard health router imports correctly
"""

import sys
sys.path.insert(0, 'c:/Users/georg/quantsight_engine/quantsight_cloud_build/backend')

try:
    from vanguard.api.health import router as health_router
    print("✅ SUCCESS: Vanguard health router imported!")
    print(f"Router prefix: {health_router.prefix}")
    print(f"Router routes: {[route.path for route in health_router.routes]}")
    
    # Check routes
    for route in health_router.routes:
        print(f"  - {route.path}: {route.methods}")
        
except ImportError as e:
    print(f"❌ FAILED: Import error: {e}")
except Exception as e:
    print(f"❌ FAILED: Unexpected error: {e}")
