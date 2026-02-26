import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SYSTEM_SNAPSHOT = {
    "firestore_ok": True,
    "gemini_ok": True,
    "vanguard_ok": True,
    "updated_at": datetime.now(timezone.utc).isoformat()
}

_snapshot_task = None

async def update_snapshot_loop():
    """Background loop to periodically verify dependencies and update the global snapshot."""
    while True:
        try:
            # Check Firestore, Gemini
            from vanguard.health_monitor import get_health_monitor
            monitor = get_health_monitor()
            # Use bounded timeout internally
            try:
                results = await asyncio.wait_for(monitor.run_all_checks(), timeout=5.0)
                SYSTEM_SNAPSHOT["firestore_ok"] = results.get("firestore", {}).get("status") != "critical"
                SYSTEM_SNAPSHOT["gemini_ok"] = results.get("gemini_ai", {}).get("status") == "healthy"
            except asyncio.TimeoutError:
                SYSTEM_SNAPSHOT["firestore_ok"] = False
                SYSTEM_SNAPSHOT["gemini_ok"] = False

            # Check Vanguard subsystems via Oracle
            try:
                from vanguard.ai.subsystem_oracle import get_oracle
                # Pass a dummy string for storage to avoid cyclic imports if archivist fails, 
                # but Oracle gracefully handles it
                oracle = get_oracle()
                # Run with timeout
                oracle_snap = await asyncio.wait_for(oracle.collect("health_ping", None), timeout=5.0)
                SYSTEM_SNAPSHOT["vanguard_ok"] = oracle_snap.critical_count == 0
            except Exception as e:
                SYSTEM_SNAPSHOT["vanguard_ok"] = False
                
            SYSTEM_SNAPSHOT["updated_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.error(f"Snapshot loop encountered an error: {e}")
            
        await asyncio.sleep(30)

def start_snapshot_loop():
    global _snapshot_task
    if _snapshot_task is None:
        _snapshot_task = asyncio.create_task(update_snapshot_loop())

def stop_snapshot_loop():
    global _snapshot_task
    if _snapshot_task is not None:
        _snapshot_task.cancel()
        _snapshot_task = None
