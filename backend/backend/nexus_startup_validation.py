"""
Nexus Hub Startup Validation
============================
Runs Healer Protocol checks before server startup to ensure clean environment.

Validates:
- Data integrity (CSV files, SQLite DB)
- Component initialization
- No orphaned quarantine files
- System resources
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from aegis.healer_protocol import HealerProtocol
from aegis.nexus_hub import NexusHub
from aegis.health_monitor import WorkerHealthMonitor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class NexusStartupValidator:
    """Pre-startup validation for Nexus Hub"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.healer = HealerProtocol(data_dir=data_dir)
        self.issues_found = []
        self.fixes_applied = []
    
    async def run(self) -> bool:
        """
        Run all validation checks.
        
        Returns:
            True if system is ready, False if critical issues found
        """
        logger.info("=" * 60)
        logger.info("NEXUS HUB STARTUP VALIDATION")
        logger.info("=" * 60)
        
        checks = [
            self._check_data_dirs(),
            self._check_quarantine(),
            self._check_database(),
            self._check_system_resources(),
            self._check_nexus_initialization()
        ]
        
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        # Count results
        passed = sum(1 for r in results if r is True)
        total = len(checks)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"VALIDATION SUMMARY: {passed}/{total} checks passed")
        logger.info("=" * 60)
        
        if self.issues_found:
            logger.warning(f"Issues found: {len(self.issues_found)}")
            for issue in self.issues_found:
                logger.warning(f"  - {issue}")
        
        if self.fixes_applied:
            logger.info(f"Fixes applied: {len(self.fixes_applied)}")
            for fix in self.fixes_applied:
                logger.info(f"  ✓ {fix}")
        
        if passed < total:
            logger.error("VALIDATION FAILED - Please fix issues before starting")
            return False
        
        logger.info("✅ ALL CHECKS PASSED - System ready for startup")
        return True
    
    async def _check_data_dirs(self) -> bool:
        """Check that all required data directories exist"""
        logger.info("[1/5] Checking data directories...")
        
        required_dirs = [
            self.data_dir / "players",
            self.data_dir / "quarantine",
            self.data_dir / "aegis_storage"
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                self.fixes_applied.append(f"Created {dir_path}")
        
        logger.info("  ✓ Data directories OK")
        return True
    
    async def _check_quarantine(self) -> bool:
        """Clean up old quarantine files"""
        logger.info("[2/5] Checking quarantine directory...")
        
        try:
            removed = await self.healer.cleanup_quarantine(max_age_days=7)
            if removed > 0:
                self.fixes_applied.append(f"Removed {removed} old quarantine files")
            
            # Check for any active healing operations
            status = self.healer.get_healing_status()
            if status['active']:
                self.issues_found.append(
                    f"{len(status['active'])} active healing operations - "
                    "may indicate recent data corruption"
                )
            
            logger.info(f"  ✓ Quarantine cleaned ({removed} old files removed)")
            return True
            
        except Exception as e:
            logger.error(f"  ✗ Quarantine check failed: {e}")
            self.issues_found.append(f"Quarantine check error: {e}")
            return False
    
    async def _check_database(self) -> bool:
        """Verify database accessibility"""
        logger.info("[3/5] Checking database...")
        
        db_path = self.data_dir.parent / "nba_data.db"
        
        if not db_path.exists():
            self.issues_found.append(f"Database not found: {db_path}")
            logger.error(f"  ✗ Database missing: {db_path}")
            return False
        
        # Try to connect
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Quick integrity check
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            
            if result[0] != "ok":
                self.issues_found.append("Database integrity check failed")
                logger.error("  ✗ Database integrity compromised")
                conn.close()
                return False
            
            # Check table count
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table';"
            )
            table_count = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"  ✓ Database OK ({table_count} tables)")
            return True
            
        except Exception as e:
            self.issues_found.append(f"Database error: {e}")
            logger.error(f"  ✗ Database error: {e}")
            return False
    
    async def _check_system_resources(self) -> bool:
        """Check system resources"""
        logger.info("[4/5] Checking system resources...")
        
        try:
            import psutil
            
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            
            # Warning thresholds
            if cpu > 90:
                self.issues_found.append(f"High CPU usage: {cpu}%")
            
            if mem.percent > 90:
                self.issues_found.append(f"High memory usage: {mem.percent}%")
            
            logger.info(
                f"  ✓ Resources OK (CPU: {cpu}%, Mem: {mem.percent}%, "
                f"Available: {mem.available // (1024**2)}MB)"
            )
            return True
            
        except ImportError:
            logger.warning("  ⚠ psutil not available - skipping resource check")
            return True
    
    async def _check_nexus_initialization(self) -> bool:
        """Test Nexus Hub initialization"""
        logger.info("[5/5] Testing Nexus initialization...")
        
        try:
            # Create health monitor
            monitor = WorkerHealthMonitor()
            
            # Initialize Nexus Hub
            hub = NexusHub(worker_monitor=monitor)
            
            # Verify components
            if len(hub.registry.endpoints) < 14:
                self.issues_found.append(
                    f"Expected 14 endpoints, found {len(hub.registry.endpoints)}"
                )
                return False
            
            # Get status
            status = hub.get_overall_status()
            
            logger.info(
                f"  ✓ Nexus Hub OK (v{hub.VERSION}, {len(hub.registry.endpoints)} endpoints, "
                f"status: {status})"
            )
            return True
            
        except Exception as e:
            self.issues_found.append(f"Nexus initialization failed: {e}")
            logger.error(f"  ✗ Nexus init failed: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Run startup validation"""
    current_dir = Path(__file__).parent
    data_dir = current_dir / "data"
    
    validator = NexusStartupValidator(data_dir)
    success = await validator.run()
    
    if not success:
        logger.error("\n❌ STARTUP VALIDATION FAILED")
        logger.error("Please address the issues above before starting the server.")
        sys.exit(1)
    
    logger.info("\n✅ STARTUP VALIDATION PASSED")
    logger.info("System is ready for Nexus Hub operation.")
    logger.info("\nYou may now start the server with: npm run electron:dev")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
